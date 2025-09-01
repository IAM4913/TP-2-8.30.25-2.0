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

        def finalize_truck():
            nonlocal truck_counter, current_weight, current_pieces, current_lines, current_orders, max_width, contains_late, has_near_due, pending_assignments
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

            # Safely serialize due dates
            _earliest = row.get("Earliest Due")
            _latest = row.get("Latest Due")
            earliest_serial = _earliest.isoformat() if isinstance(_earliest, pd.Timestamp) and pd.notna(_earliest) else None
            latest_serial = _latest.isoformat() if isinstance(_latest, pd.Timestamp) and pd.notna(_latest) else None

            pending_assignments.append({
                "so": str(row.get("SO")),
                "line": str(row.get("Line")),
                "customerName": str(row.get("Customer")),
                "customerAddress": row.get("shipping_address_1"),
                "customerCity": str(row.get("shipping_city")),
                "customerState": str(row.get("shipping_state")),
                "piecesOnTransport": int(take_pieces),
                "totalReadyPieces": int(pieces),
                "weightPerPiece": float(weight_per_piece),
                "totalWeight": float(taken_weight),
                "width": float(width),
                "isOverwidth": bool(line_is_overwidth),
                "isLate": bool(line_is_late),
                "earliestDue": earliest_serial,
                "latestDue": latest_serial,
            })

            # If we hit/exceed the max, finalize
            if current_weight >= max_weight * 0.98:  # small buffer
                finalize_truck()

        # finalize remaining for this group
        finalize_truck()

    trucks_df = pd.DataFrame(truck_rows)
    assigns_df = pd.DataFrame(assignment_rows)
    return trucks_df, assigns_df
