from __future__ import annotations

from typing import List, Tuple, Dict, Any, Optional
import math
import requests


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two points.
    Uses WGS84 mean Earth radius.
    """
    R_km = 6371.0088
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km = R_km * c
    return km * 0.621371


def driving_time_estimate_minutes(distance_miles: float, avg_speed_mph: float = 45.0) -> float:
    if distance_miles <= 0.0:
        return 0.0
    mph = max(10.0, min(75.0, float(avg_speed_mph)))
    return (distance_miles / mph) * 60.0


def google_distance_matrix(
    api_key: str,
    origins: List[Tuple[float, float]],
    destinations: List[Tuple[float, float]],
) -> Tuple[List[List[float]], List[List[float]]]:
    """Query Google Distance Matrix API.

    Returns (distance_miles_matrix, duration_minutes_matrix).
    """
    if not origins or not destinations:
        return [], []
    base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    orig_str = "|".join([f"{lat},{lng}" for lat, lng in origins])
    dest_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
    params = {
        "origins": orig_str,
        "destinations": dest_str,
        "units": "imperial",
        "key": api_key,
    }
    resp = requests.get(base_url, params=params, timeout=20)
    data = resp.json()
    if (data.get("status") or "").upper() != "OK":
        raise RuntimeError(f"DistanceMatrix status {data.get('status')}")
    rows = data.get("rows") or []
    dist_miles: List[List[float]] = []
    dur_min: List[List[float]] = []
    for r_idx, r in enumerate(rows):
        elements = r.get("elements") or []
        drow: List[float] = []
        trow: List[float] = []
        for c_idx, el in enumerate(elements):
            st = (el.get("status") or "").upper()
            if st != "OK":
                # Fallback to haversine estimate when Google cannot provide a route
                d = haversine_miles(
                    origins[r_idx][0], origins[r_idx][1],
                    destinations[c_idx][0], destinations[c_idx][1]
                )
                drow.append(d)
                trow.append(driving_time_estimate_minutes(d))
            else:
                meters = float((el.get("distance") or {}).get("value") or 0.0)
                seconds = float((el.get("duration") or {}).get("value") or 0.0)
                drow.append(meters / 1609.344)
                trow.append(seconds / 60.0)
        dist_miles.append(drow)
        dur_min.append(trow)
    return dist_miles, dur_min


def haversine_matrix(
    coords: List[Tuple[float, float]],
    factor: float = 1.25,
    avg_speed_mph: float = 45.0,
) -> Tuple[List[List[float]], List[List[float]]]:
    """Compute symmetric distance/time matrix using Haversine with a multiplier factor.

    factor inflates straight-line distance to approximate driving distance.
    """
    n = len(coords)
    dist = [[0.0 for _ in range(n)] for _ in range(n)]
    dur = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = haversine_miles(
                coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * factor
            dist[i][j] = d
            dur[i][j] = driving_time_estimate_minutes(d, avg_speed_mph)
    return dist, dur
