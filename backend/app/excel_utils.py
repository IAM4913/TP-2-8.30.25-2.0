from __future__ import annotations

from typing import List, Dict, Any
import pandas as pd
from datetime import datetime, timezone


REQUIRED_COLUMNS_MAPPED: List[str] = [
    "SO",
    "Line",
    "Customer",
    "shipping_city",
    "shipping_state",
    "Ready Weight",
    "RPcs",
    "Grd",
    "Size",
    "Width",
    "Earliest Due",
    "Latest Due",
]


def compute_calculated_fields(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    # Ensure numeric types
    for col in ["Ready Weight", "RPcs", "Width"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    # Ready Weight per piece
    if {"Ready Weight", "RPcs"}.issubset(result.columns):
        result["Weight Per Piece"] = result["Ready Weight"] / \
            result["RPcs"].replace(0, pd.NA)

    # Date conversions
    now = pd.Timestamp.now(tz="UTC").normalize()
    for col in ["Earliest Due", "Latest Due"]:
        if col in result.columns:
            result[col] = pd.to_datetime(
                result[col], errors="coerce", utc=True)

    # Use "Latest Due" as Latest Due Date for late calculation
    if "Latest Due" in result.columns:
        result["Is Late"] = result["Latest Due"] < now
        result["Days Until Late"] = (result["Latest Due"] - now).dt.days

    if "Width" in result.columns:
        result["Is Overwidth"] = result["Width"] > 96

    return result


def build_priority_bucket(row: pd.Series) -> str:
    """Determine priority bucket based on Latest Due Date"""
    if pd.isna(row.get("Latest Due")):
        return "WithinWindow"
    now = pd.Timestamp.now(tz="UTC").normalize()
    latest_due = row["Latest Due"]
    if latest_due < now:
        return "Late"
    days = int((latest_due - now).days)
    if days <= 3:
        return "NearDue"
    return "WithinWindow"
