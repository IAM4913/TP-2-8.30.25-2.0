from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, cast
import pandas as pd
import json
from io import BytesIO
from .schemas import (
    UploadPreviewResponse,
    OptimizeRequest,
    OptimizeResponse,
    CombineTrucksRequest,
    CombineTrucksResponse,
    TruckSummary,
    LineAssignment,
)
from .excel_utils import compute_calculated_fields, filter_by_planning_whse
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
        df = filter_by_planning_whse(df, ("ZAC",))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    # Normalize headers by exact names as in the source file (no strip/rename yet)
    headers: List[str] = list(map(str, df.columns.tolist()))

    missing = [col for col in REQUIRED_COLUMNS_MAPPED if col not in headers]

    # Provide a small sample for UI validation
    raw_sample = df.head(5).to_dict(orient="records") if not df.empty else []
    sample_records: List[Dict[str, Any]] = cast(List[Dict[str, Any]], raw_sample)

    return UploadPreviewResponse(
        headers=headers,
        rowCount=int(df.shape[0]),
        missingRequiredColumns=missing,
        sample=sample_records,
    )


@app.post("/optimize", response_model=OptimizeResponse)
async def optimize(file: UploadFile = File(...)) -> OptimizeResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")
    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
        df = filter_by_planning_whse(df, ("ZAC",))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

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

    trucks_list_raw = trucks_df.to_dict(orient="records") if not trucks_df.empty else []
    assigns_list_raw = assigns_df.to_dict(orient="records") if not assigns_df.empty else []
    # Ensure keys are strings for Pydantic unpacking
    trucks_list: List[Dict[str, Any]] = [
        {str(k): v for k, v in t.items()} for t in trucks_list_raw
    ]
    assigns_list: List[Dict[str, Any]] = [
        {str(k): v for k, v in a.items()} for a in assigns_list_raw
    ]

    return OptimizeResponse(
        trucks=[TruckSummary(**t) for t in trucks_list],
        assignments=[LineAssignment(**a) for a in assigns_list],
        sections=sections,
    )


@app.post("/export/trucks")
async def export_trucks(file: UploadFile = File(...)) -> StreamingResponse:
    """Export optimized truck assignments to Excel format"""
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")

    try:
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
        df = filter_by_planning_whse(df, ("ZAC",))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Failed to read Excel: {exc}") from exc

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
    request: str = Form(...)
) -> CombineTrucksResponse:
    """
    Combine selected lines from multiple trucks into a new optimized truck assignment.
    This endpoint takes the original file, re-runs optimization, and then applies the manual combination.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx files are supported")

    try:
        # Parse the JSON request from form data
        try:
            request_data = json.loads(request)
            request_obj = CombineTrucksRequest(**request_data)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request format: {str(e)}"
            )

        # Read and process the original file
        content: bytes = await file.read()
        buffer = BytesIO(content)
        df: pd.DataFrame = pd.read_excel(buffer, engine="openpyxl")
        df = filter_by_planning_whse(df, ("ZAC",))
        df = compute_calculated_fields(df)

        # Use the provided weight config
        cfg = {
            "texas_max_lbs": request_obj.weightConfig.texas_max_lbs,
            "texas_min_lbs": request_obj.weightConfig.texas_min_lbs,
            "other_max_lbs": request_obj.weightConfig.other_max_lbs,
            "other_min_lbs": request_obj.weightConfig.other_min_lbs,
        }

        # Get current optimization results
        trucks_df, assigns_df = naive_grouping(df, cfg)

        # Parse line IDs to extract assignment info (store as plain dicts, not Series)
        selected_assignments: List[Dict[str, Any]] = []
        for line_id in request_obj.lineIds:
            try:
                # Format: "truckNumber-SO-Line"
                parts = line_id.split('-', 2)
                if len(parts) != 3:
                    raise ValueError(f"Invalid line ID format: {line_id}")

                truck_num, so, line = parts
                truck_num = int(truck_num)

                # Find the assignment in assigns_df
                matching_assignments = assigns_df[
                    (assigns_df['truckNumber'] == truck_num) &
                    (assigns_df['so'] == so) &
                    (assigns_df['line'] == line)
                ]

                if matching_assignments.empty:
                    raise ValueError(
                        f"Assignment not found for line ID: {line_id}")

                # Convert the matching row (Series) into a plain dict to satisfy
                # Pydantic response models later.
                row_dict = matching_assignments.iloc[0].to_dict()
                selected_assignments.append({str(k): v for k, v in row_dict.items()})

            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error parsing line ID '{line_id}': {str(e)}"
                )

        if len(selected_assignments) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 lines must be selected for combination"
            )

        # Validate combination rules
        selected_df = pd.DataFrame(selected_assignments)

        # Check if all assignments are from the same state
        states = selected_df['customerState'].unique()
        if len(states) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot combine lines from different states: {states.tolist()}"
            )

        # Enforce same Zone/Route when present; gather from source trucks
        zones_by_truck: Dict[int, Optional[str]] = {}
        routes_by_truck: Dict[int, Optional[str]] = {}
        if not trucks_df.empty:
            for _, trow in trucks_df.iterrows():
                raw_num = trow.get('truckNumber')
                if pd.isna(raw_num):
                    continue
                try:
                    tnum = int(raw_num)
                except Exception:
                    continue
                zval = trow.get('zone')
                rval = trow.get('route')
                zones_by_truck[tnum] = (None if (zval is None or (hasattr(pd, 'isna') and pd.isna(zval))) else str(zval))
                routes_by_truck[tnum] = (None if (rval is None or (hasattr(pd, 'isna') and pd.isna(rval))) else str(rval))

        sel_truck_nums = set(int(x) for x in selected_df['truckNumber'].unique().tolist())
        sel_zones = {zones_by_truck.get(t) for t in sel_truck_nums}
        sel_routes = {routes_by_truck.get(t) for t in sel_truck_nums}
        # Normalize sets by collapsing None-only correctly
        sel_zones_clean = {z for z in sel_zones if z is not None}
        sel_routes_clean = {r for r in sel_routes if r is not None}
        if len(sel_zones_clean) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot combine lines from different zones: {sorted(sel_zones_clean)}"
            )
        if len(sel_routes_clean) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot combine lines from different routes: {sorted(sel_routes_clean)}"
            )

        selected_zone: Optional[str] = next(iter(sel_zones_clean)) if sel_zones_clean else None
        selected_route: Optional[str] = next(iter(sel_routes_clean)) if sel_routes_clean else None

        # Calculate total weight
        total_weight = selected_df['totalWeight'].sum()
        state = states[0]
        max_weight = cfg["texas_max_lbs"] if state in [
            'TX', 'Texas'] else cfg["other_max_lbs"]

        if total_weight > max_weight:
            raise HTTPException(
                status_code=400,
                detail=f"Combined weight ({total_weight:,.0f} lbs) exceeds maximum limit ({max_weight:,.0f} lbs) for {state}"
            )

        # Create new truck assignment
        # Find next available truck number
        max_truck_num = trucks_df['truckNumber'].max() if not trucks_df.empty else 0
        new_truck_number = max_truck_num + 1

        # Get info from first assignment for truck details
        first_assignment = selected_assignments[0]
        min_weight = cfg["texas_min_lbs"] if state in [
            'TX', 'Texas'] else cfg["other_min_lbs"]

        # Calculate aggregated truck stats
        total_pieces = selected_df['piecesOnTransport'].sum()
        total_orders = selected_df['so'].nunique()
        total_lines = len(selected_assignments)
        max_width = selected_df['width'].max()
        overwidth_weight = selected_df[selected_df['isOverwidth']]['totalWeight'].sum()
        percent_overwidth = (overwidth_weight / total_weight * 100) if total_weight > 0 else 0
        contains_late = selected_df['isLate'].any()

        # Determine priority bucket (use highest priority)
        priority_bucket = "WithinWindow"  # Default

        # Create customer name for combined truck
        unique_customers = selected_df['customerName'].unique()
        if len(unique_customers) == 1:
            customer_display = unique_customers[0]
        else:
            customer_display = f"Multi-Stop ({len(unique_customers)} customers)"

        # Create new truck summary
        new_truck: Dict[str, Any] = {
            "truckNumber": int(new_truck_number),
            "customerName": str(customer_display),
            "customerAddress": first_assignment.get('customerAddress'),
            "customerCity": str(first_assignment['customerCity']),
            "customerState": str(first_assignment['customerState']),
            "zone": selected_zone,
            "route": selected_route,
            "totalWeight": float(total_weight),
            "minWeight": int(min_weight),
            "maxWeight": int(max_weight),
            "totalOrders": int(total_orders),
            "totalLines": int(total_lines),
            "totalPieces": int(total_pieces),
            "maxWidth": float(max_width),
            "percentOverwidth": float(percent_overwidth),
            "containsLate": bool(contains_late),
            "priorityBucket": str(priority_bucket),
        }

        # Create updated assignments (reassign to new truck)
        updated_assignments: List[Dict[str, Any]] = []
        for assignment in selected_assignments:
            # Ensure we're working with a plain dict and coerce to JSON-serializable types
            updated_assignment = {str(k): v for k, v in dict(assignment).items()}
            updated_assignment['truckNumber'] = int(new_truck_number)
            # Explicit casting for known numeric/boolean fields
            if 'piecesOnTransport' in updated_assignment:
                updated_assignment['piecesOnTransport'] = int(updated_assignment['piecesOnTransport'])
            if 'totalReadyPieces' in updated_assignment:
                updated_assignment['totalReadyPieces'] = int(updated_assignment['totalReadyPieces'])
            if 'weightPerPiece' in updated_assignment:
                updated_assignment['weightPerPiece'] = float(updated_assignment['weightPerPiece'])
            if 'totalWeight' in updated_assignment:
                updated_assignment['totalWeight'] = float(updated_assignment['totalWeight'])
            if 'width' in updated_assignment:
                updated_assignment['width'] = float(updated_assignment['width'])
            if 'isOverwidth' in updated_assignment:
                updated_assignment['isOverwidth'] = bool(updated_assignment['isOverwidth'])
            if 'isLate' in updated_assignment:
                updated_assignment['isLate'] = bool(updated_assignment['isLate'])
            updated_assignments.append(updated_assignment)

        # Remove original trucks from those being combined (if they're now empty)
        removed_truck_ids = list(set(request_obj.truckIds))

        # Construct typed response models to satisfy validation
        from .schemas import TruckSummary, LineAssignment
        return CombineTrucksResponse(
            success=True,
            message=f"Successfully combined {len(selected_assignments)} lines into truck #{new_truck_number}",
            newTruck=TruckSummary(**new_truck),
            updatedAssignments=[LineAssignment(**a) for a in updated_assignments],
            removedTruckIds=[int(t) for t in removed_truck_ids]
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error combining trucks: {str(exc)}"
        ) from exc
