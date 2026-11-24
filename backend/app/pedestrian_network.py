"""
Pedestrian Network Module for LPU Wayfinder (Final Navigation & Phase 2B Integration)
=====================================================================================
Constructs a reliable pedestrian graph from real OsmAnd GPX survey recordings and
user-confirmed physical walkway connections.

Key Geospatial Principles:
- All 4 original GPX tracks are loaded from data/survey_analysis/verified_tracks_overlay.geojson
  as user-confirmed survey evidence physically walked by the surveyor.
- Inter-recording interruptions are loaded from data/confirmed_connections.json.
- Connections are confirmed physically traversable by the surveyor, but if exact path
  geometry between recording endpoints has not been supplied (has_explicit_geometry=False),
  endpoints are NOT connected with fabricated straight lines, and exact directions across
  that link remain disabled.
- Once geometry is explicitly confirmed via admin waypoints or link approval, graph nodes
  are connected and shortest-path routing traverses the unified network.
- Distinguishes GPX-recorded edges, outdoor connection walkways, and indoor corridors.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import networkx as nx

from .connections_store import (
    load_confirmed_connections,
    get_connections_file_path,
    haversine_distance_m
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "survey_analysis"
DEFAULT_GEOJSON_PATH = DATA_DIR / "verified_tracks_overlay.geojson"
DEFAULT_REPORT_PATH = DATA_DIR / "gpx_analysis_report.json"


class PedestrianNetwork:
    """
    Pedestrian Network Graph built from real surveyed campus tracks and
    explicitly confirmed physical connections.
    """

    def __init__(
        self,
        geojson_path: Optional[Path] = None,
        report_path: Optional[Path] = None,
        connections_path: Optional[Path] = None,
        survey_confirmed: bool = True
    ):
        self.geojson_path = geojson_path or DEFAULT_GEOJSON_PATH
        self.report_path = report_path or DEFAULT_REPORT_PATH
        self.connections_path = connections_path or get_connections_file_path()
        self.survey_confirmed = survey_confirmed
        self.graph = nx.Graph()
        self.tracks_metadata: List[Dict[str, Any]] = []
        self.unrecorded_gaps: List[Dict[str, Any]] = []
        self.confirmed_connections: List[Dict[str, Any]] = []
        self.total_recorded_points: int = 0
        self.total_recorded_distance_m: float = 0.0
        self.verified_segment_count: int = 0
        self.unverified_segment_count: int = 0
        self._build_network()

    def _build_network(self) -> None:
        """Construct the NetworkX graph from GeoJSON survey tracks and confirmed connections."""
        self.graph.clear()
        self.tracks_metadata.clear()
        self.unrecorded_gaps.clear()
        self.confirmed_connections.clear()
        self.total_recorded_points = 0
        self.total_recorded_distance_m = 0.0
        self.verified_segment_count = 0
        self.unverified_segment_count = 0

        if not self.geojson_path.exists():
            return

        # Check durable verification store for approved evidence
        from .verification_store import load_durable_evidence
        approved_evidence = [e for e in load_durable_evidence() if e.get("status") == "approved"]
        approved_track_ids = {str(e.get("target_id")) for e in approved_evidence if e.get("target_type") == "track"}

        with open(self.geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        track_features = [
            f for f in features
            if f.get("geometry", {}).get("type") == "LineString"
            and f.get("properties", {}).get("type") == "recorded_track"
        ]

        # 1. Load the 4 OsmAnd GPX recordings
        for track_idx, feat in enumerate(track_features):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])
            track_name = props.get("name", f"track_{track_idx + 1}")
            segment_label = props.get("segment_label", f"Segment {track_idx + 1}")
            track_id = f"track_{track_idx}"

            # Tracks are verified if surveyor_confirmed is active or approved via Phase 2B
            is_verified = self.survey_confirmed or bool(props.get("verified", False)) or (track_id in approved_track_ids)

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
                    verified=is_verified,
                    source="osm_and_gpx",
                    is_indoor=False
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
                        segment_label=segment_label,
                        source="gpx_recording",
                        is_indoor=False
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

        # 2. Load unrecorded gap definitions for status reporting
        self._load_unrecorded_gaps()

        # 3. Load confirmed connections and integrate defined geometries into graph
        self._integrate_confirmed_connections()

    def _load_unrecorded_gaps(self) -> None:
        """Load or derive physical unrecorded gaps between consecutive recordings."""
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
                        "status": "user_confirmed_interruption",
                        "note": g.get("note", "Physical path between recordings.")
                    })
                return
            except Exception:
                pass

        # Fallback if report missing
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
                "status": "user_confirmed_interruption",
                "note": "Recording pause between walked tracks."
            })

    def _integrate_confirmed_connections(self) -> None:
        """
        Integrate confirmed physical connections from confirmed_connections.json.
        IMPORTANT: Endpoints are ONLY connected in the NetworkX graph when explicit
        geometry has been confirmed (has_explicit_geometry=True). Straight-line gaps
        are never assumed as measured paths.
        """
        if self.connections_path and Path(self.connections_path).exists():
            try:
                with open(self.connections_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = load_confirmed_connections()
        else:
            data = load_confirmed_connections()
        self.confirmed_connections = data.get("connections", [])

        for conn in self.confirmed_connections:
            conn_id = conn.get("id")
            from_node = conn.get("from_node")
            to_node = conn.get("to_node")
            has_geom = conn.get("has_explicit_geometry", False)
            is_indoor = conn.get("is_indoor", False)
            conn_name = conn.get("name", f"Connection {conn_id}")

            if not has_geom:
                # Do not connect graph nodes without explicit geometry
                continue

            if not self.graph.has_node(from_node) or not self.graph.has_node(to_node):
                continue

            wps = conn.get("intermediate_waypoints", [])
            if wps:
                prev = from_node
                for idx, wp in enumerate(wps):
                    wp_node = f"{conn_id}_wp_{idx}"
                    self.graph.add_node(
                        wp_node,
                        lat=wp[0],
                        lon=wp[1],
                        is_waypoint=True,
                        verified=True,
                        source="manual_waypoint",
                        is_indoor=is_indoor,
                        connection_id=conn_id,
                        segment_label=conn_name
                    )
                    prev_lat = self.graph.nodes[prev]["lat"]
                    prev_lon = self.graph.nodes[prev]["lon"]
                    seg_dist = haversine_distance_m(prev_lat, prev_lon, wp[0], wp[1])
                    self.graph.add_edge(
                        prev,
                        wp_node,
                        weight=seg_dist,
                        distance_m=round(seg_dist, 2),
                        verified=True,
                        source="manual_confirmed_connection",
                        connection_id=conn_id,
                        is_indoor=is_indoor,
                        segment_label=conn_name
                    )
                    self.verified_segment_count += 1
                    prev = wp_node

                # Final segment from last waypoint to to_node
                prev_lat = self.graph.nodes[prev]["lat"]
                prev_lon = self.graph.nodes[prev]["lon"]
                to_lat = self.graph.nodes[to_node]["lat"]
                to_lon = self.graph.nodes[to_node]["lon"]
                final_dist = haversine_distance_m(prev_lat, prev_lon, to_lat, to_lon)
                self.graph.add_edge(
                    prev,
                    to_node,
                    weight=final_dist,
                    distance_m=round(final_dist, 2),
                    verified=True,
                    source="manual_confirmed_connection",
                    connection_id=conn_id,
                    is_indoor=is_indoor,
                    segment_label=conn_name
                )
                self.verified_segment_count += 1
            else:
                # Direct link confirmed between from_node and to_node
                from_lat = self.graph.nodes[from_node]["lat"]
                from_lon = self.graph.nodes[from_node]["lon"]
                to_lat = self.graph.nodes[to_node]["lat"]
                to_lon = self.graph.nodes[to_node]["lon"]
                direct_dist = haversine_distance_m(from_lat, from_lon, to_lat, to_lon)
                self.graph.add_edge(
                    from_node,
                    to_node,
                    weight=direct_dist,
                    distance_m=round(direct_dist, 2),
                    verified=True,
                    source="manual_confirmed_connection",
                    connection_id=conn_id,
                    is_indoor=is_indoor,
                    segment_label=conn_name
                )
                self.verified_segment_count += 1

    def get_connected_components(self) -> List[List[str]]:
        """Return the list of connected components in the pedestrian graph."""
        return list(nx.connected_components(self.graph))

    def get_network_status(self) -> Dict[str, Any]:
        """
        Produce comprehensive status of the pedestrian network.
        Directly powers GET /api/network/status.
        """
        components = self.get_connected_components()
        component_count = len(components)

        # Routing is considered fully enabled when all components are unified
        # into 1 connected component with verified/confirmed geometry.
        component_count = len(components)
        has_pending_geometries = any(
            not c.get("has_explicit_geometry", False) for c in self.confirmed_connections
        )
        routing_enabled = (self.verified_segment_count > 0 and component_count == 1)

        return {
            "recorded_track_count": len(self.tracks_metadata),
            "recorded_point_count": self.total_recorded_points,
            "recorded_distance_meters": self.total_recorded_distance_m,
            "verified_segment_count": self.verified_segment_count,
            "unverified_segment_count": self.unverified_segment_count,
            "disconnected_components_count": component_count,
            "tracks": self.tracks_metadata,
            "unrecorded_gaps": self.unrecorded_gaps,
            "confirmed_connections": self.confirmed_connections,
            "routing_status": {
                "available": routing_enabled,
                "public_navigation_ready": not has_pending_geometries,
                "has_pending_geometries": has_pending_geometries,
                "reason": (
                    "All 4 tracks are user-confirmed survey evidence. "
                    + (
                        f"{sum(1 for c in self.confirmed_connections if not c.get('has_explicit_geometry', False))} "
                        "connections have pending path geometry."
                        if has_pending_geometries else "All connections have defined geometry."
                    )
                ),
                "verified_coverage_meters": self.total_recorded_distance_m,
                "unverified_coverage_meters": 0.0
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
        Snap a user GPS position or location to the nearest pedestrian network node.
        Applies a maximum distance threshold and accounts for GPS accuracy.
        """
        if self.graph.number_of_nodes() == 0:
            return {
                "snapped": False,
                "node_id": None,
                "distance_m": None,
                "reason": "Pedestrian network has no nodes."
            }

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
        If a continuous path exists over recorded and defined geometry, returns
        exact shortest path, distance, duration, and segment step guidance.
        If nodes are separated by an undefined connection, returns clear unavailable
        message explaining that the link is confirmed traversable but pending geometry.
        """
        if not self.graph.has_node(origin_node) or not self.graph.has_node(destination_node):
            return {
                "available": False,
                "reason_code": "NODE_NOT_FOUND",
                "message": "Origin or destination node not found in network graph.",
                "distance": None,
                "duration": None,
                "path_nodes": None,
                "coordinates": None
            }

        if origin_node == destination_node:
            node_data = self.graph.nodes[origin_node]
            return {
                "available": True,
                "message": "You have arrived at your destination.",
                "distance": 0.0,
                "duration": 0,
                "duration_text": "0 min",
                "path_nodes": [origin_node],
                "coordinates": [[node_data["lon"], node_data["lat"]]],
                "segments": [],
                "has_indoor": False
            }

        if only_verified:
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
                "reason_code": "UNVERIFIED_NODES",
                "message": "Walking route not yet available. Pathway is awaiting verification.",
                "distance": None,
                "duration": None,
                "path_nodes": None,
                "coordinates": None
            }

        # Check if continuous path exists
        if not nx.has_path(subgraph, origin_node, destination_node):
            # Inspect if separated by an interruption whose geometry is pending
            for conn in self.confirmed_connections:
                from_n = conn.get("from_node")
                to_n = conn.get("to_node")
                if not conn.get("has_explicit_geometry", False):
                    # Check if origin is connected to from_n and dest to to_n (or vice versa)
                    can_reach_from = (origin_node == from_n or (subgraph.has_node(from_n) and nx.has_path(subgraph, origin_node, from_n)))
                    can_reach_to = (destination_node == to_n or (subgraph.has_node(to_n) and nx.has_path(subgraph, to_n, destination_node)))

                    can_reach_from_rev = (origin_node == to_n or (subgraph.has_node(to_n) and nx.has_path(subgraph, origin_node, to_n)))
                    can_reach_to_rev = (destination_node == from_n or (subgraph.has_node(from_n) and nx.has_path(subgraph, from_n, destination_node)))

                    if (can_reach_from and can_reach_to) or (can_reach_from_rev and can_reach_to_rev):
                        conn_name = conn.get("name", "pathway link")
                        is_indoor = conn.get("is_indoor", False)
                        gap_m = conn.get("straight_line_gap_m", 0.0)
                        desc = "indoor corridor" if is_indoor else "outdoor walkway"
                        return {
                            "available": False,
                            "reason_code": "CONNECTION_GEOMETRY_PENDING",
                            "connection_id": conn.get("id"),
                            "connection_name": conn_name,
                            "is_indoor": is_indoor,
                            "straight_line_gap_m": gap_m,
                            "message": (
                                f"Walking route not available across {conn_name}. "
                                f"The surveyor confirmed this {desc} is physically traversable, but its exact path geometry "
                                f"({round(gap_m, 1)}m unrecorded gap) is awaiting waypoint definition in admin. "
                                "Exact directions remain disabled until waypoints are provided."
                            ),
                            "distance": None,
                            "duration": None,
                            "path_nodes": None,
                            "coordinates": None
                        }

            return {
                "available": False,
                "reason_code": "DISCONNECTED_COMPONENTS",
                "message": "No continuous path exists between nodes. The network contains unrecorded physical gaps.",
                "distance": None,
                "duration": None,
                "path_nodes": None,
                "coordinates": None
            }

        # Path exists!
        path = nx.shortest_path(subgraph, origin_node, destination_node, weight="weight")
        dist = nx.shortest_path_length(subgraph, origin_node, destination_node, weight="weight")
        duration_sec = max(10, int(dist / 1.2))  # 1.2 m/s standard walking speed

        # Construct coordinate polyline [lon, lat]
        coords = [
            [self.graph.nodes[n]["lon"], self.graph.nodes[n]["lat"]]
            for n in path
        ]

        # Construct step-by-step guidance segments
        segments: List[Dict[str, Any]] = []
        if len(path) > 1:
            curr_type = None
            curr_label = None
            curr_indoor = False
            curr_dist = 0.0
            curr_pts = [coords[0]]

            for idx in range(len(path) - 1):
                u, v = path[idx], path[idx + 1]
                edge_data = subgraph.get_edge_data(u, v) or {}
                edge_type = edge_data.get("source", "gpx_recording")
                edge_label = edge_data.get("segment_label", "Campus Walkway")
                edge_indoor = bool(edge_data.get("is_indoor", False))
                edge_weight = edge_data.get("weight", 0.0)

                if curr_type is None:
                    curr_type = edge_type
                    curr_label = edge_label
                    curr_indoor = edge_indoor
                    curr_dist = edge_weight
                    curr_pts.append(coords[idx + 1])
                elif edge_type == curr_type and edge_indoor == curr_indoor and edge_label == curr_label:
                    curr_dist += edge_weight
                    curr_pts.append(coords[idx + 1])
                else:
                    # Flush segment
                    segments.append({
                        "label": curr_label,
                        "type": curr_type,
                        "is_indoor": curr_indoor,
                        "distance_m": round(curr_dist, 1),
                        "instruction": (
                            f"Pass through {curr_label} ({round(curr_dist, 1)}m)"
                            if curr_indoor else f"Walk {round(curr_dist, 1)}m along {curr_label}"
                        ),
                        "coordinates": curr_pts
                    })
                    curr_type = edge_type
                    curr_label = edge_label
                    curr_indoor = edge_indoor
                    curr_dist = edge_weight
                    curr_pts = [coords[idx], coords[idx + 1]]

            if curr_type is not None:
                segments.append({
                    "label": curr_label,
                    "type": curr_type,
                    "is_indoor": curr_indoor,
                    "distance_m": round(curr_dist, 1),
                    "instruction": (
                        f"Pass through {curr_label} ({round(curr_dist, 1)}m)"
                        if curr_indoor else f"Walk {round(curr_dist, 1)}m along {curr_label}"
                    ),
                    "coordinates": curr_pts
                })

        return {
            "available": True,
            "message": "Walking route found.",
            "distance": round(dist, 1),
            "duration": duration_sec,
            "duration_text": f"{math.ceil(duration_sec / 60)} min",
            "path_nodes": path,
            "coordinates": coords,
            "segments": segments,
            "has_indoor": any(s.get("is_indoor") for s in segments)
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
