from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, cast
import datetime as _dt
import pandas as pd
from io import BytesIO
import re
from openpyxl.styles import PatternFill, Font, Alignment
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
from .excel_utils import compute_calculated_fields, _find_planning_whse_col, filter_by_planning_whse, filter_by_credit_status
from .optimizer_simple import naive_grouping, NO_MULTI_STOP_CUSTOMERS
from dotenv import load_dotenv  # new
import os
import psycopg
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qsl, urlencode


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

load_dotenv()  # new: loads backend/.env


def _ensure_sslmode(dsn: str) -> str:
    """Append sslmode=require if not present in DSN query string.

    Handles both DSN with and without existing query params.
    """
    try:
        parsed = urlparse(dsn)
        # If not a URL (e.g., key=value DSN), just return as-is
        if not parsed.scheme or not parsed.netloc:
            return dsn
        q = dict(parse_qsl(parsed.query))
        if "sslmode" not in q:
            q["sslmode"] = "require"
            new_query = urlencode(q)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return dsn
    except Exception:
        return dsn


def _build_supabase_dsn() -> str:
    """Build a Postgres DSN.

    Priority:
    1) SUPABASE_DB_URL (if provided)
    2) Construct from SUPABASE_DB_HOST, SUPABASE_DB_PORT, SUPABASE_DB_NAME, SUPABASE_DB_USER, SUPABASE_DB_PASSWORD
       (password is URL-encoded to handle special characters)
    Always ensures sslmode=require for Supabase.
    """
    # 1) Direct URL
    raw = os.getenv("SUPABASE_DB_URL")
    if raw:
        return _ensure_sslmode(raw)

    # 2) Assemble from parts
    host = os.getenv("SUPABASE_DB_HOST")
    user = os.getenv("SUPABASE_DB_USER", "postgres")
    password = os.getenv("SUPABASE_DB_PASSWORD")
    dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
    port = os.getenv("SUPABASE_DB_PORT", "5432")
    if host and password:
        pw_enc = quote_plus(password)
        dsn = f"postgresql://{user}:{pw_enc}@{host}:{port}/{dbname}?sslmode=require"
        return dsn
    return ""


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/db/ping")
def db_ping() -> Dict[str, Any]:
    """Test connection to Supabase Postgres using SUPABASE_DB_URL.

    Returns a tiny payload with server_version and current_timestamp from the DB.
    """
    dsn = _build_supabase_dsn()
    if not dsn:
        raise HTTPException(
            status_code=500, detail="Database connection not configured. Set SUPABASE_DB_URL or SUPABASE_DB_HOST + SUPABASE_DB_PASSWORD.")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select version(), now();")
                version, now_val = cur.fetchone()
        return {"ok": True, "version": str(version), "now": str(now_val)}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"DB ping failed: {exc}") from exc


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

    # Drop credit-hold rows (keep only allowed credit states)
    try:
        df = filter_by_credit_status(df, allowed_values=("A",))
    except Exception:
        pass

    # Normalize headers by exact names as in the source file (no strip/rename yet)
    headers: List[str] = list(map(str, df.columns.tolist()))

    missing = [col for col in REQUIRED_COLUMNS_MAPPED if col not in headers]

    # Provide a small sample for UI validation
    sample_records = df.head(5).to_dict(
        orient="records") if not df.empty else []

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

    # Drop credit-hold rows (keep only allowed credit states)
    try:
        df = filter_by_credit_status(df, allowed_values=("A",))
    except Exception:
        pass

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

    trucks_list = trucks_df.to_dict(
        orient="records") if not trucks_df.empty else []
    assigns_list = assigns_df.to_dict(
        orient="records") if not assigns_df.empty else []

    # Clean up NaN values in assignments before creating Pydantic models
    for assign in assigns_list:
        # Handle NaN values for boolean fields
        if pd.isna(assign.get('isRemainder')):
            assign['isRemainder'] = False
        if pd.isna(assign.get('isPartial')):
            assign['isPartial'] = False
        # Handle NaN values for string fields
        if pd.isna(assign.get('parentLine')):
            assign['parentLine'] = None
        # Handle NaN values for integer fields
        if pd.isna(assign.get('remainingPieces')):
            assign['remainingPieces'] = 0

    # Ensure JSON-serializable keys and create typed models
    trucks_models: List[TruckSummary] = [TruckSummary(
        **{str(k): v for k, v in t.items()}) for t in trucks_list]
    assigns_models: List[LineAssignment] = [LineAssignment(
        **{str(k): v for k, v in a.items()}) for a in assigns_list]

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

    # Drop credit-hold rows (keep only allowed credit states)
    try:
        df = filter_by_credit_status(df, allowed_values=("A",))
    except Exception:
        pass

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
        raise HTTPException(
            status_code=400, detail=f"Invalid request: {exc}") from exc

    # Load Excel
    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Drop credit-hold rows (keep only allowed credit states)
    try:
        df = filter_by_credit_status(df, allowed_values=("A",))
    except Exception:
        pass

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
        raise HTTPException(
            status_code=400, detail=f"Optimization failed: {exc}") from exc

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
    mask_selected = assigns_df.apply(lambda r: (
        r["__so_key__"], r["__line_key__"]) in sel_pairs, axis=1)
    selected_rows = assigns_df[mask_selected]
    if selected_rows.empty:
        return CombineTrucksResponse(success=False, message="Selected lines not found in current optimization", updatedAssignments=[], removedTruckIds=[])

    # Determine candidate trucks and target (lightest among involved)
    involved_trucks = sorted(set(int(t)
                             for t in selected_rows["truckNumber"].tolist()))
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
    removed = [t for t in source_trucks_before if t !=
               target_truck and t not in remaining_by_truck.index.tolist()]

    # Recompute target truck summary from its assignments
    t_assigns = assigns_df[assigns_df["truckNumber"] == target_truck].copy()
    # Determine state and limits from any row
    any_state = str(t_assigns["customerState"].iloc[0]
                    ) if not t_assigns.empty else ""
    is_texas = str(any_state).strip().upper() in {"TX", "TEXAS"}
    max_weight = cfg["texas_max_lbs"] if is_texas else cfg["other_max_lbs"]
    min_weight = cfg["texas_min_lbs"] if is_texas else cfg["other_min_lbs"]
    total_weight = float(t_assigns["totalWeight"].sum())
    total_pieces = int(t_assigns["piecesOnTransport"].sum())
    total_lines = int(t_assigns.shape[0])
    total_orders = int(t_assigns["so"].nunique())
    max_width = float(t_assigns["width"].max()) if not t_assigns.empty else 0.0
    contains_late = bool(t_assigns["isLate"].any(
    )) if "isLate" in t_assigns.columns else False
    priority_bucket = "Late" if contains_late else "WithinWindow"
    # Use first destination/customer for summary context
    customer_name = str(
        t_assigns["customerName"].iloc[0]) if not t_assigns.empty else ""
    customer_city = str(
        t_assigns["customerCity"].iloc[0]) if not t_assigns.empty else ""
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
    updated_assignments_rows = assigns_df[assigns_df["truckNumber"].isin(
        list(changed_trucks))]
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
            trttav_no=str(a.get("trttav_no")) if pd.notna(
                a.get("trttav_no")) else None,
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
            earliestDue=str(a.get("earliestDue")) if pd.notna(
                a.get("earliestDue")) else None,
            latestDue=str(a.get("latestDue")) if pd.notna(
                a.get("latestDue")) else None,
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

    # Helper: normalize pandas/python datetimes to timezone-naive python datetime
    def as_dt(v: Any) -> Any:
        if isinstance(v, pd.Timestamp):
            try:
                if v.tz is not None or getattr(v, 'tzinfo', None) is not None:
                    v = v.tz_localize(None)
            except Exception:
                try:
                    v = v.tz_convert(None)
                except Exception:
                    pass
            return v.to_pydatetime()
        if isinstance(v, _dt.datetime):
            return v.replace(tzinfo=None) if v.tzinfo is not None else v
        return v

    # Helper: next business day after a given date (skip Sat/Sun)
    def next_business_day_after(value: Any) -> _dt.datetime:
        try:
            ts = pd.to_datetime(value, errors="coerce")
        except Exception:
            ts = pd.NaT
        if pd.isna(ts):
            return next_business_day()
        try:
            ts = ts.tz_localize(None)
        except Exception:
            try:
                ts = ts.tz_convert(None)
            except Exception:
                pass
        ts = ts + pd.Timedelta(days=1)
        while ts.weekday() >= 5:
            ts = ts + pd.Timedelta(days=1)
        return ts.to_pydatetime()

    # Helper: add N business days to a given date (skip Sat/Sun)
    def add_business_days(start: Any, days: int) -> _dt.datetime:
        try:
            ts = pd.to_datetime(start, errors="coerce")
        except Exception:
            ts = pd.NaT
        if pd.isna(ts):
            ts = pd.Timestamp.today().normalize()
        try:
            ts = ts.tz_localize(None)
        except Exception:
            try:
                ts = ts.tz_convert(None)
            except Exception:
                pass
        remaining = int(days or 0)
        step = 1 if remaining >= 0 else -1
        while remaining != 0:
            ts = ts + pd.Timedelta(days=step)
            if ts.weekday() < 5:
                remaining -= step
        return ts.to_pydatetime()

    # Planned Delivery column no longer drives Actual Ship; logic is per-load as specified
    has_planned_col = False

    # Optimize to get trucks and line splits (pieces/weights per transport)
    cfg = {"texas_max_lbs": 52000, "texas_min_lbs": 47000,
           "other_max_lbs": 48000, "other_min_lbs": 44000}
    try:
        trucks_df, assigns_df = naive_grouping(df.copy(), cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Optimization failed: {exc}") from exc

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
    col_bal_weight = find_col("balweight") or find_col(
        "balanceweight") or find_col("bal weight")
    col_frm = find_col("frm")
    col_grd = find_col("grd")
    col_size = find_col("size")
    col_width = find_col("width") or "Width"
    col_lgth = find_col("lgth") or find_col("length")
    col_trttav = find_col(
        "trttavno", contains_ok=False) or find_col("trttavno")
    # Exact 'R' column from input for R# mapping
    col_r = find_col("r", contains_ok=False)
    col_latest_due = find_col("latestdue") or "Latest Due"
    col_earliest_due_src = find_col("earliestdue") or "Earliest Due"
    col_customer = find_col(
        "customer", contains_ok=False) or find_col("customer")
    col_so = find_col("so", contains_ok=False) or "SO"
    col_line = find_col("line", contains_ok=False) or "Line"
    whse_col = _find_planning_whse_col(df)

    # Index original rows by (SO, Line)
    keyed = df.copy()
    try:
        keyed["__so_key__"] = keyed[col_so].astype(str)
        keyed["__line_key__"] = keyed[col_line].astype(str)
    except Exception:
        keyed["__so_key__"] = keyed["SO"].astype(
            str) if "SO" in keyed.columns else pd.Series([None]*len(keyed), dtype="string")
        keyed["__line_key__"] = keyed["Line"].astype(
            str) if "Line" in keyed.columns else pd.Series([None]*len(keyed), dtype="string")
    index_map: Dict[tuple, Dict[str, Any]] = {}
    for _, r in keyed.iterrows():
        index_map[(str(r.get("__so_key__")), str(
            r.get("__line_key__")))] = r.to_dict()

    # Quick truck meta
    zones_by_truck: Dict[int, Optional[str]] = {}
    routes_by_truck: Dict[int, Optional[str]] = {}
    if not trucks_df.empty:
        for _, trow in trucks_df.iterrows():
            tnum = int(trow["truckNumber"]) if pd.notna(
                trow.get("truckNumber")) else None
            if tnum is None:
                continue
            zones_by_truck[tnum] = None if pd.isna(
                trow.get("zone")) else str(trow.get("zone"))
            routes_by_truck[tnum] = None if pd.isna(
                trow.get("route")) else str(trow.get("route"))

    headers = [
        "Actual Ship", "TR#", "Carrier", "Loaded", "Shipped", "Earliest Ship Date", "Ship Date", "Customer", "Type",
        "SO#", "SO Line", "R#", "WHSE", "Zone", "Route", "BPCS", "RPCS", "Bal Weight",
        "Ready Weight", "Frm", "Grd", "Size", "Width", "Lgth", "D", "PRV",
    ]

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
    # Map truck -> priority bucket based on its assignments
    bucket_by_truck: Dict[int, str] = {}
    if not assigns_df.empty:
        for tnum in assigns_df["truckNumber"].unique().tolist():
            try:
                tnum_i = int(tnum)
            except Exception:
                continue
            subset_tmp = assigns_df[assigns_df["truckNumber"] == tnum_i]
            bucket_val = "WithinWindow"
            if "priorityBucket" in subset_tmp.columns:
                vals = subset_tmp["priorityBucket"].dropna().astype(
                    str).tolist()
                if any(v == "Late" for v in vals):
                    bucket_val = "Late"
                elif any(v == "NearDue" for v in vals):
                    bucket_val = "NearDue"
            elif "isLate" in subset_tmp.columns and bool(subset_tmp["isLate"].any()):
                bucket_val = "Late"
            bucket_by_truck[tnum_i] = bucket_val
    # Helper to build rows for a given ordered list of trucks

    def build_rows_for(truck_order: List[int]) -> tuple[List[List[Any]], List[int], List[float]]:
        rows_local: List[List[Any]] = []
        sep_indices: List[int] = []
        sep_utils: List[float] = []

        def to_int(v: Any) -> Optional[int]:
            try:
                if v is None or (hasattr(pd, 'isna') and pd.isna(v)):
                    return None
                return int(float(v))
            except Exception:
                return None

        def to_float(v: Any) -> Optional[float]:
            try:
                if v is None or (hasattr(pd, 'isna') and pd.isna(v)):
                    return None
                return float(v)
            except Exception:
                return None
        for truck_num in truck_order:
            subset = assigns_df[assigns_df["truckNumber"] == truck_num]
            if subset.empty:
                continue
            # Compute per-load Actual Ship per rules:
            # - If any line is Late -> next business day
            # - Else -> day after latest Earliest Due among lines in this load
            contains_late_subset = bool(
                subset["isLate"].any()) if "isLate" in subset.columns else False
            if contains_late_subset:
                truck_actual_ship = as_dt(next_business_day())
            else:
                # Prefer assignments_df 'earliestDue'
                ed_series = None
                if "earliestDue" in subset.columns:
                    try:
                        ed_series = pd.to_datetime(
                            subset["earliestDue"], errors="coerce")
                    except Exception:
                        ed_series = None
                # Fallback to source 'Earliest Due' via index_map
                if ed_series is None or ed_series.dropna().empty:
                    ed_vals: list = []
                    for _, arow in subset.iterrows():
                        so = str(arow.get("so"))
                        line = str(arow.get("line"))
                        # Strip remainder suffixes for index_map lookup since source data doesn't have them
                        line_for_lookup = line
                        if line and line.endswith(('-R1', '-R2', '-R3', '-R4', '-R5', '-R6', '-R7', '-R8', '-R9')):
                            # Remove the -RX suffix
                            line_for_lookup = line[:-3]
                        src = index_map.get((so, line_for_lookup), {})
                        ed_vals.append(src.get(col_earliest_due_src))
                    try:
                        ed_series = pd.to_datetime(
                            pd.Series(ed_vals), errors="coerce")
                    except Exception:
                        ed_series = pd.Series([], dtype="datetime64[ns]")
                if ed_series.dropna().empty:
                    # No usable earliest due; default to next business day
                    truck_actual_ship = as_dt(next_business_day())
                else:
                    max_ed = ed_series.max()
                    # Next business day after max earliest due
                    truck_actual_ship = next_business_day_after(max_ed)
                    # If this date is in the past, move it 3 business days into the future from today
                    try:
                        tas = pd.to_datetime(
                            truck_actual_ship, errors="coerce")
                        today = pd.Timestamp.today().normalize()
                        if pd.notna(tas) and tas < today:
                            truck_actual_ship = add_business_days(today, 3)
                    except Exception:
                        pass
            for _, a in subset.iterrows():
                so = str(a.get("so"))
                line = str(a.get("line"))
                # Strip remainder suffixes (-R1, -R2, etc.) from line number for DH load list export
                line_for_export = line
                line_for_lookup = line
                if line and line.endswith(('-R1', '-R2', '-R3', '-R4', '-R5', '-R6', '-R7', '-R8', '-R9')):
                    # Remove the -RX suffix for export
                    line_for_export = line[:-3]
                    # Remove the -RX suffix for index_map lookup
                    line_for_lookup = line[:-3]
                cust = str(a.get("customerName"))
                src = index_map.get((so, line_for_lookup), {})
                ship_date = src.get(
                    col_latest_due) if col_latest_due in src else src.get("Latest Due")
                # as_dt defined above
                # Use on-transport values for counts and weights (no SO line quantities)
                bpcs_val = int(a.get("piecesOnTransport") or 0)
                bal_weight_val = float(a.get("totalWeight") or 0.0)
                # Frm: pull from source as-is (case-insensitive), do not force numeric
                frm_val = src.get(col_frm) if col_frm else None
                # keep as-is (text in data rows)
                grd_val = src.get(col_grd) if col_grd else None
                size_val = src.get(col_size) if col_size else None
                width_val = to_float(src.get(col_width)) if (
                    col_width and col_width in src) else to_float(a.get("width"))
                lgth_val = to_float(src.get(col_lgth)) if col_lgth else None
                d_val = src.get(col_trttav) if col_trttav else None
                # R#: from source 'R' column, if present
                rnum_val = None
                if col_r and col_r in src:
                    rnum_val = to_int(src.get(col_r))
                # PRV: 1 for data lines with weight
                prv_val = 1 if float(a.get("totalWeight")
                                     or 0.0) > 0.0 else None
                # Get earliest ship date from source data
                earliest_ship_date = src.get(
                    col_earliest_due_src) if col_earliest_due_src in src else src.get("Earliest Due")

                row = [
                    truck_actual_ship,
                    int(truck_num),
                    "Jordan Carriers",
                    "",
                    "",
                    as_dt(earliest_ship_date),
                    as_dt(ship_date),
                    cust,
                    src.get(col_type) if col_type else None,
                    so,
                    line_for_export,  # Use cleaned line number without remainder suffix
                    rnum_val,
                    src.get(whse_col) if whse_col else None,
                    zones_by_truck.get(int(truck_num)),
                    routes_by_truck.get(int(truck_num)),
                    bpcs_val,
                    int(a.get("piecesOnTransport") or 0),
                    bal_weight_val,
                    float(a.get("totalWeight") or 0.0),
                    frm_val,
                    grd_val,
                    size_val,
                    width_val,
                    lgth_val,
                    d_val,
                    prv_val,
                ]
                rows_local.append(row)
            # Info row
            total_ready_weight = float(subset["totalWeight"].sum()) if "totalWeight" in subset.columns else float(
                trucks_meta.get(int(truck_num), {}).get("totalWeight", 0.0))
            meta = trucks_meta.get(int(truck_num), {})
            max_weight = float(meta.get("maxWeight", 0.0))
            contains_late = bool(meta.get("containsLate", False)) or (
                bool(subset["isLate"].any()) if "isLate" in subset.columns else False)
            max_width = float(meta.get("maxWidth", 0.0))
            if "width" in subset.columns and not subset.empty:
                try:
                    max_width = max(float(x)
                                    for x in subset["width"].tolist() if pd.notna(x))
                except Exception:
                    pass
            pct_util = (total_ready_weight / max_weight *
                        100.0) if max_weight > 0 else 0.0
            late_status = "Late" if contains_late else "On time"
            overwidth_status = "Overwidth" if max_width > 96 else "Not Overwidth"
            sep_row = cast(List[Any], [None] * len(headers))
            for label, value in (("RPCS", late_status), ("Ready Weight", round(total_ready_weight, 2)), ("Frm", int(max_weight) if max_weight else None), ("Grd", f"{pct_util:.1f}%"), ("Width", overwidth_status)):
                try:
                    idx_col = headers.index(label)
                    sep_row[idx_col] = value
                except ValueError:
                    pass
            rows_local.append(sep_row)
            sep_indices.append(len(rows_local) - 1)
            sep_utils.append(float(pct_util))
        return rows_local, sep_indices, sep_utils

    # Determine sort order by percent utilization (descending)
    util_by_truck: Dict[int, float] = {}
    if not assigns_df.empty:
        for tnum in assigns_df["truckNumber"].unique().tolist():
            try:
                tnum_i = int(tnum)
            except Exception:
                continue
            subset_tmp = assigns_df[assigns_df["truckNumber"] == tnum_i]
            total_ready_weight_tmp = float(subset_tmp["totalWeight"].sum()) if "totalWeight" in subset_tmp.columns else float(
                trucks_meta.get(int(tnum_i), {}).get("totalWeight", 0.0))
            max_weight_tmp = float(trucks_meta.get(
                int(tnum_i), {}).get("maxWeight", 0.0))
            util_by_truck[tnum_i] = (
                total_ready_weight_tmp / max_weight_tmp) if max_weight_tmp > 0 else 0.0
    sorted_trucks = sorted(util_by_truck.keys(
    ), key=lambda k: util_by_truck.get(k, 0.0), reverse=True)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Define sheets and included buckets
        sheets_spec = [
            ("Late + NearDue", {"Late", "NearDue"}),
            ("WithinWindow", {"WithinWindow"}),
        ]
        for sheet, include in sheets_spec:
            truck_order = [tn for tn in sorted_trucks if bucket_by_truck.get(
                int(tn), "WithinWindow") in include]
            rows_local, sep_indices, sep_utils = build_rows_for(truck_order)
            out_df = pd.DataFrame(rows_local, columns=headers)
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
                ws.cell(row=1, column=c).font = Font(
                    name="Calibri", size=11, bold=True)

            # Shade and italicize only the separator/info rows in light blue
            fill = PatternFill(start_color="DCE6F1",
                               end_color="DCE6F1", fill_type="solid")
            for idx in sep_indices:
                excel_row = 2 + idx  # header is row 1
                if excel_row <= ws.max_row:
                    for c in range(1, ws.max_column + 1):
                        cell = ws.cell(row=excel_row, column=c)
                        cell.fill = fill
                        cell.font = Font(name="Calibri", size=11, italic=True)

            # Apply date format mm/dd/yyy to Actual Ship, Ship Date, and Earliest Ship Date columns
            header_to_col: Dict[str, int] = {}
            for c in range(1, ws.max_column + 1):
                header_val = ws.cell(row=1, column=c).value
                if isinstance(header_val, str):
                    header_to_col[header_val.strip()] = c
            date_fmt = "mm/dd/yyy"
            for header in ("Actual Ship", "Ship Date", "Earliest Ship Date"):
                cidx = header_to_col.get(header)
                if cidx:
                    for r in range(2, ws.max_row + 1):
                        cell = ws.cell(row=r, column=cidx)
                        cell.number_format = date_fmt

            # Color-code utilization % in separator rows (Grd column)
            grd_col = header_to_col.get("Grd")
            if grd_col and sep_indices:
                for idx, util in zip(sep_indices, sep_utils):
                    excel_row = 2 + idx
                    if excel_row <= ws.max_row:
                        cell = ws.cell(row=excel_row, column=grd_col)
                        # Keep italic; set color based on thresholds
                        if util >= 90.0:
                            color = "FF00B050"  # green
                        elif util >= 84.0:
                            color = "FFFFC000"  # yellow
                        else:
                            color = "FFFF0000"  # red
                        cell.font = Font(name="Calibri", size=11,
                                         italic=True, color=color)

            # Apply numeric formats to non-date numeric columns
            # Do not force numeric on Frm; it may be text in source
            int_cols = ["TR#", "R#", "BPCS", "RPCS", "PRV"]
            float_cols = ["Bal Weight", "Ready Weight", "Width", "Lgth"]
            # Treat RPCS specially: only format as number if the cell is numeric (for data rows, RPCS is not used; sep rows contain text)
            for hdr in int_cols:
                cidx = header_to_col.get(hdr)
                if not cidx:
                    continue
                for r in range(2, ws.max_row + 1):
                    cell = ws.cell(row=r, column=cidx)
                    if hdr == "RPCS" and isinstance(cell.value, str):
                        continue
                    cell.number_format = "0"
            for hdr in float_cols:
                cidx = header_to_col.get(hdr)
                if not cidx:
                    continue
                for r in range(2, ws.max_row + 1):
                    cell = ws.cell(row=r, column=cidx)
                    cell.number_format = "#,##0.00"

            # Standardize font to Calibri 11 for entire sheet while preserving bold/italic/colors
            for r in range(1, ws.max_row + 1):
                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=r, column=c)
                    f = cell.font or Font()
                    cell.font = Font(name="Calibri", size=11,
                                     bold=f.bold, italic=f.italic, color=f.color)

            # Left-align all cells
            left_align = Alignment(horizontal="left")
            for r in range(1, ws.max_row + 1):
                for c in range(1, ws.max_column + 1):
                    ws.cell(row=r, column=c).alignment = left_align

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
                width = min(max_len + 2, 50)
                if width < 10:
                    width = 10
                ws.column_dimensions[get_column_letter(c)].width = width

    output.seek(0)
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dh_load_list.xlsx"},
    )
