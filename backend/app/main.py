from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, cast
import datetime as _dt
import pandas as pd
from io import BytesIO
import re
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter
from .schemas import (
    UploadPreviewResponse,
    OptimizeRequest,
    OptimizeResponse,
    TruckSummary,
    LineAssignment,
    CombineTrucksRequest,
    CombineTrucksResponse,
)
from .excel_utils import compute_calculated_fields, _find_planning_whse_col, filter_by_planning_whse
from .optimizer_simple import naive_grouping, NO_MULTI_STOP_CUSTOMERS


REQUIRED_COLUMNS_MAPPED: List[str] = [
    "SO",  # Sales Order Number
    "Line",  # Line Number
    "Customer",  # Customer Name
    "shipping_city",  # Shipping City
    "shipping_state",  # Shipping State
    "Ready Weight",  # Ready Weight (lbs)
    "RPcs",  # Ready Pieces (quantity)
    "Grd",  # Material Grade
    "Size",  # Material Thickness (Size)
    "Width",  # Material Width
    "Earliest Due",  # Earliest Due Date
    "Latest Due",  # Latest Due Date
]


app = FastAPI(title="Truck Planner Backend", version="0.1.0")

# Enable CORS for local development UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload/preview", response_model=UploadPreviewResponse)
async def upload_preview(file: UploadFile = File(...)) -> UploadPreviewResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")

    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        # Read with openpyxl engine for .xlsx
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Normalize headers by exact names as in the source file (no strip/rename yet)
    headers: List[str] = list(map(str, df.columns.tolist()))

    missing = [col for col in REQUIRED_COLUMNS_MAPPED if col not in headers]

    # Provide a small sample for UI validation
    sample_records = df.head(5).to_dict(orient="records") if not df.empty else []

    # Normalize sample keys to strings
    norm_sample: List[Dict[str, Any]] = []
    for rec in sample_records:
        norm_sample.append({str(k): v for k, v in rec.items()})

    return UploadPreviewResponse(
        headers=headers,
        rowCount=int(df.shape[0]),
        missingRequiredColumns=missing,
        sample=norm_sample,
    )


@app.post("/optimize", response_model=OptimizeResponse)
async def optimize(
    file: UploadFile = File(...),
    planningWhse: Optional[str] = Form("ZAC"),
) -> OptimizeResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")
    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Filter to Planning Whse first (defaults to ZAC); if column not present, no-op
    if planningWhse:
        try:
            df = filter_by_planning_whse(df, allowed_values=(planningWhse,))
        except Exception:
            # If anything goes wrong, fall back to unfiltered to avoid blocking
            pass

    df = compute_calculated_fields(df)

    # Use default weight config for now - we'll add form parameter support later
    cfg = {
        "texas_max_lbs": 52000,
        "texas_min_lbs": 47000,
        "other_max_lbs": 48000,
        "other_min_lbs": 44000,
    }

    try:
        print(f"DataFrame shape: {df.shape}")
        print(f"Available columns: {list(df.columns)}")
        print(f"Weight config: {cfg}")
        trucks_df, assigns_df = naive_grouping(df, cfg)
        print(
            f"Optimization successful: {len(trucks_df)} trucks, {len(assigns_df)} assignments")
    except Exception as exc:  # noqa: BLE001
        print(f"Optimization error: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=400, detail=f"Optimization failed: {exc}") from exc

    # Build sections mapping
    sections: Dict[str, List[int]] = {}
    if not trucks_df.empty:
        for bucket, g in trucks_df.groupby("priorityBucket"):
            sections[str(bucket)] = list(map(int, g["truckNumber"].tolist()))

    trucks_list = trucks_df.to_dict(orient="records") if not trucks_df.empty else []
    assigns_list = assigns_df.to_dict(orient="records") if not assigns_df.empty else []
    # Ensure JSON-serializable keys and create typed models
    trucks_models: List[TruckSummary] = [TruckSummary(**{str(k): v for k, v in t.items()}) for t in trucks_list]
    assigns_models: List[LineAssignment] = [LineAssignment(**{str(k): v for k, v in a.items()}) for a in assigns_list]

    return OptimizeResponse(
        trucks=trucks_models,
        assignments=assigns_models,
        sections=sections,
    )


@app.post("/export/trucks")
async def export_trucks(
    file: UploadFile = File(...),
    planningWhse: Optional[str] = Form("ZAC"),
) -> StreamingResponse:
    """Export optimized truck assignments to Excel format"""
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")

    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Apply Planning Whse filter first (default ZAC); if missing column, no-op
    if planningWhse:
        try:
            df = filter_by_planning_whse(df, allowed_values=(planningWhse,))
        except Exception:
            pass
    df = compute_calculated_fields(df)
    cfg = {
        "texas_max_lbs": 52000,
        "texas_min_lbs": 47000,
        "other_max_lbs": 48000,
        "other_min_lbs": 44000,
    }

    try:
        trucks_df, assigns_df = naive_grouping(df, cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Optimization failed: {exc}") from exc

    # Create Excel output with multiple sheets
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not trucks_df.empty:
            trucks_df.to_excel(writer, sheet_name="Truck Summary", index=False)
        if not assigns_df.empty:
            assigns_df.to_excel(
                writer, sheet_name="Order Details", index=False)

    output.seek(0)

    return StreamingResponse(
        BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=truck_optimization_results.xlsx"}
    )


@app.get("/no-multi-stop-customers")
def get_no_multi_stop_customers() -> Dict[str, List[str]]:
    """Get list of customers that cannot be combined with others"""
    return {"customers": NO_MULTI_STOP_CUSTOMERS}


@app.post("/no-multi-stop-customers")
def update_no_multi_stop_customers(customers: List[str]) -> Dict[str, str]:
    """Update list of customers that cannot be combined with others"""
    global NO_MULTI_STOP_CUSTOMERS
    # Note: This is temporary - in production this should be stored in a database
    NO_MULTI_STOP_CUSTOMERS.clear()
    NO_MULTI_STOP_CUSTOMERS.extend(customers)
    return {"message": f"Updated no-multi-stop list with {len(customers)} customers"}


@app.post("/combine-trucks", response_model=CombineTrucksResponse)
async def combine_trucks(
    file: UploadFile = File(...),
    request: str = Form(...),
    planningWhse: Optional[str] = Form(None),
) -> CombineTrucksResponse:
    """Combine selected lines into a single truck.

    Notes:
    - Stateless: recomputes trucks/assignments from the uploaded file.
    - Matches selected lines by (SO, Line) ignoring the client-side truck numbers to avoid numbering drift.
    - Chooses the lightest truck among those containing the selected lines as the target truck.
    """
    # Parse request payload
    try:
        req = CombineTrucksRequest.model_validate_json(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid request: {exc}") from exc

    # Load Excel
    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Compute fields and optimize (deterministic grouping)
    # Optional: filter to Planning Whse to align with UI selection
    if planningWhse:
        try:
            df = filter_by_planning_whse(df, allowed_values=(planningWhse,))
        except Exception:
            pass
    df = compute_calculated_fields(df)
    cfg = {
        "texas_max_lbs": req.weightConfig.texas_max_lbs,
        "texas_min_lbs": req.weightConfig.texas_min_lbs,
        "other_max_lbs": req.weightConfig.other_max_lbs,
        "other_min_lbs": req.weightConfig.other_min_lbs,
    }
    try:
        trucks_df, assigns_df = naive_grouping(df.copy(), cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Optimization failed: {exc}") from exc

    if trucks_df.empty or assigns_df.empty:
        return CombineTrucksResponse(success=False, message="No trucks or assignments to combine", updatedAssignments=[], removedTruckIds=[])

    # Parse selected lines: id format "truckNumber-SO-Line"
    sel_pairs: List[tuple[str, str]] = []
    for lid in req.lineIds:
        parts = str(lid).split("-")
        if len(parts) < 3:
            continue
        _, so, line = parts[-3], parts[-2], parts[-1]
        sel_pairs.append((str(so), str(line)))
    if not sel_pairs:
        return CombineTrucksResponse(success=False, message="No valid line IDs provided", updatedAssignments=[], removedTruckIds=[])

    # Find matching assignment rows
    def as_str(s: Any) -> str:
        return str(s)

    assigns_df = assigns_df.copy()
    assigns_df["__so_key__"] = assigns_df["so"].map(as_str)
    assigns_df["__line_key__"] = assigns_df["line"].map(as_str)
    mask_selected = assigns_df.apply(lambda r: (r["__so_key__"], r["__line_key__"]) in sel_pairs, axis=1)
    selected_rows = assigns_df[mask_selected]
    if selected_rows.empty:
        return CombineTrucksResponse(success=False, message="Selected lines not found in current optimization", updatedAssignments=[], removedTruckIds=[])

    # Determine candidate trucks and target (lightest among involved)
    involved_trucks = sorted(set(int(t) for t in selected_rows["truckNumber"].tolist()))
    trucks_sub = trucks_df[trucks_df["truckNumber"].isin(involved_trucks)]
    if trucks_sub.empty:
        return CombineTrucksResponse(success=False, message="Candidate trucks not found", updatedAssignments=[], removedTruckIds=[])
    target_row = trucks_sub.sort_values("totalWeight").iloc[0]
    target_truck = int(target_row["truckNumber"])  # lightest

    # Compute total selected weight and validate against target's max
    total_selected_weight = float(selected_rows["totalWeight"].sum())
    target_max = float(target_row.get("maxWeight") or 0.0)
    if target_max > 0 and (float(target_row.get("totalWeight") or 0.0) + total_selected_weight) > target_max * 1.0001:
        return CombineTrucksResponse(success=False, message="Combination exceeds target truck max weight", updatedAssignments=[], removedTruckIds=[])

    # Reassign selected lines to target
    source_trucks_before = set(involved_trucks)
    assigns_df.loc[mask_selected, "truckNumber"] = target_truck

    # Determine removed trucks (those that had only selected lines)
    remaining_by_truck = assigns_df.groupby("truckNumber").size()
    removed = [t for t in source_trucks_before if t != target_truck and t not in remaining_by_truck.index.tolist()]

    # Recompute target truck summary from its assignments
    t_assigns = assigns_df[assigns_df["truckNumber"] == target_truck].copy()
    # Determine state and limits from any row
    any_state = str(t_assigns["customerState"].iloc[0]) if not t_assigns.empty else ""
    is_texas = str(any_state).strip().upper() in {"TX", "TEXAS"}
    max_weight = cfg["texas_max_lbs"] if is_texas else cfg["other_max_lbs"]
    min_weight = cfg["texas_min_lbs"] if is_texas else cfg["other_min_lbs"]
    total_weight = float(t_assigns["totalWeight"].sum())
    total_pieces = int(t_assigns["piecesOnTransport"].sum())
    total_lines = int(t_assigns.shape[0])
    total_orders = int(t_assigns["so"].nunique())
    max_width = float(t_assigns["width"].max()) if not t_assigns.empty else 0.0
    contains_late = bool(t_assigns["isLate"].any()) if "isLate" in t_assigns.columns else False
    priority_bucket = "Late" if contains_late else "WithinWindow"
    # Use first destination/customer for summary context
    customer_name = str(t_assigns["customerName"].iloc[0]) if not t_assigns.empty else ""
    customer_city = str(t_assigns["customerCity"].iloc[0]) if not t_assigns.empty else ""
    customer_state = any_state
    zone_val = None
    route_val = None

    new_truck_summary = TruckSummary(
        truckNumber=target_truck,
        customerName=customer_name,
        customerAddress=None,
        customerCity=customer_city,
        customerState=customer_state,
        zone=zone_val,
        route=route_val,
        totalWeight=float(total_weight),
        minWeight=int(min_weight),
        maxWeight=int(max_weight),
        totalOrders=int(total_orders),
        totalLines=int(total_lines),
        totalPieces=int(total_pieces),
        maxWidth=float(max_width),
        percentOverwidth=float(0.0),
        containsLate=bool(contains_late),
        priorityBucket=str(priority_bucket),
    )

    # Build updated assignments for changed trucks only
    changed_trucks = set(source_trucks_before) | {target_truck}
    updated_assignments_rows = assigns_df[assigns_df["truckNumber"].isin(list(changed_trucks))]
    updated_assignments: List[LineAssignment] = []
    for _, a in updated_assignments_rows.iterrows():
        tnum_val = a.get("truckNumber")
        try:
            tnum_int = int(tnum_val) if pd.notna(tnum_val) else target_truck
        except Exception:
            tnum_int = target_truck
        updated_assignments.append(LineAssignment(
            truckNumber=tnum_int,
            so=str(a.get("so")),
            line=str(a.get("line")),
            customerName=str(a.get("customerName")),
            customerAddress=a.get("customerAddress"),
            customerCity=str(a.get("customerCity")),
            customerState=str(a.get("customerState")),
            piecesOnTransport=int(a.get("piecesOnTransport") or 0),
            totalReadyPieces=int(a.get("totalReadyPieces") or 0),
            weightPerPiece=float(a.get("weightPerPiece") or 0.0),
            totalWeight=float(a.get("totalWeight") or 0.0),
            width=float(a.get("width") or 0.0),
            isOverwidth=bool(a.get("isOverwidth", False)),
            isLate=bool(a.get("isLate", False)),
            earliestDue=str(a.get("earliestDue")) if pd.notna(a.get("earliestDue")) else None,
            latestDue=str(a.get("latestDue")) if pd.notna(a.get("latestDue")) else None,
        ))

    return CombineTrucksResponse(
        success=True,
        message=f"Combined {len(selected_rows)} lines into truck {target_truck}",
        newTruck=new_truck_summary,
        updatedAssignments=updated_assignments,
        removedTruckIds=[int(i) for i in removed],
    )


@app.post("/export/dh-load-list")
async def export_dh_load_list(
    file: UploadFile = File(...),
    plannedDeliveryCol: Optional[str] = Form(None),
    planningWhse: Optional[str] = Form("ZAC"),
) -> StreamingResponse:
    """Export a DH Load List Excel per mapping.

    - Optional Planned Delivery column via 'plannedDeliveryCol' (UI now defaults to next business day)
    - Inserts a blue info row between transports (loads) with per-load stats in italics
    - Adds hidden blank column C to match provided layout
    """
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Apply Planning Whse filter first (default ZAC); if missing column, no-op
    if planningWhse:
        try:
            df = filter_by_planning_whse(df, allowed_values=(planningWhse,))
        except Exception:
            pass
    df = compute_calculated_fields(df)

    # Helper: compute next available business day (skip Sat/Sun)
    def next_business_day() -> Any:
        d = pd.Timestamp.today().normalize()
        d = d + pd.Timedelta(days=1)
        while d.weekday() >= 5:  # 5=Sat, 6=Sun
            d = d + pd.Timedelta(days=1)
        # return timezone-naive python datetime for Excel compatibility
        try:
            d = d.tz_localize(None)
        except Exception:
            pass
        return d.to_pydatetime()

    # If provided, ensure the column exists; otherwise we'll default per-row
    has_planned_col = bool(plannedDeliveryCol) and plannedDeliveryCol in df.columns

    # Optimize to get trucks and line splits (pieces/weights per transport)
    cfg = {"texas_max_lbs": 52000, "texas_min_lbs": 47000, "other_max_lbs": 48000, "other_min_lbs": 44000}
    try:
        trucks_df, assigns_df = naive_grouping(df.copy(), cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Optimization failed: {exc}") from exc

    # Column normalization helpers
    def norm_key(s: Any) -> str:
        s = str(s)
        s = re.sub(r"\s+", " ", s)
        s = s.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    normalized = {norm_key(c): c for c in df.columns}

    def find_col(target: str, contains_ok: bool = True) -> Optional[str]:
        if target in normalized:
            return normalized[target]
        if contains_ok:
            for nk, orig in normalized.items():
                if target in nk:
                    return orig
        return None

    # Source columns
    col_type = find_col("type")
    col_bpcs = find_col("bpcs")  # BPcs totals per input line
    col_bal_weight = find_col("balweight") or find_col("balanceweight") or find_col("bal weight")
    col_frm = find_col("frm")
    col_grd = find_col("grd")
    col_size = find_col("size")
    col_width = find_col("width") or "Width"
    col_lgth = find_col("lgth") or find_col("length")
    col_trttav = find_col("trttavno", contains_ok=False) or find_col("trttavno")
    col_latest_due = find_col("latestdue") or "Latest Due"
    col_customer = find_col("customer", contains_ok=False) or find_col("customer")
    col_so = find_col("so", contains_ok=False) or "SO"
    col_line = find_col("line", contains_ok=False) or "Line"
    whse_col = _find_planning_whse_col(df)

    # Index original rows by (SO, Line)
    keyed = df.copy()
    try:
        keyed["__so_key__"] = keyed[col_so].astype(str)
        keyed["__line_key__"] = keyed[col_line].astype(str)
    except Exception:
        keyed["__so_key__"] = keyed["SO"].astype(str) if "SO" in keyed.columns else pd.Series([None]*len(keyed), dtype="string")
        keyed["__line_key__"] = keyed["Line"].astype(str) if "Line" in keyed.columns else pd.Series([None]*len(keyed), dtype="string")
    index_map: Dict[tuple, Dict[str, Any]] = {}
    for _, r in keyed.iterrows():
        index_map[(str(r.get("__so_key__")), str(r.get("__line_key__")))] = r.to_dict()

    # Quick truck meta
    zones_by_truck: Dict[int, Optional[str]] = {}
    routes_by_truck: Dict[int, Optional[str]] = {}
    if not trucks_df.empty:
        for _, trow in trucks_df.iterrows():
            tnum = int(trow["truckNumber"]) if pd.notna(trow.get("truckNumber")) else None
            if tnum is None:
                continue
            zones_by_truck[tnum] = None if pd.isna(trow.get("zone")) else str(trow.get("zone"))
            routes_by_truck[tnum] = None if pd.isna(trow.get("route")) else str(trow.get("route"))

    headers = [
        "Actual Ship", "TR#", "Carrier", "Loaded", "Shipped", "Ship Date", "Customer", "Type",
        "SO#", "SO Line", "R#", "WHSE", "Zone", "Route", "BPCS", "RPCS", "Bal Weight",
        "Ready Weight", "Frm", "Grd", "Size", "Width", "Lgth", "D",
    ]

    rows: List[List[Any]] = []
    separator_row_indices: List[int] = []  # indices into `rows` for the blue info rows

    # Build quick lookup for truck metadata
    trucks_meta: Dict[int, Dict[str, Any]] = {}
    if not trucks_df.empty:
        for _, t in trucks_df.iterrows():
            # Guard against missing/None truckNumber
            tnum_val = t.get("truckNumber")
            if tnum_val is None or (hasattr(pd, "isna") and pd.isna(tnum_val)):
                continue
            try:
                tnum = int(tnum_val)
            except Exception:  # noqa: BLE001
                continue
            trucks_meta[tnum] = {
                "totalWeight": float(t.get("totalWeight") or 0.0),
                "maxWeight": float(t.get("maxWeight") or 0.0),
                "containsLate": bool(t.get("containsLate", False)),
                "maxWidth": float(t.get("maxWidth") or 0.0),
            }
    if not assigns_df.empty:
        # Determine sort order by percent utilization (descending)
        util_by_truck: Dict[int, float] = {}
        for tnum in assigns_df["truckNumber"].unique().tolist():
            try:
                tnum_i = int(tnum)
            except Exception:
                continue
            subset_tmp = assigns_df[assigns_df["truckNumber"] == tnum_i]
            total_ready_weight_tmp = float(subset_tmp["totalWeight"].sum()) if "totalWeight" in subset_tmp.columns else float(trucks_meta.get(int(tnum_i), {}).get("totalWeight", 0.0))
            max_weight_tmp = float(trucks_meta.get(int(tnum_i), {}).get("maxWeight", 0.0))
            util_by_truck[tnum_i] = (total_ready_weight_tmp / max_weight_tmp) if max_weight_tmp > 0 else 0.0

        sorted_trucks = sorted(util_by_truck.keys(), key=lambda k: util_by_truck.get(k, 0.0), reverse=True)

        for truck_num in sorted_trucks:
            subset = assigns_df[assigns_df["truckNumber"] == truck_num]
            if subset.empty:
                continue

            # R# per customer order
            route_index: Dict[str, int] = {}
            next_idx = 1
            for _, a in subset.iterrows():
                cust = str(a.get("customerName"))
                if cust not in route_index:
                    route_index[cust] = next_idx
                    next_idx += 1

            for _, a in subset.iterrows():
                so = str(a.get("so"))
                line = str(a.get("line"))
                cust = str(a.get("customerName"))
                src = index_map.get((so, line), {})

                if has_planned_col:
                    actual_ship = src.get(plannedDeliveryCol)  # type: ignore[index]
                else:
                    actual_ship = next_business_day()
                ship_date = src.get(col_latest_due) if col_latest_due in src else src.get("Latest Due")
                # Convert pandas/py datetime to timezone-naive python dt for Excel
                def as_dt(v: Any) -> Any:
                    if isinstance(v, pd.Timestamp):
                        try:
                            # drop timezone if present
                            if v.tz is not None or getattr(v, 'tzinfo', None) is not None:
                                v = v.tz_localize(None)
                        except Exception:
                            try:
                                v = v.tz_convert(None)
                            except Exception:
                                pass
                        return v.to_pydatetime()
                    if isinstance(v, _dt.datetime):
                        if v.tzinfo is not None:
                            # make naive
                            return v.replace(tzinfo=None)
                        return v
                    return v

                row = [
                    as_dt(actual_ship),
                    int(truck_num),
                    "Jordan Carriers",
                    "",
                    "",
                    as_dt(ship_date),
                    cust,
                    src.get(col_type) if col_type else None,
                    so,
                    line,
                    route_index.get(cust, 1),
                    src.get(whse_col) if whse_col else None,
                    zones_by_truck.get(int(truck_num)),
                    routes_by_truck.get(int(truck_num)),
                    src.get(col_bpcs) if col_bpcs else None,
                    int(a.get("piecesOnTransport") or 0),
                    src.get(col_bal_weight) if col_bal_weight else None,
                    float(a.get("totalWeight") or 0.0),
                    src.get(col_frm) if col_frm else None,
                    src.get(col_grd) if col_grd else None,
                    src.get(col_size) if col_size else None,
                    src.get(col_width) if col_width in src else a.get("width"),
                    src.get(col_lgth) if col_lgth else None,
                    src.get(col_trttav) if col_trttav else None,
                ]
                rows.append(row)

            # Separator/info row (light blue, italic): per-load stats
            # Compute per-truck stats from assignments as source of truth
            total_ready_weight = float(subset["totalWeight"].sum()) if "totalWeight" in subset.columns else float(trucks_meta.get(int(truck_num), {}).get("totalWeight", 0.0))
            meta = trucks_meta.get(int(truck_num), {})
            max_weight = float(meta.get("maxWeight", 0.0))
            contains_late = bool(meta.get("containsLate", False)) or (bool(subset["isLate"].any()) if "isLate" in subset.columns else False)
            max_width = float(meta.get("maxWidth", 0.0))
            if "width" in subset.columns:
                try:
                    max_width = max(float(x) for x in subset["width"].tolist() if pd.notna(x)) if not subset.empty else max_width
                except Exception:
                    pass

            pct_util = (total_ready_weight / max_weight * 100.0) if max_weight > 0 else 0.0
            late_status = "Late" if contains_late else "On time"
            overwidth_status = "Overwidth" if max_width > 96 else "Not Overwidth"

            # Start with all Nones, then fill specific columns
            sep_row = cast(List[Any], [None] * len(headers))
            try:
                rpcsi = headers.index("RPCS")
                sep_row[rpcsi] = late_status
            except ValueError:
                pass
            try:
                rwi = headers.index("Ready Weight")
                sep_row[rwi] = round(total_ready_weight, 2)
            except ValueError:
                pass
            try:
                frmi = headers.index("Frm")
                sep_row[frmi] = int(max_weight) if max_weight else None
            except ValueError:
                pass
            try:
                grdi = headers.index("Grd")
                sep_row[grdi] = f"{pct_util:.1f}%"
            except ValueError:
                pass
            try:
                widthi = headers.index("Width")
                sep_row[widthi] = overwidth_status
            except ValueError:
                pass

            rows.append(sep_row)
            separator_row_indices.append(len(rows) - 1)  # 0-based index into rows

    # drop trailing blank
    if rows and (all(v is None for v in rows[-1]) or (len(separator_row_indices) and separator_row_indices[-1] == len(rows) - 1 and all(v is None for v in rows[-1]))):
        # If the last row is an all-None separator (shouldn't occur now), drop it and adjust indices
        rows.pop()
        if separator_row_indices and separator_row_indices[-1] >= len(rows):
            separator_row_indices.pop()

    # Write workbook with styling
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        out_df = pd.DataFrame(rows, columns=headers)
        sheet = "DH Load List"
        out_df.to_excel(writer, sheet_name=sheet, index=False)

        ws = writer.sheets[sheet]
        # Insert hidden blank column C
        ws.insert_cols(3)
        ws.cell(row=1, column=3).value = None
        ws.column_dimensions[get_column_letter(3)].hidden = True
        # Freeze the header row
        ws.freeze_panes = "A2"

        # Bold header
        for c in range(1, ws.max_column + 1):
            ws.cell(row=1, column=c).font = Font(bold=True)

        # Shade and italicize only the separator/info rows in light blue
        fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
        for idx in separator_row_indices:
            excel_row = 2 + idx  # header is row 1
            if excel_row <= ws.max_row:
                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=excel_row, column=c)
                    cell.fill = fill
                    cell.font = Font(italic=True)

        # Apply date format mm/dd/yyy to Actual Ship and Ship Date columns
        header_to_col: Dict[str, int] = {}
        for c in range(1, ws.max_column + 1):
            header_val = ws.cell(row=1, column=c).value
            if isinstance(header_val, str):
                header_to_col[header_val.strip()] = c
        date_fmt = "mm/dd/yyy"
        for header in ("Actual Ship", "Ship Date"):
            cidx = header_to_col.get(header)
            if cidx:
                for r in range(2, ws.max_row + 1):
                    cell = ws.cell(row=r, column=cidx)
                    # Set number format regardless; Excel will apply to date values
                    cell.number_format = date_fmt

        # Auto-fit column widths (skip hidden column C)
        for c in range(1, ws.max_column + 1):
            if ws.column_dimensions[get_column_letter(c)].hidden:
                continue
            max_len = 0
            for r in range(1, ws.max_row + 1):
                val = ws.cell(row=r, column=c).value
                if val is None:
                    continue
                sval = val if isinstance(val, str) else str(val)
                if len(sval) > max_len:
                    max_len = len(sval)
            # Add padding, clamp to a reasonable max
            width = min(max_len + 2, 50)
            # Ensure a sensible minimum width for key columns
            if width < 10:
                width = 10
            ws.column_dimensions[get_column_letter(c)].width = width

    output.seek(0)
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dh_load_list.xlsx"},
    )
