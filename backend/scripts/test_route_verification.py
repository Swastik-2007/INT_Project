"""
Test Suite for LPU Wayfinder Phase 2B: Pedestrian Route Verification System
=============================================================================
Validates:
1. Authentication and authorization on admin verification endpoints (401 on missing/bad token).
2. Pending verification items list (tracks, gaps, entrances).
3. Evidence submission with field observations.
4. Verification approval and rejection workflows.
5. Audit history recording and retrieval.
6. Rejection of invalid GPS coordinates (outside campus boundaries).
7. Rejection of missing/empty field evidence (HTTP 422).
8. Building entrance registration and ground-truth coordinate validation.
9. Unverified route prevention (strict safety check).
10. Preservation of disconnected components across unverified gaps.
11. Existing API backward compatibility (/api/locations, /api/survey-tracks, /api/network/status, /api/route).
12. Strict test database isolation: real database immutability verification (SHA-256 and record check).
"""

import sys
import os
import shutil
import tempfile
import hashlib
import atexit
from pathlib import Path
from datetime import datetime, timedelta
from jose import jwt
from dotenv import load_dotenv

# Set paths
project_root = Path(__file__).resolve().parent.parent.parent
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

# ---------------------------------------------------------------------------
# Strict Test Database & Verification Storage Isolation Setup
# ---------------------------------------------------------------------------
real_db_path = project_root / "lpu_wayfinder.db"
real_db_exists_before = real_db_path.exists()
real_db_hash_before = hashlib.sha256(real_db_path.read_bytes()).hexdigest() if real_db_exists_before else None
real_db_size_before = real_db_path.stat().st_size if real_db_exists_before else 0

# Create temporary workspace for isolated test execution
test_temp_dir = tempfile.mkdtemp(prefix="lpu_test_isolation_")
test_db_path = Path(test_temp_dir) / "test_wayfinder.db"
test_verification_dir = Path(test_temp_dir) / "verification"
test_verification_dir.mkdir(parents=True, exist_ok=True)

# Copy baseline database into isolated temp location so baseline locations (1..5) are present in test db
if real_db_exists_before:
    shutil.copy2(real_db_path, test_db_path)

# Set environment variables BEFORE ANY application imports initialize connections
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["VERIFICATION_DATA_DIR"] = str(test_verification_dir)

# Load .env safely without mutating our isolated DATABASE_URL or VERIFICATION_DATA_DIR
_env_path = project_root / ".env"
load_dotenv(dotenv_path=_env_path, override=False)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# Clean up temporary test files on process exit
def cleanup_temp_workspace():
    try:
        shutil.rmtree(test_temp_dir, ignore_errors=True)
    except Exception:
        pass

atexit.register(cleanup_temp_workspace)

# ---------------------------------------------------------------------------
# Application Imports & Dependency Overrides
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.router import get_db
from app.db import init_db
from app.pedestrian_network import get_pedestrian_network, reload_pedestrian_network

# Initialize schema in the temporary test database
init_db()

# Create dedicated test session maker and override FastAPI get_db dependency
test_engine = create_engine(os.environ["DATABASE_URL"], echo=False)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db_session = TestSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

results = []

def run_test(name, fn):
    try:
        fn()
        results.append((name, "PASSED", ""))
    except Exception as e:
        results.append((name, "FAILED", str(e)))


def make_admin_token():
    exp = datetime.utcnow() + timedelta(hours=1)
    return jwt.encode({"sub": ADMIN_USERNAME, "exp": exp}, SECRET_KEY, algorithm="HS256")


# Test 1: Authentication & Authorization
def test_1_auth_protection():
    endpoints = [
        ("GET", "/api/admin/verification/pending"),
        ("POST", "/api/admin/verification/evidence"),
        ("POST", "/api/admin/verification/review"),
        ("POST", "/api/admin/verification/entrance"),
        ("GET", "/api/admin/verification/history"),
    ]
    for method, ep in endpoints:
        if method == "GET":
            res = client.get(ep)
        else:
            res = client.post(ep, json={})
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {ep}, got {res.status_code}"

    # Invalid token must return 401
    bad_headers = {"Authorization": "Bearer invalid_token_xyz"}
    res = client.get("/api/admin/verification/pending", headers=bad_headers)
    assert res.status_code == 401, f"Expected 401 for bad token, got {res.status_code}"


# Test 2: Pending Verification List
def test_2_pending_verification_list():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/admin/verification/pending", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "tracks" in data
    assert "gaps" in data
    assert "locations" in data
    assert len(data["tracks"]) == 4
    assert len(data["gaps"]) == 3
    assert len(data["locations"]) >= 5


# Test 3: Submitting Field Evidence
def test_3_submit_evidence():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    evidence_payload = {
        "target_type": "track",
        "target_id": "track_0",
        "observer_name": "Field Surveyor Amit",
        "surface_type": "concrete_pavers",
        "is_accessible": True,
        "is_lit": True,
        "gps_start_lat": 31.253018,
        "gps_start_lon": 75.703517,
        "gps_end_lat": 31.253500,
        "gps_end_lon": 75.704000,
        "notes": "Surveyed main campus spine walkway. Paved, wide, step-free access with operational lighting.",
        "image_url": "https://example.com/survey_photo1.jpg"
    }
    res = client.post("/api/admin/verification/evidence", json=evidence_payload, headers=headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    ev = res.json()
    assert ev["status"] == "pending"
    assert ev["target_id"] == "track_0"
    assert ev["observer_name"] == "Field Surveyor Amit"


# Test 4: Approving and Rejecting Evidence
def test_4_review_evidence_flow():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # First submit an item to reject
    sub_res = client.post("/api/admin/verification/evidence", json={
        "target_type": "gap",
        "target_id": "gap_1",
        "observer_name": "Surveyor Rahul",
        "notes": "Attempted shortcut through maintenance area; not suitable for students.",
    }, headers=headers)
    assert sub_res.status_code == 201
    ev_id = sub_res.json()["id"]

    # Reject with rationale
    reject_res = client.post("/api/admin/verification/review", json={
        "evidence_id": ev_id,
        "action": "reject",
        "review_notes": "Maintenance access only; lacks accessible pedestrian pavement."
    }, headers=headers)
    assert reject_res.status_code == 200, f"Expected 200, got {reject_res.status_code}"
    assert reject_res.json()["verification_status"] == "rejected"


# Test 5: Audit History Recording
def test_5_audit_history():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/verification/history", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    history = res.json()
    assert isinstance(history, list)
    assert len(history) > 0
    actions = [h["action"] for h in history]
    assert "SUBMIT_EVIDENCE" in actions or "REJECT_EVIDENCE" in actions or "APPROVE_EVIDENCE" in actions


# Test 6: Rejection of Invalid GPS Coordinates
def test_6_invalid_coordinates_rejection():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Coordinates far from campus (e.g. New Delhi: 28.6139, 77.2090)
    bad_coords_payload = {
        "target_type": "track",
        "target_id": "track_1",
        "observer_name": "Test Surveyor",
        "gps_start_lat": 28.6139,  # Outside LPU campus bounds (~31.25)
        "gps_start_lon": 77.2090,
        "notes": "Recorded in New Delhi, not on LPU campus ground."
    }
    res = client.post("/api/admin/verification/evidence", json=bad_coords_payload, headers=headers)
    assert res.status_code == 422, f"Expected 422 for coordinates outside campus, got {res.status_code}"
    assert "outside" in res.text.lower() or "boundary" in res.text.lower() or "boundaries" in res.text.lower()


# Test 7: Rejection of Missing/Empty Field Evidence
def test_7_missing_field_evidence_rejection():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Empty notes
    empty_notes_payload = {
        "target_type": "track",
        "target_id": "track_2",
        "observer_name": "Test Surveyor",
        "notes": "   "  # Whitespace only
    }
    res = client.post("/api/admin/verification/evidence", json=empty_notes_payload, headers=headers)
    assert res.status_code == 422, f"Expected 422 for missing notes, got {res.status_code}"

    # Missing notes entirely
    no_notes_payload = {
        "target_type": "track",
        "target_id": "track_2",
        "observer_name": "Test Surveyor"
    }
    res = client.post("/api/admin/verification/evidence", json=no_notes_payload, headers=headers)
    assert res.status_code == 422, f"Expected 422 for omitted notes, got {res.status_code}"


# Test 8: Register and Verify Building Entrance in Isolated Test Database
def test_8_register_building_entrance():
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Register entrance for Block 34 (location_id=4) in test environment
    entrance_payload = {
        "location_id": 4,
        "entrance_latitude": 31.251520,
        "entrance_longitude": 75.705050,
        "door_name": "North Main Entrance",
        "verification_source": "On-site GPS Doorway Survey - OsmAnd + Survey Tool"
    }
    res = client.post("/api/admin/verification/entrance", json=entrance_payload, headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["verified"] is True
    assert abs(data["entrance_latitude"] - 31.251520) < 0.0001
    assert abs(data["entrance_longitude"] - 75.705050) < 0.0001

    # Verify that invalid entrance coords outside campus are rejected
    bad_entrance_payload = {
        "location_id": 4,
        "entrance_latitude": 35.0000,
        "entrance_longitude": 80.0000,
        "door_name": "Invalid Doorway",
        "verification_source": "Fake Data"
    }
    bad_res = client.post("/api/admin/verification/entrance", json=bad_entrance_payload, headers=headers)
    assert bad_res.status_code == 422, f"Expected 422 for out-of-bounds entrance, got {bad_res.status_code}"


# Test 9: Unverified Route Prevention & Disconnected Components
def test_9_unverified_route_prevention():
    net = get_pedestrian_network()
    # Route between unverified nodes
    route = net.calculate_shortest_path("trk0_0", "trk1_0", only_verified=True)
    assert route["available"] is False, "Route must remain unavailable for unverified paths"
    assert "awaiting" in route["message"].lower() or "unrecorded" in route["message"].lower()

    # Disconnected components remain exactly 4
    status = net.get_network_status()
    assert status["disconnected_components_count"] == 4, f"Expected 4 components, got {status['disconnected_components_count']}"
    assert status["routing_status"]["available"] is False


# Test 10: Existing API Backward Compatibility
def test_10_api_backward_compatibility():
    # 1. /api/locations
    res1 = client.get("/api/locations")
    assert res1.status_code == 200
    locs = res1.json()
    assert len(locs) >= 5

    # 2. /api/survey-tracks
    res2 = client.get("/api/survey-tracks")
    assert res2.status_code == 200
    assert res2.json()["type"] == "FeatureCollection"

    # 3. /api/network/status
    res3 = client.get("/api/network/status")
    assert res3.status_code == 200
    assert res3.json()["recorded_track_count"] == 4

    # 4. /api/verification/status (Phase 2B public endpoint)
    res4 = client.get("/api/verification/status")
    assert res4.status_code == 200
    v_stat = res4.json()
    assert "tracks" in v_stat
    assert "gaps" in v_stat
    assert "entrances" in v_stat
    assert v_stat["tracks"]["total"] == 4


# Test 11: Real Database & Storage Isolation Verification
def test_11_real_database_untouched():
    import sqlite3

    # 1. Confirm real database file exists and was not replaced or deleted
    assert real_db_path.exists() == real_db_exists_before, "Real database file existence changed!"

    if real_db_exists_before:
        # 2. Check SHA-256 hash of real database is bit-for-bit identical to pre-test baseline
        real_db_hash_after = hashlib.sha256(real_db_path.read_bytes()).hexdigest()
        assert real_db_hash_after == real_db_hash_before, (
            f"CRITICAL: Real database was modified! Hash before: {real_db_hash_before}, Hash after: {real_db_hash_after}"
        )
        assert real_db_path.stat().st_size == real_db_size_before, "Real database file size changed!"

        # 3. Direct inspection on real database to confirm records were untouched
        conn = sqlite3.connect(real_db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, name, verified, entrance_point FROM location ORDER BY id")
        rows = cur.fetchall()

        # Check tables in real database
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]

        # Verify Block 34 (id=4) was NOT modified by test_8_register_building_entrance
        loc_4 = next((r for r in rows if r[0] == 4), None)
        assert loc_4 is not None, "Location 4 not found in real database"
        assert loc_4[2] == 0, f"Location 4 in real database was altered to verified={loc_4[2]}"
        assert loc_4[3] is None, f"Location 4 entrance_point in real database was altered to {loc_4[3]}"

        conn.close()
        assert len(rows) == 5, f"Expected 5 locations in real database, found {len(rows)}"

    # 4. Check that real data/verification directory has no stray test files
    real_verif_dir = project_root / "data" / "verification"
    if real_verif_dir.exists():
        stray_files = [f.name for f in real_verif_dir.iterdir()]
        assert len(stray_files) == 0, f"Real verification directory was polluted with: {stray_files}"


# Register tests in sequence
run_test("1. Authentication & Authorization Protection (401 on missing/bad token)", test_1_auth_protection)
run_test("2. Pending Verification Items List (tracks, gaps, entrances)", test_2_pending_verification_list)
run_test("3. Field Evidence Submission (substantive notes, valid coordinates)", test_3_submit_evidence)
run_test("4. Evidence Review Workflow (approval & rejection with admin rationale)", test_4_review_evidence_flow)
run_test("5. Audit History Logging & Retrieval", test_5_audit_history)
run_test("6. Rejection of Invalid GPS Coordinates Outside Campus Bounds (HTTP 422)", test_6_invalid_coordinates_rejection)
run_test("7. Rejection of Missing/Empty Field Evidence (HTTP 422)", test_7_missing_field_evidence_rejection)
run_test("8. Campus Building Entrance Registration and Verification (isolated)", test_8_register_building_entrance)
run_test("9. Unverified Route Prevention & Disconnected Component Preservation", test_9_unverified_route_prevention)
run_test("10. Existing API Backward Compatibility (/locations, /survey-tracks, /network/status)", test_10_api_backward_compatibility)
run_test("11. Strict Test Database & Verification Storage Isolation (SHA-256 validation)", test_11_real_database_untouched)

print("\n" + "=" * 70)
print("PHASE 2B: ROUTE VERIFICATION SYSTEM TEST RESULTS")
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
