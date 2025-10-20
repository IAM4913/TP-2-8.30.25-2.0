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


def apply_routing_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply business rule filters for routing optimization.

    Filters applied in order:
    1. Transform yes_no="yes" rows: set RPcs=BPcs and Ready Weight=Balance Weight
    2. Exclude Credit="H" (credit hold)
    3. Exclude ship_hold="H" (shipping hold)
    4. Exclude RPcs<=0 (no pieces to ship)

    Returns filtered DataFrame with transformations applied.
    """
    if df.empty:
        return df

    result = df.copy()
    initial_count = len(result)

    # Step 1: Transform yes_no="yes" rows BEFORE filtering
    if "yes_no" in result.columns:
        # Case-insensitive match for "yes"
        yes_mask = result["yes_no"].astype(
            str).str.strip().str.lower() == "yes"
        yes_count = yes_mask.sum()

        if yes_count > 0:
            # Copy BPcs to RPcs
            if "BPcs" in result.columns:
                result.loc[yes_mask, "RPcs"] = result.loc[yes_mask, "BPcs"]

            # Copy Balance Weight to Ready Weight
            if "Balance Weight" in result.columns:
                result.loc[yes_mask,
                           "Ready Weight"] = result.loc[yes_mask, "Balance Weight"]

            print(
                f"[apply_routing_filters] Transformed {yes_count} rows where yes_no='yes' (RPcs=BPcs, Ready Weight=Balance Weight)")

    # Step 2: Filter out Credit="H" (exact match, case-sensitive)
    if "Credit" in result.columns:
        credit_hold_mask = result["Credit"].astype(str).str.strip() == "H"
        credit_hold_count = credit_hold_mask.sum()
        result = result[~credit_hold_mask].copy()
        if credit_hold_count > 0:
            print(
                f"[apply_routing_filters] Filtered out {credit_hold_count} rows with Credit='H'")

    # Step 3: Filter out ship_hold="H" (exact match, case-sensitive)
    if "ship_hold" in result.columns:
        ship_hold_mask = result["ship_hold"].astype(str).str.strip() == "H"
        ship_hold_count = ship_hold_mask.sum()
        result = result[~ship_hold_mask].copy()
        if ship_hold_count > 0:
            print(
                f"[apply_routing_filters] Filtered out {ship_hold_count} rows with ship_hold='H'")

    # Step 4: Filter out RPcs<=0
    if "RPcs" in result.columns:
        # Ensure numeric type
        result["RPcs"] = pd.to_numeric(result["RPcs"], errors="coerce")
        rpcs_invalid_mask = (result["RPcs"].isna()) | (result["RPcs"] <= 0)
        rpcs_invalid_count = rpcs_invalid_mask.sum()
        result = result[~rpcs_invalid_mask].copy()
        if rpcs_invalid_count > 0:
            print(
                f"[apply_routing_filters] Filtered out {rpcs_invalid_count} rows with RPcs<=0")

    final_count = len(result)
    total_filtered = initial_count - final_count
    print(
        f"[apply_routing_filters] Total: {initial_count} rows -> {final_count} rows ({total_filtered} filtered out)")

    return result.reset_index(drop=True)


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

    # Infer country based on state/province code. Default to USA.
    MX_STATE_CODES = {
        "AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "CH", "CMX", "COA", "COL",
        "DUR", "GUA", "GRO", "HID", "JAL", "MEX", "MIC", "MOR", "NAY", "NLE",
        "OAX", "PUE", "QUE", "ROO", "SLP", "SIN", "SON", "TAB", "TAM", "TLA",
        "VER", "YUC", "ZAC"
    }
    country_c = "Mexico" if (
        state_c or "").upper() in MX_STATE_CODES else "USA"

    return {"street": street_c, "city": city_c, "state": state_c, "zip": zip_c, "country": country_c}


def make_normalized_key(parts: Dict[str, Optional[str]]) -> str:
    """Make a consistent normalized address key suitable for caching."""
    comp = [
        (parts.get("street") or "").strip().lower(),
        (parts.get("city") or "").strip().lower(),
        (parts.get("state") or "").strip().upper(),
        (parts.get("zip") or "").strip(),
        (parts.get("country") or "USA").strip(),
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
