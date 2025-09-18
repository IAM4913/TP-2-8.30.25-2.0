from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from collections import defaultdict
from .excel_utils import build_priority_bucket
import re

# Customers that cannot be combined with other customers on same truck
NO_MULTI_STOP_CUSTOMERS = [
    "Sabre Tubular Structures",
    "GamTex",
    "Cmcr Fort Worth",
    "Ozark Steel LLC",
    "Gachman Metals & Recycling Co",
    "Sabre",
    "Sabre - Kennedale",
    "Sabre Industries",
    "Sabre Southbridge Plate STP",
    "Petrosmith Equipment LP",
    "W&W AFCO STEEL",
    "Red Dot Corporation",
    # Add more customer names here as needed
]


def is_texas(state: str) -> bool:
    return str(state).strip().upper() in {"TX", "TEXAS"}


def allows_multi_stop(customer: str) -> bool:
    """Check if customer allows combining with other customers on same truck"""
    return str(customer).strip().upper() not in [c.upper() for c in NO_MULTI_STOP_CUSTOMERS]


def can_combine_customers(customer1: str, customer2: str) -> bool:
    """Check if two customers can be combined on the same truck"""
    if customer1 == customer2:
        return True
    # If either customer is in no-multi-stop list, they cannot be combined
    return allows_multi_stop(customer1) and allows_multi_stop(customer2)


def naive_grouping(df: pd.DataFrame, weight_config: Dict[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # Filter rows with required basics
    required = [
        "SO",
        "Line",
        "Customer",
        "shipping_city",
        "shipping_state",
        "RPcs",
        "Ready Weight",
        "Width",
    ]
    # Optional columns for enhanced grouping
    optional_grouping_cols = ["Zone", "Route"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for optimization: {missing}")

    # Normalize optional grouping headers case-insensitively (Zone/Route), be robust to whitespace and variants
    def norm_key(s: Any) -> str:
        s = str(s)
        s = re.sub(r"\s+", " ", s)
        s = s.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    df = df.copy()
    normalized = {norm_key(c): c for c in df.columns}

    def find_col(target: str, contains_ok: bool = True) -> Optional[str]:
        # prefer exact first
        if target in normalized:
            return normalized[target]
        if contains_ok:
            # find any column whose normalized key contains target
            for nk, orig in normalized.items():
                if target in nk:
                    return orig
        return None

    zone_src = find_col('zone')
    route_src = find_col('route')
    # Source transport identifier column (e.g., trttav_no)
    trttav_src = find_col('trttavno', contains_ok=False) or find_col('trttavno')
    if zone_src is not None and 'Zone' not in df.columns:
        df['Zone'] = df[zone_src]
    if route_src is not None and 'Route' not in df.columns:
        df['Route'] = df[route_src]

    # Determine per-piece weight; fallback evenly if missing
    per_piece = df.get("Weight Per Piece")
    if per_piece is None or per_piece.isna().all():
        # fallback: assume uniform split across pieces
        df["Weight Per Piece"] = df["Ready Weight"] / \
            df["RPcs"].replace(0, pd.NA)

    # Sort by priority and then by zone/route/location to enhance grouping
    df["priorityBucket"] = df.apply(build_priority_bucket, axis=1)
    priority_order = {"Late": 0, "NearDue": 1, "WithinWindow": 2, "NotDue": 3}
    df["priorityRank"] = df["priorityBucket"].map(priority_order).fillna(2)

    # Build sort columns based on available data
    sort_cols = ["priorityRank"]
    if "Zone" in df.columns:
        sort_cols.append("Zone")
    if "Route" in df.columns:
        sort_cols.append("Route")
    sort_cols.extend(["Customer", "shipping_state", "shipping_city"])

    df = df.sort_values(sort_cols).reset_index(drop=True)

    truck_rows = []
    assignment_rows = []
    truck_counter = 0

    # Build grouping columns - include Customer to keep customers separate
    grouping_cols = []
    if "Zone" in df.columns:
        grouping_cols.append("Zone")
    if "Route" in df.columns:
        grouping_cols.append("Route")
    grouping_cols.extend(["Customer", "shipping_state", "shipping_city"])

    # Group by zone/route/customer/destination (one customer per truck)
    for group_key, group in df.groupby(grouping_cols, dropna=False):
        group = group.reset_index(drop=True)
        if group.empty:
            continue

        # Extract values from first row
        customer = group["Customer"].iloc[0]
        state = group["shipping_state"].iloc[0]
        city = group["shipping_city"].iloc[0]
        zone_val = group["Zone"].iloc[0] if "Zone" in group.columns else None
        route_val = group["Route"].iloc[0] if "Route" in group.columns else None

        max_weight = weight_config["texas_max_lbs"] if is_texas(
            str(state)) else weight_config["other_max_lbs"]
        min_weight = weight_config["texas_min_lbs"] if is_texas(
            str(state)) else weight_config["other_min_lbs"]

        current_weight = 0.0
        current_pieces = 0
        current_orders = set()
        current_lines = 0
        max_width = 0.0
        contains_late = False
        has_near_due = False
        pending_assignments = []
        # Track the earliest "Earliest Due" seen on the current truck to gate mixing with Late
        truck_earliest_due = None

        def finalize_truck():
            nonlocal truck_counter, current_weight, current_pieces, current_lines, current_orders, max_width, contains_late, has_near_due, pending_assignments, truck_earliest_due
            if current_weight == 0:
                return
            truck_counter += 1
            overwidth_weight = sum(
                a["totalWeight"] for a in pending_assignments if a["isOverwidth"]) if pending_assignments else 0.0
            percent_overwidth = float(
                overwidth_weight / current_weight * 100.0) if current_weight > 0 else 0.0

            # Determine worst-case priority for the truck
            if contains_late:
                priority_bucket = "Late"
            elif has_near_due:
                priority_bucket = "NearDue"
            else:
                priority_bucket = "WithinWindow"

            truck_rows.append({
                "truckNumber": truck_counter,
                "customerName": str(customer),
                "customerAddress": group["shipping_address_1"].iloc[0] if "shipping_address_1" in group.columns and not group.empty else None,
                "customerCity": str(city),
                "customerState": str(state),
                "zone": None if pd.isna(zone_val) else str(zone_val),
                "route": None if pd.isna(route_val) else str(route_val),
                "totalWeight": float(current_weight),
                "minWeight": int(min_weight),
                "maxWeight": int(max_weight),
                "totalOrders": int(len(current_orders)),
                "totalLines": int(current_lines),
                "totalPieces": int(current_pieces),
                "maxWidth": float(max_width),
                "percentOverwidth": float(percent_overwidth),
                "containsLate": bool(contains_late),
                "priorityBucket": priority_bucket,
            })
            for a in pending_assignments:
                a = a.copy()
                a["truckNumber"] = truck_counter
                assignment_rows.append(a)
            # reset
            current_weight = 0.0
            current_pieces = 0
            current_orders = set()
            current_lines = 0
            max_width = 0.0
            contains_late = False
            has_near_due = False
            pending_assignments = []
            truck_earliest_due = None

        # Track remainders that need to be processed
        pending_remainders = []

        # Normalize today's date (UTC midnight) once (per group)
        today_utc = pd.Timestamp.now(tz="UTC").normalize()

        for _, row in group.iterrows():
            pieces = int(row.get("RPcs") or 0)
            if pieces <= 0:
                continue

            width = float(row.get("Width") or 0.0)
            weight_per_piece = float(row.get("Weight Per Piece") or 0.0)
            line_total_weight = float(row.get("Ready Weight") or 0.0)
            line_is_overwidth = bool(width > 96)
            line_is_late = bool(row.get("Is Late", False))
            row_bucket = str(row.get("priorityBucket", "WithinWindow"))
            if row_bucket == "NearDue":
                has_near_due = True

            # Parse earliest due for mixing rules
            row_earliest_due = None
            try:
                _ed = row.get("Earliest Due")
                if pd.notna(_ed):
                    row_earliest_due = pd.to_datetime(_ed, errors="coerce", utc=True)
            except Exception:
                row_earliest_due = None

            # --- Late mixing rule during INITIAL packing ---
            # Requirement: Late orders can only be combined with orders already within the shipping window
            # (today >= Earliest Due). Enforce both directions before placing weight:
            # 1) If current truck already contains any Late and incoming row is NOT Late,
            #    only allow if row_earliest_due <= today. Otherwise, finalize and start new truck.
            if (not line_is_late) and contains_late and current_weight > 0:
                if (row_earliest_due is None) or (pd.notna(row_earliest_due) and row_earliest_due > today_utc):
                    finalize_truck()

            # 2) If incoming row IS Late and current truck has non-late items whose earliest ship date is in future
            #    (truck_earliest_due > today), then finalize first before placing the Late row.
            if line_is_late and current_weight > 0 and not contains_late:
                if (truck_earliest_due is not None) and pd.notna(truck_earliest_due) and truck_earliest_due > today_utc:
                    finalize_truck()

            # If the full line won't fit, split by pieces
            needed_weight = line_total_weight
            available_capacity = max_weight - current_weight
            if needed_weight <= available_capacity:
                take_pieces = pieces
            else:
                take_pieces = int(
                    available_capacity // weight_per_piece) if weight_per_piece > 0 else 0

            if take_pieces == 0 and current_weight > 0:
                # finalize current truck and try again
                finalize_truck()
                available_capacity = max_weight - current_weight
                take_pieces = int(min(pieces, available_capacity //
                                  weight_per_piece)) if weight_per_piece > 0 else pieces

            take_pieces = max(0, min(pieces, take_pieces))
            if take_pieces == 0:
                continue

            taken_weight = take_pieces * weight_per_piece
            current_weight += taken_weight
            current_pieces += take_pieces
            current_lines += 1
            current_orders.add(str(row.get("SO")))
            max_width = max(max_width, width)
            contains_late = contains_late or line_is_late

            # Update truck's earliest Earliest Due (for future mixing decisions)
            if row_earliest_due is not None and pd.notna(row_earliest_due):
                if (truck_earliest_due is None) or (row_earliest_due < truck_earliest_due):
                    truck_earliest_due = row_earliest_due

            # Safely serialize due dates
            _earliest = row.get("Earliest Due")
            _latest = row.get("Latest Due")
            earliest_serial = _earliest.isoformat() if isinstance(_earliest, pd.Timestamp) and pd.notna(_earliest) else None
            latest_serial = _latest.isoformat() if isinstance(_latest, pd.Timestamp) and pd.notna(_latest) else None

            pending_assignments.append({
                "so": str(row.get("SO")),
                "line": str(row.get("Line")),
                # Pass through transport/load identifier from original source, normalized
                "trttav_no": (str(row.get(trttav_src)) if trttav_src and trttav_src in row.index else None),
                "customerName": str(row.get("Customer")),
                "customerAddress": row.get("shipping_address_1"),
                "customerCity": str(row.get("shipping_city")),
                "customerState": str(row.get("shipping_state")),
                "zone": None if pd.isna(zone_val) else str(zone_val),
                "route": None if pd.isna(route_val) else str(route_val),
                "piecesOnTransport": int(take_pieces),
                "totalReadyPieces": int(pieces),
                "weightPerPiece": float(weight_per_piece),
                "totalWeight": float(taken_weight),
                "width": float(width),
                "isOverwidth": bool(line_is_overwidth),
                "isLate": bool(line_is_late),
                "priorityBucket": str(row_bucket),
                "earliestDue": earliest_serial,
                "latestDue": latest_serial,
                "isPartial": bool(take_pieces < pieces),
                "remainingPieces": int(pieces - take_pieces) if take_pieces < pieces else 0,
                "isRemainder": False,
                "parentLine": None,
            })

            # **CRITICAL: Track remainder if line was split**
            remainder_pieces = pieces - take_pieces
            if remainder_pieces > 0:
                remainder_weight = remainder_pieces * weight_per_piece
                # Create remainder row for processing
                remainder_row = row.copy()
                remainder_row["RPcs"] = remainder_pieces
                remainder_row["Ready Weight"] = remainder_weight
                # Mark as remainder for tracking
                remainder_row["_is_remainder"] = True
                remainder_row["_parent_line"] = f"{row.get('SO')}-{row.get('Line')}"
                pending_remainders.append(remainder_row)

            # If we hit/exceed the max, finalize
            if current_weight >= max_weight * 0.98:  # small buffer
                finalize_truck()

        # **PROCESS ALL REMAINDERS** - Critical step that was missing!
        # Process remainders iteratively to avoid infinite recursion
        max_remainder_iterations = 100  # Safety limit
        iteration_count = 0

        while pending_remainders and iteration_count < max_remainder_iterations:
            iteration_count += 1
            current_remainders = pending_remainders.copy()
            pending_remainders = []  # Clear for next iteration
            
            # Sort remainders by priority (Late first) to ensure they get allocated
            remainder_df = pd.DataFrame(current_remainders)
            if "priorityBucket" in remainder_df.columns:
                priority_order = {"Late": 0, "NearDue": 1, "WithinWindow": 2, "NotDue": 3}
                remainder_df["priorityRank"] = remainder_df["priorityBucket"].map(priority_order).fillna(2)
                remainder_df = remainder_df.sort_values("priorityRank").reset_index(drop=True)
            
            # Process remainders
            for _, remainder_row in remainder_df.iterrows():
                pieces = int(remainder_row.get("RPcs") or 0)
                if pieces <= 0:
                    continue

                width = float(remainder_row.get("Width") or 0.0)
                weight_per_piece = float(remainder_row.get("Weight Per Piece") or 0.0)
                line_total_weight = float(remainder_row.get("Ready Weight") or 0.0)
                line_is_overwidth = bool(width > 96)
                line_is_late = bool(remainder_row.get("Is Late", False))
                row_bucket = str(remainder_row.get("priorityBucket", "WithinWindow"))
                if row_bucket == "NearDue":
                    has_near_due = True

                # Parse earliest due for mixing rules
                rem_earliest_due = None
                try:
                    _ed = remainder_row.get("Earliest Due")
                    if pd.notna(_ed):
                        rem_earliest_due = pd.to_datetime(_ed, errors="coerce", utc=True)
                except Exception:
                    rem_earliest_due = None

                # Apply the same Late mixing rules during remainder placement
                if (not line_is_late) and contains_late and current_weight > 0:
                    if (rem_earliest_due is None) or (pd.notna(rem_earliest_due) and rem_earliest_due > today_utc):
                        finalize_truck()
                        # After finalizing, we're starting a new truck context
                if line_is_late and current_weight > 0 and not contains_late:
                    if (truck_earliest_due is not None) and pd.notna(truck_earliest_due) and truck_earliest_due > today_utc:
                        finalize_truck()

                # Check if remainder fits in current truck
                needed_weight = line_total_weight
                available_capacity = max_weight - current_weight
                if needed_weight <= available_capacity:
                    take_pieces = pieces
                else:
                    # Start new truck for remainder if current truck has items
                    if current_weight > 0:
                        finalize_truck()
                        available_capacity = max_weight - current_weight
                    take_pieces = min(pieces, int(available_capacity // weight_per_piece)) if weight_per_piece > 0 else pieces

                take_pieces = max(0, min(pieces, take_pieces))
                if take_pieces == 0:
                    continue

                taken_weight = take_pieces * weight_per_piece
                current_weight += taken_weight
                current_pieces += take_pieces
                current_lines += 1
                current_orders.add(str(remainder_row.get("SO")))
                max_width = max(max_width, width)
                contains_late = contains_late or line_is_late

                # Safely serialize due dates
                _earliest = remainder_row.get("Earliest Due")
                _latest = remainder_row.get("Latest Due")
                earliest_serial = _earliest.isoformat() if isinstance(_earliest, pd.Timestamp) and pd.notna(_earliest) else None
                latest_serial = _latest.isoformat() if isinstance(_latest, pd.Timestamp) and pd.notna(_latest) else None

                pending_assignments.append({
                    "so": str(remainder_row.get("SO")),
                    "line": f"{remainder_row.get('Line')}-R{iteration_count}",  # Mark as remainder with iteration
                    "trttav_no": (str(remainder_row.get(trttav_src)) if trttav_src and trttav_src in remainder_row.index else None),
                    "customerName": str(remainder_row.get("Customer")),
                    "customerAddress": remainder_row.get("shipping_address_1"),
                    "customerCity": str(remainder_row.get("shipping_city")),
                    "customerState": str(remainder_row.get("shipping_state")),
                    "zone": None if pd.isna(zone_val) else str(zone_val),
                    "route": None if pd.isna(route_val) else str(route_val),
                    "piecesOnTransport": int(take_pieces),
                    "totalReadyPieces": int(pieces),
                    "weightPerPiece": float(weight_per_piece),
                    "totalWeight": float(taken_weight),
                    "width": float(width),
                    "isOverwidth": bool(line_is_overwidth),
                    "isLate": bool(line_is_late),
                    "priorityBucket": str(row_bucket),
                    "earliestDue": earliest_serial,
                    "latestDue": latest_serial,
                    "isPartial": bool(take_pieces < pieces),
                    "remainingPieces": int(pieces - take_pieces) if take_pieces < pieces else 0,
                    "isRemainder": True,
                    "parentLine": remainder_row.get("_parent_line", ""),
                })

                # Update truck's earliest Earliest Due (for future mixing decisions)
                if rem_earliest_due is not None and pd.notna(rem_earliest_due):
                    if (truck_earliest_due is None) or (rem_earliest_due < truck_earliest_due):
                        truck_earliest_due = rem_earliest_due

                # **Handle remaining pieces for next iteration**
                remainder_pieces = pieces - take_pieces
                if remainder_pieces > 0:
                    remainder_weight = remainder_pieces * weight_per_piece
                    # Create another remainder for next iteration
                    next_remainder = remainder_row.copy()
                    next_remainder["RPcs"] = remainder_pieces
                    next_remainder["Ready Weight"] = remainder_weight
                    pending_remainders.append(next_remainder)

                # If we hit/exceed the max, finalize
                if current_weight >= max_weight * 0.98:  # small buffer
                    finalize_truck()

        # finalize remaining for this group
        finalize_truck()

    trucks_df = pd.DataFrame(truck_rows)
    assigns_df = pd.DataFrame(assignment_rows)

    # --- Cross-bucket fill step ---
    # Top off Late trucks using NearDue/WithinWindow; then NearDue using WithinWindow.
    # Constraints: Planning Whse already filtered upstream; require exact match on
    # Zone, Route, Customer, City, State (i.e., trucks with identical summary context).
    # Respect maxWeight and do not split assignment fragments further.
    def _truck_group_key(trow: pd.Series) -> tuple:
        return (
            (None if pd.isna(trow.get("zone")) else str(trow.get("zone"))),
            (None if pd.isna(trow.get("route")) else str(trow.get("route"))),
            str(trow.get("customerName")),
            str(trow.get("customerState")),
            str(trow.get("customerCity")),
        )

    if not trucks_df.empty and not assigns_df.empty:
        def _to_int_or_none(v: Any) -> Optional[int]:
            try:
                if v is None or (hasattr(pd, 'isna') and pd.isna(v)):
                    return None
                return int(v)
            except Exception:
                try:
                    return int(float(v))
                except Exception:
                    try:
                        s = str(v)
                        return int(s)
                    except Exception:
                        return None
        # Map truck -> group key
        trucks_df = trucks_df.copy()
        assigns_df = assigns_df.copy()

        # Ensure expected columns
        if "priorityBucket" not in assigns_df.columns:
            # Derive from isLate when missing
            if "isLate" in assigns_df.columns:
                assigns_df["priorityBucket"] = assigns_df["isLate"].map(lambda x: "Late" if bool(x) else "WithinWindow")
            else:
                assigns_df["priorityBucket"] = "WithinWindow"

        # Build quick access
        def rebuild_truck_summaries(from_assigns: pd.DataFrame) -> pd.DataFrame:
            if from_assigns.empty:
                return pd.DataFrame(columns=list(trucks_df.columns))
            # Aggregate by truckNumber
            agg = []
            for tnum, g in from_assigns.groupby("truckNumber"):
                tnum_i = _to_int_or_none(tnum)
                if tnum_i is None:
                    continue
                # Get meta from any original truck row if available
                base = trucks_df[trucks_df["truckNumber"] == tnum_i]
                if base.empty:
                    # construct minimal via first row of assignments
                    any_row = g.iloc[0]
                    zone_val = None
                    route_val = None
                    customer = str(any_row.get("customerName"))
                    city = str(any_row.get("customerCity"))
                    state = str(any_row.get("customerState"))
                else:
                    brow = base.iloc[0]
                    zone_val = None if pd.isna(brow.get("zone")) else str(brow.get("zone"))
                    route_val = None if pd.isna(brow.get("route")) else str(brow.get("route"))
                    customer = str(brow.get("customerName"))
                    city = str(brow.get("customerCity"))
                    state = str(brow.get("customerState"))

                is_tx = is_texas(state)
                max_weight = weight_config["texas_max_lbs"] if is_tx else weight_config["other_max_lbs"]
                min_weight = weight_config["texas_min_lbs"] if is_tx else weight_config["other_min_lbs"]
                total_weight = float(g["totalWeight"].sum())
                total_pieces = int(g["piecesOnTransport"].sum()) if "piecesOnTransport" in g.columns else int(len(g))
                total_lines = int(g.shape[0])
                total_orders = int(g["so"].nunique()) if "so" in g.columns else total_lines
                max_width = float(g["width"].max()) if "width" in g.columns and not g.empty else 0.0
                contains_late = bool((g.get("isLate") == True).any()) if "isLate" in g.columns else False
                # Determine truck bucket by assignment priority buckets
                priority_bucket = "WithinWindow"
                if "priorityBucket" in g.columns:
                    vals = g["priorityBucket"].dropna().astype(str).tolist()
                    if any(v == "Late" for v in vals):
                        priority_bucket = "Late"
                    elif any(v == "NearDue" for v in vals):
                        priority_bucket = "NearDue"

                agg.append({
                    "truckNumber": int(tnum_i),
                    "customerName": customer,
                    "customerAddress": None,
                    "customerCity": city,
                    "customerState": state,
                    "zone": zone_val,
                    "route": route_val,
                    "totalWeight": float(total_weight),
                    "minWeight": int(min_weight),
                    "maxWeight": int(max_weight),
                    "totalOrders": int(total_orders),
                    "totalLines": int(total_lines),
                    "totalPieces": int(total_pieces),
                    "maxWidth": float(max_width),
                    "percentOverwidth": float(0.0),
                    "containsLate": bool(contains_late),
                    "priorityBucket": str(priority_bucket),
                })
            return pd.DataFrame(agg)

        # Helper to run a single fill pass: fill_buckets is target list, donor_buckets are allowed donors
        def fill_pass(target_buckets: set, donor_buckets: set):
            nonlocal assigns_df, trucks_df
            # Recompute summary each pass for up-to-date weights
            trucks_local = rebuild_truck_summaries(assigns_df)
            if trucks_local.empty:
                return
            # Build group -> trucks within
            groups: Dict[tuple, Dict[str, List[int]]] = defaultdict(lambda: {"targets": [], "donors": []})
            for _, trow in trucks_local.iterrows():
                tnum = int(trow["truckNumber"]) if pd.notna(trow.get("truckNumber")) else None
                if tnum is None:
                    continue
                gk = _truck_group_key(trow)
                bucket = str(trow.get("priorityBucket", "WithinWindow"))
                if bucket in target_buckets:
                    groups[gk]["targets"].append(tnum)
                if bucket in donor_buckets:
                    groups[gk]["donors"].append(tnum)

            # For each group, try to move assignment rows from donors to targets
            for gk, d in groups.items():
                targets = d["targets"]
                donors = d["donors"]
                if not targets or not donors:
                    continue
                # Work on local views to avoid repeated filtering
                for t_truck in targets:
                    # Get latest summary for target
                    t_summary = rebuild_truck_summaries(assigns_df)
                    t_row = t_summary[t_summary["truckNumber"] == t_truck]
                    if t_row.empty:
                        continue
                    t_row = t_row.iloc[0]
                    t_weight = float(t_row.get("totalWeight") or 0.0)
                    t_min = float(t_row.get("minWeight") or 0.0)
                    t_max = float(t_row.get("maxWeight") or 0.0)
                    if t_weight >= t_min or t_weight >= t_max * 0.98:
                        continue
                    # Iterate donors; prefer donors with same group and lower priority bucket first
                    for d_truck in list(donors):
                        if d_truck == t_truck:
                            continue
                        # Candidate rows from donor matching this exact group key
                        zone_key, route_key, cust_key, state_key, city_key = gk
                        cand = assigns_df[(assigns_df["truckNumber"] == d_truck)]
                        # Ensure zone/route columns exist on assignments
                        if "zone" not in cand.columns:
                            cand["zone"] = None
                        if "route" not in cand.columns:
                            cand["route"] = None
                        # Build boolean mask for exact match (with None handling)
                        def _eq_or_none(series, key):
                            if key is None:
                                return series.isna() | (series.astype(object) == None)  # noqa: E711
                            return series.astype(str) == str(key)
                        mask = (
                            _eq_or_none(cand["zone"], zone_key)
                            & _eq_or_none(cand["route"], route_key)
                            & (cand["customerName"].astype(str) == str(cust_key))
                            & (cand["customerState"].astype(str) == str(state_key))
                            & (cand["customerCity"].astype(str) == str(city_key))
                        )
                        cand = cand[mask]
                        if cand.empty:
                            continue
                        # Move rows one by one while capacity allows
                        moved_any = False
                        for ridx, arow in cand.iterrows():
                            w = float(arow.get("totalWeight") or 0.0)
                            if w <= 0:
                                continue
                            
                            # If target is a Late truck, do not move assignments whose earliestDue is after today.
                            # (Business rule: a Late truck must not contain items whose earliest ship date is later than today.)
                            if "Late" in target_buckets:
                                earliest_due = arow.get("earliestDue")
                                if earliest_due is not None:
                                    try:
                                        # Parse the earliest due date into a Timestamp
                                        earliest_due_date = pd.to_datetime(earliest_due, errors="coerce")
                                        # Use today's date (normalized) as the cutoff. If earliestDue is strictly after today,
                                        # skip moving this assignment into a Late truck.
                                        today = pd.Timestamp.now().normalize()
                                        if pd.notna(earliest_due_date) and earliest_due_date > today:
                                            continue
                                    except Exception:
                                        # If we can't parse the date, allow the assignment to proceed (safe fallback)
                                        pass
                            
                            if (t_weight + w) <= (t_max * 1.0001):
                                # Reassign
                                assigns_df.at[ridx, "truckNumber"] = t_truck
                                t_weight += w
                                moved_any = True
                                # Stop if we reached min weight or close to max
                                if t_weight >= t_min or t_weight >= t_max * 0.98:
                                    break
                        # Remove donor from list if emptied
                        rem_count = assigns_df[assigns_df["truckNumber"] == d_truck].shape[0]
                        if rem_count == 0:
                            try:
                                donors.remove(d_truck)
                            except ValueError:
                                pass
                        if t_weight >= t_min or t_weight >= t_max * 0.98:
                            break

        # Pass 1: Late <- NearDue or WithinWindow
        fill_pass(target_buckets={"Late"}, donor_buckets={"NearDue", "WithinWindow"})
        # Pass 2: NearDue <- WithinWindow
        fill_pass(target_buckets={"NearDue"}, donor_buckets={"WithinWindow"})

        # Rebuild final summaries after reassignment
        trucks_df = rebuild_truck_summaries(assigns_df)

    return trucks_df, assigns_df
