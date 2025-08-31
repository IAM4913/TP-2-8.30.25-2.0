from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
from io import BytesIO
from .schemas import UploadPreviewResponse, OptimizeRequest, OptimizeResponse
from .excel_utils import compute_calculated_fields
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
    sample_records: List[Dict[str, Any]] = (
        df.head(5).to_dict(orient="records") if not df.empty else []
    )

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

    return OptimizeResponse(
        trucks=trucks_df.to_dict(
            orient="records") if not trucks_df.empty else [],
        assignments=assigns_df.to_dict(
            orient="records") if not assigns_df.empty else [],
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
