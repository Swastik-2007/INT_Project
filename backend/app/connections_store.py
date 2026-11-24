"""
Confirmed Connections Store (LPU Wayfinder)
=============================================
Manages user-confirmed physical connections between GPX survey tracks.
Distinguishes recorded tracks from manually confirmed walkway connections.
Enforces that straight-line gaps are NEVER described as measured walking
distances or verified corridor shapes until explicit geometry is supplied.
"""

import json
import os
import math
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance in meters on WGS84 ellipsoid."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_connections_file_path() -> Path:
    override = os.getenv("CONFIRMED_CONNECTIONS_FILE")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "confirmed_connections.json"


def load_confirmed_connections() -> Dict[str, Any]:
    path = get_connections_file_path()
    if not path.exists():
        return {"connections": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading confirmed connections: {e}")
        return {"connections": []}


def save_confirmed_connections(data: Dict[str, Any]) -> None:
    path = get_connections_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_connection_by_id(conn_id: str) -> Optional[Dict[str, Any]]:
    data = load_confirmed_connections()
    for conn in data.get("connections", []):
        if conn.get("id") == conn_id:
            return conn
    return None


def update_connection_geometry(
    conn_id: str,
    intermediate_waypoints: List[List[float]],
    confirmed_by: str,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Update geometry for a confirmed connection.
    Computes real geodesic distance across all defined waypoints:
    [from_coords] -> waypoint_1 -> ... -> waypoint_k -> [to_coords].
    """
    data = load_confirmed_connections()
    target_conn = None
    for conn in data.get("connections", []):
        if conn.get("id") == conn_id:
            target_conn = conn
            break

    if not target_conn:
        return None

    from_coords = target_conn["from_coords"]
    to_coords = target_conn["to_coords"]

    # Build sequence of points
    all_pts = [from_coords] + intermediate_waypoints + [to_coords]
    total_dist = 0.0
    for idx in range(len(all_pts) - 1):
        p1 = all_pts[idx]
        p2 = all_pts[idx + 1]
        total_dist += haversine_distance_m(p1[0], p1[1], p2[0], p2[1])

    target_conn["intermediate_waypoints"] = intermediate_waypoints
    target_conn["has_explicit_geometry"] = True
    target_conn["status"] = "geometry_defined"
    target_conn["measured_distance_m"] = round(total_dist, 2)
    target_conn["geometry_confirmed_by"] = confirmed_by
    target_conn["geometry_update_timestamp"] = datetime.utcnow().isoformat() + "Z"
    if notes:
        target_conn["notes"] = notes

    save_confirmed_connections(data)
    return target_conn


def reset_connection_geometry(conn_id: str) -> Optional[Dict[str, Any]]:
    """Reset connection geometry back to pending geometry state."""
    data = load_confirmed_connections()
    target_conn = None
    for conn in data.get("connections", []):
        if conn.get("id") == conn_id:
            target_conn = conn
            break

    if not target_conn:
        return None

    target_conn["intermediate_waypoints"] = []
    target_conn["has_explicit_geometry"] = False
    target_conn["status"] = "confirmed_pending_geometry"
    target_conn["measured_distance_m"] = None

    save_confirmed_connections(data)
    return target_conn
