"""
Unit tests for LPU Wayfinder Pedestrian Routing Network Module (Phase 2A).
Validates graph construction, geodesic edge calculation, disconnected components,
gap preservation, GPS snapping thresholds, and unverified route prevention.
Strictly non-destructive: does not modify or delete SQLite records or raw GPX files.
"""

import sys
import os
from pathlib import Path
import networkx as nx

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.pedestrian_network import PedestrianNetwork, haversine_distance_m

results = []

def run_test(name, fn):
    try:
        fn()
        results.append((name, "PASSED", ""))
    except Exception as e:
        results.append((name, "FAILED", str(e)))

net = PedestrianNetwork()

# Test 1: Graph Construction
def test_1_graph_construction():
    assert net.graph is not None, "Graph must not be None"
    num_nodes = net.graph.number_of_nodes()
    num_edges = net.graph.number_of_edges()
    assert num_nodes == 263, f"Expected 263 nodes, got {num_nodes}"
    assert num_edges == 259, f"Expected 259 edges, got {num_edges}"
    assert len(net.tracks_metadata) == 4, f"Expected 4 tracks, got {len(net.tracks_metadata)}"
    track_names = [t["name"] for t in net.tracks_metadata]
    assert len(track_names) == 4
    assert all(".gpx" in name.lower() for name in track_names)

# Test 2: Geodesic Distance Edge Calculation
def test_2_geodesic_distance_calculation():
    total_dist = 0.0
    for u, v, data in net.graph.edges(data=True):
        weight = data.get("weight", 0.0)
        assert weight > 0, f"Edge ({u}, {v}) must have positive length, got {weight}"
        # Recalculate distance with haversine formula
        n1 = net.graph.nodes[u]
        n2 = net.graph.nodes[v]
        calc = haversine_distance_m(n1["lat"], n1["lon"], n2["lat"], n2["lon"])
        assert abs(weight - calc) < 0.01, f"Mismatch in edge weight calculation: {weight} vs {calc}"
        total_dist += weight

    # Verify total distance matches ground truth within 1 meter
    assert abs(total_dist - 1734.03) < 1.0, f"Total distance {total_dist:.2f}m deviated from 1734.03m"

# Test 3: Disconnected Components Topology
def test_3_disconnected_components():
    components = list(nx.connected_components(net.graph))
    assert len(components) == 4, f"Expected exactly 4 disconnected components, found {len(components)}"
    comp_sizes = sorted([len(c) for c in components])
    # Sizes correspond to tracks: B (13), C (14), D (98), A (138)
    assert comp_sizes == [13, 14, 98, 138], f"Unexpected component sizes: {comp_sizes}"

# Test 4: Missing Connections (Gaps) Preserved
def test_4_missing_connections_preserved():
    # Gap 1: No path between Track A and Track B
    node_a_end = "trk0_137"
    node_b_start = "trk1_0"
    assert not nx.has_path(net.graph, node_a_end, node_b_start), "Track A and Track B must NOT have an edge or path"

    # Gap 2: No path between Track B and Track C
    node_b_end = "trk1_12"
    node_c_start = "trk2_0"
    assert not nx.has_path(net.graph, node_b_end, node_c_start), "Track B and Track C must NOT have an edge or path"

    # Gap 3: No path through Block 34 (Track C to Track D)
    node_c_end = "trk2_13"
    node_d_start = "trk3_0"
    assert not nx.has_path(net.graph, node_c_end, node_d_start), "Track C and Track D must NOT have an edge or path"

# Test 5: Unverified Route Prevention
def test_5_unverified_route_prevention():
    # Inside Track A, path exists in raw graph, but verified segments = 0
    start_node = "trk0_0"
    end_node = "trk0_50"
    route = net.calculate_shortest_path(start_node, end_node, only_verified=True)
    assert route["available"] is False, "Route must not be available when only_verified=True"
    msg = route["message"].lower()
    assert "awaiting" in msg or "unverified" in msg
    assert net.verified_segment_count == 0, f"Verified segment count must be 0, got {net.verified_segment_count}"

# Test 6: GPS Snapping Threshold and Accuracy Check
def test_6_gps_snapping_thresholds():
    # 1. Close point (exactly on Track A start node trk0_0) with good accuracy
    node0 = net.graph.nodes["trk0_0"]
    snap1 = net.snap_to_network(node0["lat"], node0["lon"], max_distance_m=30.0, accuracy_m=5.0)
    assert snap1["snapped"] is True, f"Should snap to node within 30m, got {snap1}"
    assert snap1["node_id"] == "trk0_0"
    assert snap1["distance_m"] < 0.1, f"Snapping distance should be <0.1m, got {snap1['distance_m']}"

    # 2. Point far away (>1 km from campus)
    snap2 = net.snap_to_network(31.3000, 75.8000, max_distance_m=30.0, accuracy_m=5.0)
    assert snap2["snapped"] is False, "Should reject snapping when distance > 30m"
    assert "exceeding" in snap2["reason"].lower() or "away" in snap2["reason"].lower()

    # 3. Point close but GPS accuracy is poor (>50m)
    snap3 = net.snap_to_network(node0["lat"], node0["lon"], max_distance_m=30.0, accuracy_m=65.0)
    assert snap3["snapped"] is False, "Should reject snapping when GPS accuracy > 50m"
    assert "poor" in snap3["reason"].lower() or "accuracy" in snap3["reason"].lower()

# Test 7: Routing API Response Schema Compatibility
def test_7_api_response_schema():
    res = net.calculate_shortest_path("trk0_0", "trk1_0")
    required_keys = ["available", "message", "distance", "duration", "path_nodes"]
    for k in required_keys:
        assert k in res, f"Response missing key: {k}"
    assert res["distance"] is None
    assert res["duration"] is None
    assert res["available"] is False

# Test 8: Network Status Ground Truth Verification
def test_8_network_status_ground_truth():
    status = net.get_network_status()
    assert status["recorded_track_count"] == 4, f"Expected 4 tracks, got {status['recorded_track_count']}"
    assert status["recorded_point_count"] == 263, f"Expected 263 points, got {status['recorded_point_count']}"
    assert abs(status["recorded_distance_meters"] - 1734.03) < 1.0
    assert status["disconnected_components_count"] == 4
    assert status["verified_segment_count"] == 0
    assert status["routing_status"]["available"] is False
    assert len(status["unrecorded_gaps"]) == 3
    # Check gap 3 is the Block 34 indoor passage
    gap3 = status["unrecorded_gaps"][2]
    assert abs(gap3["displacement_meters"] - 73.63) < 0.1
    assert gap3.get("is_indoor_corridor") is True

# Register all tests
run_test("1. Graph Construction (263 nodes, 259 edges, 4 tracks)", test_1_graph_construction)
run_test("2. Geodesic Edge Distance Calculation (1734.03m ground truth)", test_2_geodesic_distance_calculation)
run_test("3. Disconnected Components Topology (4 isolated components)", test_3_disconnected_components)
run_test("4. Missing Connections / Unrecorded Gaps Preserved (no fabricated edges)", test_4_missing_connections_preserved)
run_test("5. Unverified Route Prevention (strict safety, 0 verified edges)", test_5_unverified_route_prevention)
run_test("6. GPS Snapping Thresholds (30m threshold, 50m accuracy cutoff)", test_6_gps_snapping_thresholds)
run_test("7. Route API Response Compatibility (clean schema compliance)", test_7_api_response_schema)
run_test("8. Network Status Report Matches Survey Evidence", test_8_network_status_ground_truth)

print("\n" + "=" * 70)
print("PEDESTRIAN ROUTING NETWORK (PHASE 2A) UNIT TESTS")
print("=" * 70)
for name, status, err in results:
    icon = "PASS" if status == "PASSED" else "FAIL"
    print(f"[{icon}] {name}")
    if err:
        print(f"       Error: {err}")
print("=" * 70)
passed_count = sum(1 for _, s, _ in results if s == "PASSED")
print(f"Summary: {passed_count}/{len(results)} tests passed.")
print("=" * 70)

if passed_count != len(results):
    sys.exit(1)
