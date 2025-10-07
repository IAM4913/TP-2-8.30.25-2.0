from __future__ import annotations

from typing import Optional, Dict, Any, Tuple
import requests
import psycopg


class GeocodeError(Exception):
    pass


def _confidence_from_google(result: Dict[str, Any]) -> float:
    """Heuristic confidence scoring 0..1 based on Google Geocoding result."""
    if not result:
        return 0.0
    types = set(result.get("types") or [])
    partial = bool(result.get("partial_match"))
    if "street_address" in types or "premise" in types or "subpremise" in types:
        base = 0.95
    elif "route" in types or "intersection" in types:
        base = 0.85
    elif "locality" in types or "administrative_area_level_1" in types:
        base = 0.7
    else:
        base = 0.6
    if partial:
        base -= 0.15
    return max(0.0, min(1.0, base))


def google_geocode_query(address_query: str, api_key: str) -> Tuple[float, float, float, str, str]:
    """Return (lat, lng, confidence, provider, formatted_address). Raises GeocodeError on failure."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(
        url, params={"address": address_query, "key": api_key}, timeout=12)
    if resp.status_code != 200:
        raise GeocodeError(f"HTTP {resp.status_code}")
    data = resp.json()
    status = (data.get("status") or "").upper()
    if status != "OK" or not data.get("results"):
        raise GeocodeError(status or "NO_RESULTS")
    first = data["results"][0]
    loc = (first.get("geometry") or {}).get("location") or {}
    lat = float(loc.get("lat"))
    lng = float(loc.get("lng"))
    conf = _confidence_from_google(first)
    formatted = str(first.get("formatted_address") or "")
    return lat, lng, conf, "google", formatted


def cache_lookup_address(dsn: str, normalized: str) -> Optional[Dict[str, Any]]:
    if not dsn:
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, normalized, latitude, longitude, confidence, provider from address_cache where normalized=%s",
                    (normalized,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "normalized": row[1],
                    "latitude": row[2],
                    "longitude": row[3],
                    "confidence": row[4],
                    "provider": row[5],
                }
    except Exception:
        return None


def cache_upsert_address(
    dsn: str,
    normalized: str,
    parts: Dict[str, Optional[str]],
    lat: float,
    lng: float,
    confidence: float,
    provider: str,
) -> None:
    if not dsn:
        return
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into address_cache (normalized, street, suite, city, state, zip, latitude, longitude, confidence, provider)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict (normalized)
                    do update set street=excluded.street, suite=excluded.suite, city=excluded.city,
                                  state=excluded.state, zip=excluded.zip, latitude=excluded.latitude,
                                  longitude=excluded.longitude, confidence=excluded.confidence,
                                  provider=excluded.provider, updated_at=now()
                    """,
                    (
                        normalized,
                        parts.get("street"),
                        parts.get("suite"),
                        parts.get("city"),
                        parts.get("state"),
                        parts.get("zip"),
                        lat,
                        lng,
                        confidence,
                        provider,
                    ),
                )
            conn.commit()
    except Exception:
        # Non-fatal
        pass


def build_address_query(parts: Dict[str, Optional[str]]) -> str:
    comps = [parts.get("street"), parts.get("city"),
             parts.get("state"), parts.get("zip"), "USA"]
    return ", ".join([c for c in comps if c and str(c).strip()])

