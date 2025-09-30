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


# ---- Address extraction & normalization (Phase 1) ----
_ADDR_TOKENS = {
    "street": ("street", "addr", "address", "shippingaddress", "shipaddr", "shipaddress"),
    "city": ("city", "shippingcity", "shipcity"),
    "state": ("state", "st", "shippingstate", "shipstate"),
    "zip": ("zip", "zipcode", "postal", "postalcode", "shippingzip", "shipzip"),
}


def _find_col_by_tokens(df: pd.DataFrame, tokens: tuple[str, ...]) -> Optional[str]:
    normalized = {_norm_key(c): c for c in df.columns}
    for t in tokens:
        key = re.sub(r"[^a-z0-9]+", "", str(t).lower())
        if key in normalized:
            return normalized[key]
    # fallback contains search
    for nk, orig in normalized.items():
        if any(tok in nk for tok in tokens):
            return orig
    return None


def detect_address_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Return mapping of 'street','city','state','zip' columns if discoverable."""
    return {
        "street": _find_col_by_tokens(df, _ADDR_TOKENS["street"]),
        "city": _find_col_by_tokens(df, _ADDR_TOKENS["city"]),
        "state": _find_col_by_tokens(df, _ADDR_TOKENS["state"]),
        "zip": _find_col_by_tokens(df, _ADDR_TOKENS["zip"]),
    }


def normalize_address_parts(street: Optional[str], city: Optional[str], state: Optional[str], zip_code: Optional[str]) -> Dict[str, Optional[str]]:
    def clean(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    street_c = clean(street)
    city_c = clean(city)
    state_c = clean(state)
    zip_c = clean(zip_code)
    if state_c:
        state_c = state_c.upper()
    if zip_c:
        zip_c = re.sub(r"[^0-9]", "", zip_c)[:10]
    return {"street": street_c, "city": city_c, "state": state_c, "zip": zip_c}


def make_normalized_key(parts: Dict[str, Optional[str]]) -> str:
    """Make a consistent normalized address key suitable for caching."""
    comp = [
        (parts.get("street") or "").strip().lower(),
        (parts.get("city") or "").strip().lower(),
        (parts.get("state") or "").strip().upper(),
        (parts.get("zip") or "").strip(),
        "USA",
    ]
    joined = ",".join(comp)
    joined = re.sub(r"\s+", " ", joined)
    return re.sub(r"[^a-z0-9, ]", "", joined)


def extract_unique_addresses(df: pd.DataFrame) -> List[Dict[str, Optional[str]]]:
    cols = detect_address_columns(df)
    street_col, city_col, state_col, zip_col = cols.get(
        "street"), cols.get("city"), cols.get("state"), cols.get("zip")
    if not any([city_col, state_col, street_col, zip_col]):
        return []
    subset_cols = [c for c in [street_col, city_col, state_col, zip_col] if c]
    if not subset_cols:
        return []
    sub = df[subset_cols].copy()
    sub = sub.fillna("")
    unique_rows = sub.drop_duplicates()
    results: List[Dict[str, Optional[str]]] = []
    for _, r in unique_rows.iterrows():
        street = r.get(street_col) if street_col else None
        city = r.get(city_col) if city_col else None
        state = r.get(state_col) if state_col else None
        zip_code = r.get(zip_col) if zip_col else None
        parts = normalize_address_parts(str(street) if street is not None else None,
                                        str(city) if city is not None else None,
                                        str(state) if state is not None else None,
                                        str(zip_code) if zip_code is not None else None)
        results.append({**parts, "normalized": make_normalized_key(parts)})
    return results
