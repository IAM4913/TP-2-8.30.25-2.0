from __future__ import annotations

from typing import List, Dict, Any, Optional, Iterable
import pandas as pd
from datetime import datetime, timezone
import re


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


# ---- Planning Warehouse helpers ----
def _norm_key(s: Any) -> str:
    s = str(s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _find_planning_whse_col(df: pd.DataFrame) -> Optional[str]:
    """Find the Planning Warehouse column regardless of case/spacing/variants."""
    normalized = {_norm_key(c): c for c in df.columns}
    # Preferred direct matches
    for target in ("planningwhse", "planningwarehouse", "planningwhs", "planningwhsecode"):
        if target in normalized:
            return normalized[target]
    # Fallback: contains both planning and whse/warehouse tokens
    for nk, orig in normalized.items():
        if "planning" in nk and ("whse" in nk or "warehouse" in nk or "whs" in nk):
            return orig
    return None


def filter_by_planning_whse(df: pd.DataFrame, allowed_values: Iterable[str] = ("ZAC",)) -> pd.DataFrame:
    """Return only rows where Planning Whse matches one of allowed_values (case-insensitive). If column not found, return original df unmodified."""
    col = _find_planning_whse_col(df)
    if not col:
        return df
    allowed = {str(v).strip().upper() for v in allowed_values}
    series = df[col].astype(str).str.strip().str.upper()
    mask = series.isin(list(allowed))
    return df.loc[mask].reset_index(drop=True)


# ---- Credit status helpers ----
def _find_credit_status_col(df: pd.DataFrame) -> Optional[str]:
    """Find the credit status column regardless of case/spacing/variants.

    Looks for columns like: Credit, Credit Status, CreditStatus, Credit Hold.
    """
    normalized = {_norm_key(c): c for c in df.columns}
    # Preferred direct matches
    for target in ("credit", "creditstatus", "creditcode", "credithold", "crstatus"):
        if target in normalized:
            return normalized[target]
    # Fallbacks: any column containing the token 'credit'
    for nk, orig in normalized.items():
        if "credit" in nk:
            return orig
    return None


def filter_by_credit_status(
    df: pd.DataFrame,
    allowed_values: Iterable[str] = ("A",),
) -> pd.DataFrame:
    """Keep only rows whose credit status is in allowed_values (case-insensitive).

    If a credit column cannot be found, returns the original DataFrame unmodified.
    Example: allowed_values=("A",) keeps only available credit rows and drops holds like "H".
    """
    col = _find_credit_status_col(df)
    if not col:
        return df
    allowed = {str(v).strip().upper() for v in allowed_values}
    series = df[col].astype(str).str.strip().str.upper()
    mask = series.isin(list(allowed))
    return df.loc[mask].reset_index(drop=True)
