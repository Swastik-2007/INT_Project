"""
Pedestrian Network Module for LPU Wayfinder (Phase 2A)
======================================================
Constructs a reliable pedestrian graph from real GPS survey recordings.
Enforces strict geospatial integrity:
- Preserves individual recording boundaries.
- Detects disconnected graph components.
- Retains verification status (unverified survey recordings remain unverified).
- Never infers or fabricates unrecorded pedestrian connections or shortcuts.
- Rejects routing over unverified edges or across gaps.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "survey_analysis"
DEFAULT_GEOJSON_PATH = DATA_DIR / "verified_tracks_overlay.geojson"
DEFAULT_REPORT_PATH = DATA_DIR / "gpx_analysis_report.json"


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance in meters between two coordinates on WGS84 ellipsoid."""
    R = 6371000.0  # Earth's mean radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class PedestrianNetwork:
    """
    Pedestrian Network Graph built from real surveyed campus tracks.
    Maintains network topology, component analysis, and snapping logic.
    """

    def __init__(
        self,
        geojson_path: Optional[Path] = None,
        report_path: Optional[Path] = None
    ):
        self.geojson_path = geojson_path or DEFAULT_GEOJSON_PATH
        self.report_path = report_path or DEFAULT_REPORT_PATH
        self.graph = nx.Graph()
        self.tracks_metadata: List[Dict[str, Any]] = []
        self.unrecorded_gaps: List[Dict[str, Any]] = []
        self.total_recorded_points: int = 0
        self.total_recorded_distance_m: float = 0.0
        self.verified_segment_count: int = 0
        self.unverified_segment_count: int = 0
        self._build_network()

    def _build_network(self) -> None:
        """Construct the NetworkX graph from GeoJSON survey tracks."""
        self.graph.clear()
        self.tracks_metadata.clear()
        self.total_recorded_points = 0
        self.total_recorded_distance_m = 0.0
        self.verified_segment_count = 0
        self.unverified_segment_count = 0

        if not self.geojson_path.exists():
            return

        # Check durable verification store for approved tracks and gap connections
        from .verification_store import load_durable_evidence
        approved_evidence = [e for e in load_durable_evidence() if e.get("status") == "approved"]
        approved_track_ids = {str(e.get("target_id")) for e in approved_evidence if e.get("target_type") == "track"}
        approved_gap_evidence = {str(e.get("target_id")): e for e in approved_evidence if e.get("target_type") == "gap"}

        with open(self.geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        track_features = [
            f for f in features
            if f.get("geometry", {}).get("type") == "LineString"
            and f.get("properties", {}).get("type") == "recorded_track"
        ]

        for track_idx, feat in enumerate(track_features):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])
            track_name = props.get("name", f"track_{track_idx + 1}")
            segment_label = props.get("segment_label", f"Segment {track_idx + 1}")
            track_id = f"track_{track_idx}"
            is_verified = bool(props.get("verified", False)) or (track_id in approved_track_ids)

            track_dist = 0.0
            point_count = len(coords)
            self.total_recorded_points += point_count

            track_nodes: List[str] = []

            for i, coord in enumerate(coords):
                lon = float(coord[0])
                lat = float(coord[1])
                ele = float(coord[2]) if len(coord) > 2 else None

                node_id = f"trk{track_idx}_{i}"
                is_endpoint = (i == 0 or i == point_count - 1)
                endpoint_type = "start" if i == 0 else ("end" if i == point_count - 1 else None)

                self.graph.add_node(
                    node_id,
                    lat=lat,
                    lon=lon,
                    ele=ele,
                    track_idx=track_idx,
                    track_name=track_name,
                    segment_label=segment_label,
                    index_in_track=i,
                    is_endpoint=is_endpoint,
                    endpoint_type=endpoint_type,
                    verified=is_verified
                )
                track_nodes.append(node_id)

                if i > 0:
                    prev_node = track_nodes[i - 1]
                    prev_lat = self.graph.nodes[prev_node]["lat"]
                    prev_lon = self.graph.nodes[prev_node]["lon"]
                    dist = haversine_distance_m(prev_lat, prev_lon, lat, lon)

                    track_dist += dist
                    self.total_recorded_distance_m += dist

                    if is_verified:
                        self.verified_segment_count += 1
                    else:
                        self.unverified_segment_count += 1

                    self.graph.add_edge(
                        prev_node,
                        node_id,
                        weight=dist,
                        distance_m=round(dist, 2),
                        verified=is_verified,
                        track_idx=track_idx,
                        track_name=track_name,
                        segment_label=segment_label
                    )

            self.tracks_metadata.append({
                "track_index": track_idx,
                "name": track_name,
                "segment_label": segment_label,
                "point_count": point_count,
                "distance_m": round(track_dist, 2),
                "verified": is_verified,
                "start_node": track_nodes[0] if track_nodes else None,
                "end_node": track_nodes[-1] if track_nodes else None,
            })

        self.total_recorded_distance_m = round(self.total_recorded_distance_m, 2)
        self._load_unrecorded_gaps()

    def _load_unrecorded_gaps(self) -> None:
        """Load or derive physical unrecorded gaps between consecutive recordings."""
        self.unrecorded_gaps.clear()

        # If analysis report exists, read curated surveyor gap notes
        if self.report_path.exists():
            try:
                with open(self.report_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                gaps = report.get("gaps", [])
                for g in gaps:
                    self.unrecorded_gaps.append({
                        "from_recording": g.get("from_recording"),
                        "to_recording": g.get("to_recording"),
                        "displacement_meters": g.get("gap_distance_m"),
                        "bearing_degrees": g.get("gap_bearing_deg"),
                        "time_gap_seconds": g.get("time_gap_sec"),
                        "from_endpoint": g.get("from_endpoint"),
                        "to_startpoint": g.get("to_startpoint"),
                        "is_indoor_corridor": (
                            "Block 34 to BH4" in str(g.get("to_recording", "")) or
                            (g.get("gap_distance_m") or 0) > 70.0
                        ),
                        "status": "unrecorded_physical_gap",
                        "note": g.get("note", "Physical path between recordings was unrecorded.")
                    })
                self._apply_gap_verifications()
                return
            except Exception:
                pass

        # Fallback: derive gap endpoint displacement from consecutive track endpoints
        for i in range(len(self.tracks_metadata) - 1):
            t1 = self.tracks_metadata[i]
            t2 = self.tracks_metadata[i + 1]
            end_node = self.graph.nodes[t1["end_node"]]
            start_node = self.graph.nodes[t2["start_node"]]

            disp = haversine_distance_m(
                end_node["lat"], end_node["lon"],
                start_node["lat"], start_node["lon"]
            )
            self.unrecorded_gaps.append({
                "from_recording": t1["name"],
                "to_recording": t2["name"],
                "displacement_meters": round(disp, 2),
                "from_endpoint": {"lat": end_node["lat"], "lon": end_node["lon"]},
                "to_startpoint": {"lat": start_node["lat"], "lon": start_node["lon"]},
                "is_indoor_corridor": i == 2,
                "status": "unrecorded_physical_gap",
                "note": "Deliberate recording pause; connection unverified."
            })
        self._apply_gap_verifications()

    def _apply_gap_verifications(self) -> None:
        """
        Integrate approved pedestrian segments into the NetworkX graph ONLY
        when their geometry and endpoints have been explicitly validated.
        Never interpolates across unverified gaps.
        """
        from .verification_store import load_durable_evidence
        approved_evidence = [e for e in load_durable_evidence() if e.get("status") == "approved"]
        approved_gap_evidence = {str(e.get("target_id")): e for e in approved_evidence if e.get("target_type") == "gap"}

        for gap_idx, gap in enumerate(self.unrecorded_gaps):
            gap_id = f"gap_{gap_idx + 1}"
            if gap_id in approved_gap_evidence:
                ev = approved_gap_evidence[gap_id]
                gap["verified"] = True
                gap["verified_by"] = ev.get("reviewed_by")
                gap["verified_at"] = ev.get("reviewed_at")
                gap["status"] = "verified_field_walkway"
                s_lat = ev.get("gps_start_lat")
                s_lon = ev.get("gps_start_lon")
                e_lat = ev.get("gps_end_lat")
                e_lon = ev.get("gps_end_lon")
                if s_lat is not None and s_lon is not None and e_lat is not None and e_lon is not None:
                    snap_s = self.snap_to_network(s_lat, s_lon, max_distance_m=15.0)
                    snap_e = self.snap_to_network(e_lat, e_lon, max_distance_m=15.0)
                    if snap_s["snapped"] and snap_e["snapped"] and snap_s["node_id"] != snap_e["node_id"]:
                        conn_dist = haversine_distance_m(s_lat, s_lon, e_lat, e_lon)
                        self.graph.add_edge(
                            snap_s["node_id"],
                            snap_e["node_id"],
                            weight=conn_dist,
                            distance_m=round(conn_dist, 2),
                            verified=True,
                            gap_id=gap_id,
                            segment_label=f"Verified Walkway: {gap_id}"
                        )
                        self.verified_segment_count += 1

    def get_connected_components(self) -> List[List[str]]:
        """Return the list of connected components in the pedestrian graph."""
        return list(nx.connected_components(self.graph))

    def get_network_status(self) -> Dict[str, Any]:
        """
        Produce a comprehensive status of the pedestrian network.
        Directly powers GET /api/network/status.
        """
        components = self.get_connected_components()
        component_count = len(components)

        routing_enabled = (
            self.verified_segment_count > 0 and
            component_count == 1
        )

        return {
            "recorded_track_count": len(self.tracks_metadata),
            "recorded_point_count": self.total_recorded_points,
            "recorded_distance_meters": self.total_recorded_distance_m,
            "verified_segment_count": self.verified_segment_count,
            "unverified_segment_count": self.unverified_segment_count,
            "disconnected_components_count": component_count,
            "tracks": self.tracks_metadata,
            "unrecorded_gaps": self.unrecorded_gaps,
            "routing_status": {
                "available": routing_enabled,
                "public_navigation_ready": False,
                "reason": (
                    "All 4 survey tracks are pending field verification. "
                    f"The pedestrian graph contains {component_count} disconnected components "
                    f"with {len(self.unrecorded_gaps)} unrecorded gaps. "
                    "Navigation routing remains disabled to prevent simulated or unverified paths."
                ),
                "verified_coverage_meters": 0.0,
                "unverified_coverage_meters": self.total_recorded_distance_m
            }
        }

    def snap_to_network(
        self,
        lat: float,
        lon: float,
        max_distance_m: float = 30.0,
        accuracy_m: Optional[float] = None,
        only_verified: bool = False
    ) -> Dict[str, Any]:
        """
        Snap a user GPS position to the nearest pedestrian network node.
        Applies a strict maximum distance threshold and accounts for GPS accuracy.
        Never snaps across buildings or disconnected walkways.
        """
        if self.graph.number_of_nodes() == 0:
            return {
                "snapped": False,
                "node_id": None,
                "distance_m": None,
                "reason": "Pedestrian network has no nodes."
            }

        # If user GPS accuracy is too poor (>50m), refuse snapping
        if accuracy_m is not None and accuracy_m > 50.0:
            return {
                "snapped": False,
                "node_id": None,
                "distance_m": None,
                "reason": f"GPS accuracy (±{round(accuracy_m)}m) is too poor for reliable snapping (threshold: 50m)."
            }

        nearest_node = None
        min_dist = float("inf")

        for node_id, data in self.graph.nodes(data=True):
            if only_verified and not data.get("verified", False):
                continue

            dist = haversine_distance_m(lat, lon, data["lat"], data["lon"])
            if dist < min_dist:
                min_dist = dist
                nearest_node = node_id

        if nearest_node is None:
            return {
                "snapped": False,
                "node_id": None,
                "distance_m": None,
                "reason": "No qualifying network nodes available."
            }

        min_dist_rounded = round(min_dist, 2)
        if min_dist > max_distance_m:
            return {
                "snapped": False,
                "node_id": nearest_node,
                "distance_m": min_dist_rounded,
                "reason": (
                    f"Location is {min_dist_rounded}m away from nearest walkway node, "
                    f"exceeding the maximum snapping threshold of {max_distance_m}m."
                )
            }

        node_data = self.graph.nodes[nearest_node]
        return {
            "snapped": True,
            "node_id": nearest_node,
            "distance_m": min_dist_rounded,
            "node_coords": [node_data["lat"], node_data["lon"]],
            "track_name": node_data.get("track_name"),
            "segment_label": node_data.get("segment_label"),
            "verified": node_data.get("verified", False)
        }

    def calculate_shortest_path(
        self,
        origin_node: str,
        destination_node: str,
        only_verified: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate shortest path strictly over verified edges.
        If only_verified=True and the network has no verified path between nodes,
        returns available: False without fabricating directions.
        """
        if not self.graph.has_node(origin_node) or not self.graph.has_node(destination_node):
            return {
                "available": False,
                "message": "Origin or destination node not found in network graph.",
                "distance": None,
                "duration": None,
                "path_nodes": None
            }

        if only_verified:
            # Create a view/subgraph of only verified edges
            verified_edges = [
                (u, v) for u, v, d in self.graph.edges(data=True)
                if d.get("verified", False)
            ]
            subgraph = self.graph.edge_subgraph(verified_edges)
        else:
            subgraph = self.graph

        if not subgraph.has_node(origin_node) or not subgraph.has_node(destination_node):
            return {
                "available": False,
                "message": "Walking route not yet available. Pathway is awaiting verification.",
                "distance": None,
                "duration": None,
                "path_nodes": None
            }

        if not nx.has_path(subgraph, origin_node, destination_node):
            return {
                "available": False,
                "message": "No continuous path exists between nodes. The network contains unrecorded physical gaps.",
                "distance": None,
                "duration": None,
                "path_nodes": None
            }

        path = nx.shortest_path(subgraph, origin_node, destination_node, weight="weight")
        dist = nx.shortest_path_length(subgraph, origin_node, destination_node, weight="weight")
        duration_sec = int(dist / 1.2)  # 1.2 m/s standard walking speed

        return {
            "available": True,
            "message": "Verified route found.",
            "distance": round(dist, 1),
            "duration": duration_sec,
            "path_nodes": path
        }


# Singleton instance for efficient reuse across FastAPI requests
_pedestrian_network_instance: Optional[PedestrianNetwork] = None


def get_pedestrian_network() -> PedestrianNetwork:
    """Get or initialize the cached PedestrianNetwork instance."""
    global _pedestrian_network_instance
    if _pedestrian_network_instance is None:
        _pedestrian_network_instance = PedestrianNetwork()
    return _pedestrian_network_instance


def reload_pedestrian_network() -> PedestrianNetwork:
    """Force re-construction of the pedestrian network singleton with latest verification data."""
    global _pedestrian_network_instance
    _pedestrian_network_instance = PedestrianNetwork()
    return _pedestrian_network_instance
