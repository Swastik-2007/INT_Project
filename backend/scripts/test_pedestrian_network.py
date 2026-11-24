"""
Unit tests for LPU Wayfinder Pedestrian Routing Network Module
================================================================
Validates both:
- SCENARIO A: Raw Survey / Disconnected Configuration (Original Survey Baseline)
  - 4 original GPX recordings
  - 263 recorded GPS points
  - 1734.03m recorded GPX distance
  - 4 disconnected components without confirmed links
  - No path across missing or undefined connections
  - Navigation blocked across undefined geometry
  - Schema contract for unavailable routes

- SCENARIO B: Configured Connected Navigation (Active Campus Network)
  - Original GPX files unchanged (263 recorded points, 1734.03m recorded distance)
  - 3 manually confirmed connections active (outdoor walkways + Block 34 indoor corridor)
  - 1 single connected pedestrian network component
  - Graph node count includes connection waypoints (264 nodes)
  - Total connected graph distance: 1837.79m (1734.03m recorded GPX + 103.77m connections)
  - BH4 Area -> Main Gate route available: ~1837.8m, ~1531s, indoor corridor segment preserved
  - Schema contract for active routes

Strict isolation: tests run on temporary isolated connection files and never mutate data/confirmed_connections.json.
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
import networkx as nx

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.pedestrian_network import PedestrianNetwork, haversine_distance_m
from app.connections_store import (
    load_confirmed_connections,
    update_connection_geometry,
    reset_connection_geometry
)

results = []

def run_test(name, fn):
    try:
        fn()
        results.append((name, "PASSED", ""))
    except Exception as e:
        results.append((name, "FAILED", str(e)))


# ==============================================================================
# Helper Fixtures: Scenario A and Scenario B Isolated Networks
# ==============================================================================

def get_scenario_a_network():
    """
    Scenario A: Raw survey with all 3 connections pending (has_explicit_geometry: False).
    Creates an isolated temporary confirmed_connections.json without mutating production.
    """
    temp_dir = tempfile.mkdtemp(prefix="lpu_scen_a_")
    temp_file = Path(temp_dir) / "confirmed_connections.json"

    # Baseline disconnected configuration
    raw_conns = {
        "version": "1.0",
        "description": "Scenario A: Disconnected raw survey baseline",
        "connections": [
            {
                "id": "conn_ab",
                "name": "Track A to Track B Connection",
                "from_track": "Main_gate to Admission & class area.gpx",
                "from_node": "trk0_137",
                "from_coords": [31.2531338, 75.7047218],
                "to_track": "Block 30 to 32.gpx",
                "to_node": "trk1_0",
                "to_coords": [31.2529843, 75.7048714],
                "straight_line_gap_m": 21.88,
                "classification": "outdoor_walkway",
                "is_indoor": False,
                "status": "pending_definition",
                "has_explicit_geometry": False,
                "intermediate_waypoints": []
            },
            {
                "id": "conn_bc",
                "name": "Track B to Track C Connection",
                "from_track": "Block 30 to 32.gpx",
                "from_node": "trk1_12",
                "from_coords": [31.2524186, 75.70508],
                "to_track": "Block 32 to 34.gpx",
                "to_node": "trk2_0",
                "to_coords": [31.2523447, 75.7050889],
                "straight_line_gap_m": 8.26,
                "classification": "outdoor_walkway",
                "is_indoor": False,
                "status": "pending_definition",
                "has_explicit_geometry": False,
                "intermediate_waypoints": []
            },
            {
                "id": "conn_cd",
                "name": "Track C to Track D via Block 34 Indoor Corridor",
                "from_track": "Block 32 to 34.gpx",
                "from_node": "trk2_13",
                "from_coords": [31.2515096, 75.7050747],
                "to_track": "Block 34 to BH4.gpx",
                "to_node": "trk3_0",
                "to_coords": [31.2515297, 75.7043005],
                "straight_line_gap_m": 73.63,
                "classification": "indoor_corridor",
                "is_indoor": True,
                "status": "pending_definition",
                "has_explicit_geometry": False,
                "intermediate_waypoints": []
            }
        ]
    }
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(raw_conns, f, indent=2)

    net = PedestrianNetwork(connections_path=temp_file)
    return net, temp_dir


def get_scenario_b_network():
    """
    Scenario B: Connected navigation network with all 3 connections confirmed.
    Loads real confirmed connections into an isolated temporary workspace.
    """
    real_data = load_confirmed_connections()
    temp_dir = tempfile.mkdtemp(prefix="lpu_scen_b_")
    temp_file = Path(temp_dir) / "confirmed_connections.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(real_data, f, indent=2)

    net = PedestrianNetwork(connections_path=temp_file)
    return net, temp_dir


# Initialize isolated networks
net_a, dir_a = get_scenario_a_network()
net_b, dir_b = get_scenario_b_network()


# ==============================================================================
# SCENARIO A TESTS: Raw Survey / Disconnected Configuration
# ==============================================================================

def test_1_scen_a_graph_construction():
    """Scenario A: Graph construction from 4 raw GPX tracks (263 nodes, 259 edges)."""
    assert net_a.graph is not None
    assert net_a.graph.number_of_nodes() == 263, f"Expected 263 nodes, got {net_a.graph.number_of_nodes()}"
    assert net_a.graph.number_of_edges() == 259, f"Expected 259 edges, got {net_a.graph.number_of_edges()}"
    assert len(net_a.tracks_metadata) == 4
    track_names = [t["name"] for t in net_a.tracks_metadata]
    assert all(".gpx" in name.lower() for name in track_names)


def test_2_scen_a_geodesic_distance_calculation():
    """Scenario A: Recorded GPX distance matches ground truth (1734.03m)."""
    total_dist = sum(data.get("weight", 0.0) for _, _, data in net_a.graph.edges(data=True))
    assert abs(total_dist - 1734.03) < 1.0, f"Total distance {total_dist:.2f}m deviated from 1734.03m"
    assert abs(net_a.total_recorded_distance_m - 1734.03) < 1.0


def test_3_scen_a_disconnected_components():
    """Scenario A: Exactly 4 disconnected components without confirmed links."""
    components = list(nx.connected_components(net_a.graph))
    assert len(components) == 4, f"Expected 4 disconnected components, found {len(components)}"
    comp_sizes = sorted([len(c) for c in components])
    assert comp_sizes == [13, 14, 98, 138], f"Unexpected component sizes: {comp_sizes}"


def test_4_scen_a_missing_connections_preserved():
    """Scenario A: Preservation of unrecorded gaps without fabricated edges."""
    assert not nx.has_path(net_a.graph, "trk0_137", "trk1_0"), "Track A and Track B must NOT have an edge"
    assert not nx.has_path(net_a.graph, "trk1_12", "trk2_0"), "Track B and Track C must NOT have an edge"
    assert not nx.has_path(net_a.graph, "trk2_13", "trk3_0"), "Track C and Track D must NOT have an edge"


def test_5_scen_a_undefined_connection_route_prevention():
    """Scenario A: Navigation blocked across undefined connection geometry."""
    route = net_a.calculate_shortest_path("trk0_0", "trk1_0", only_verified=True)
    assert route["available"] is False, "Route must remain disabled across undefined connections"
    assert route.get("reason_code") == "CONNECTION_GEOMETRY_PENDING"
    assert route["distance"] is None
    assert route["duration"] is None


def test_6_scen_a_gps_snapping():
    """Scenario A & B: GPS snapping thresholds (30m threshold, 50m accuracy cutoff)."""
    node0 = net_a.graph.nodes["trk0_0"]
    snap1 = net_a.snap_to_network(node0["lat"], node0["lon"], max_distance_m=30.0, accuracy_m=5.0)
    assert snap1["snapped"] is True
    assert snap1["node_id"] == "trk0_0"
    assert snap1["distance_m"] < 0.1

    # Far away point (>30m)
    snap2 = net_a.snap_to_network(31.3000, 75.8000, max_distance_m=30.0, accuracy_m=5.0)
    assert snap2["snapped"] is False

    # Low accuracy (>50m)
    snap3 = net_a.snap_to_network(node0["lat"], node0["lon"], max_distance_m=30.0, accuracy_m=65.0)
    assert snap3["snapped"] is False


def test_7_scen_a_network_status():
    """Scenario A: Network status reflects 4 disconnected components and routing disabled."""
    status = net_a.get_network_status()
    assert status["recorded_track_count"] == 4
    assert status["recorded_point_count"] == 263
    assert abs(status["recorded_distance_meters"] - 1734.03) < 1.0
    assert status["disconnected_components_count"] == 4
    assert status["routing_status"]["available"] is False
    assert status["routing_status"]["has_pending_geometries"] is True
    assert len(status["unrecorded_gaps"]) == 3


def test_8_scen_a_api_response_schema_disconnected():
    """Scenario A: Route API response contract when route is unavailable."""
    res = net_a.calculate_shortest_path("trk0_0", "trk1_0")
    required_keys = ["available", "message", "distance", "duration", "path_nodes", "reason_code"]
    for k in required_keys:
        assert k in res, f"Response missing key: {k}"
    assert res["available"] is False
    assert res["distance"] is None
    assert res["duration"] is None
    assert res["reason_code"] == "CONNECTION_GEOMETRY_PENDING"


# ==============================================================================
# SCENARIO B TESTS: Configured Connected Navigation
# ==============================================================================

def test_9_scen_b_connected_graph_topology():
    """Scenario B: 3 confirmed connections active, 1 unified connected component."""
    # Original GPX recorded points & distance remain unchanged
    assert net_b.total_recorded_points == 263
    assert abs(net_b.total_recorded_distance_m - 1734.03) < 1.0
    assert len(net_b.tracks_metadata) == 4

    # Graph includes connection waypoints (263 GPX nodes + 1 corridor waypoint = 264 nodes)
    assert net_b.graph.number_of_nodes() == 264, f"Expected 264 nodes, got {net_b.graph.number_of_nodes()}"

    # Connected components is unified into exactly 1
    components = list(nx.connected_components(net_b.graph))
    assert len(components) == 1, f"Expected exactly 1 unified component, got {len(components)}"

    # Total connected graph distance includes original GPX + connection links (~1837.79m)
    total_graph_dist = sum(data.get("weight", 0.0) for _, _, data in net_b.graph.edges(data=True))
    assert abs(total_graph_dist - 1837.79) < 2.0, f"Expected ~1837.79m, got {total_graph_dist:.2f}m"


def test_10_scen_b_connected_paths_across_links():
    """Scenario B: Path exists across all three confirmed connections."""
    assert nx.has_path(net_b.graph, "trk0_137", "trk1_0"), "Connection A->B must connect graph"
    assert nx.has_path(net_b.graph, "trk1_12", "trk2_0"), "Connection B->C must connect graph"
    assert nx.has_path(net_b.graph, "trk2_13", "trk3_0"), "Connection C->D (Block 34) must connect graph"


def test_11_scen_b_bh4_to_main_gate_route():
    """Scenario B: Verified full campus route from BH4 Area to Main Gate (1837.8m, 1531s)."""
    # BH4 Area (trk3_97) to Main Gate (trk0_0)
    route = net_b.calculate_shortest_path("trk3_97", "trk0_0", only_verified=True)
    assert route["available"] is True, "BH4 to Main Gate route must be available"
    assert abs(route["distance"] - 1837.8) < 2.0, f"Expected ~1837.8m, got {route['distance']}"
    assert abs(route["duration"] - 1531) < 10, f"Expected ~1531s, got {route['duration']}"
    assert route["has_indoor"] is True, "Route through Block 34 must flag has_indoor=True"

    # Confirm Block 34 corridor indoor segment is present with explicit metadata
    indoor_segs = [s for s in route["segments"] if s.get("is_indoor")]
    assert len(indoor_segs) > 0, "Expected at least 1 indoor corridor segment"
    assert any("Block 34" in s.get("label", "") for s in indoor_segs)


def test_12_scen_b_api_response_schema_connected():
    """Scenario B: Route API response contract when route is available."""
    res = net_b.calculate_shortest_path("trk3_97", "trk0_0", only_verified=True)
    required_keys = ["available", "message", "distance", "duration", "duration_text", "path_nodes", "coordinates", "segments", "has_indoor"]
    for k in required_keys:
        assert k in res, f"Connected response missing key: {k}"
    assert res["available"] is True
    assert isinstance(res["distance"], float) and res["distance"] > 0
    assert isinstance(res["duration"], int) and res["duration"] > 0
    assert isinstance(res["path_nodes"], list) and len(res["path_nodes"]) > 0
    assert isinstance(res["coordinates"], list) and len(res["coordinates"]) > 0
    assert isinstance(res["segments"], list) and len(res["segments"]) > 0


def test_13_scen_b_network_status_connected():
    """Scenario B: Network status reflects 1 unified component and routing available."""
    status = net_b.get_network_status()
    assert status["recorded_track_count"] == 4
    assert status["recorded_point_count"] == 263
    assert abs(status["recorded_distance_meters"] - 1734.03) < 1.0
    assert status["disconnected_components_count"] == 1
    assert status["routing_status"]["available"] is True
    assert status["routing_status"]["public_navigation_ready"] is True
    assert status["routing_status"]["has_pending_geometries"] is False


def test_14_scen_b_confirmed_connections_store_metadata():
    """Scenario B: Confirmed connections store contains expected metadata."""
    data = load_confirmed_connections()
    conns = data.get("connections", [])
    assert len(conns) == 3
    ids = [c["id"] for c in conns]
    assert ids == ["conn_ab", "conn_bc", "conn_cd"]

    conn_cd = next(c for c in conns if c["id"] == "conn_cd")
    assert conn_cd["is_indoor"] is True
    assert conn_cd["classification"] == "indoor_corridor"
    assert "Block 34" in conn_cd["name"]
    assert conn_cd["has_explicit_geometry"] is True


# ==============================================================================
# Register and Run All Tests
# ==============================================================================

# Scenario A: Raw Survey / Disconnected Baseline
run_test("1. Scenario A: Graph Construction (263 nodes, 259 edges, 4 tracks)", test_1_scen_a_graph_construction)
run_test("2. Scenario A: Geodesic Distance Calculation (1734.03m ground truth)", test_2_scen_a_geodesic_distance_calculation)
run_test("3. Scenario A: Disconnected Components Topology (4 isolated components)", test_3_scen_a_disconnected_components)
run_test("4. Scenario A: Missing Connections Preserved (no fabricated edges)", test_4_scen_a_missing_connections_preserved)
run_test("5. Scenario A: Undefined Connection Route Prevention (blocked across gaps)", test_5_scen_a_undefined_connection_route_prevention)
run_test("6. Scenario A/B: GPS Snapping Thresholds (30m threshold, 50m accuracy cutoff)", test_6_scen_a_gps_snapping)
run_test("7. Scenario A: Network Status Report (4 components, routing disabled)", test_7_scen_a_network_status)
run_test("8. Scenario A: Routing API Response Schema Compatibility (unavailable)", test_8_scen_a_api_response_schema_disconnected)

# Scenario B: Configured Connected Navigation
run_test("9. Scenario B: Connected Graph Topology (264 nodes, 1 component, 1837.79m)", test_9_scen_b_connected_graph_topology)
run_test("10. Scenario B: Connected Paths Across Confirmed Walkways & Corridors", test_10_scen_b_connected_paths_across_links)
run_test("11. Scenario B: BH4 Area to Main Gate Route Verified (1837.8m, 1531s)", test_11_scen_b_bh4_to_main_gate_route)
run_test("12. Scenario B: Routing API Response Schema Compatibility (available)", test_12_scen_b_api_response_schema_connected)
run_test("13. Scenario B: Network Status Report (1 component, routing available)", test_13_scen_b_network_status_connected)
run_test("14. Scenario B: Confirmed Connections Store Metadata (indoor corridor)", test_14_scen_b_confirmed_connections_store_metadata)

# Cleanup isolated directories
try:
    shutil.rmtree(dir_a, ignore_errors=True)
    shutil.rmtree(dir_b, ignore_errors=True)
except Exception:
    pass

print("\n" + "=" * 75)
print("PEDESTRIAN ROUTING NETWORK TEST RESULTS (SCENARIO A & SCENARIO B)")
print("=" * 75)
for name, status, err in results:
    icon = "PASS" if status == "PASSED" else "FAIL"
    print(f"[{icon}] {name}")
    if err:
        print(f"       Error: {err}")
print("=" * 75)
passed_count = sum(1 for _, s, _ in results if s == "PASSED")
print(f"Summary: {passed_count}/{len(results)} tests passed.")
print("=" * 75)

if passed_count != len(results):
    sys.exit(1)
