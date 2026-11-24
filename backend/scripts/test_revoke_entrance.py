"""
Test Suite for Revoke Entrance Verification Feature (Phase 2B Correction)
==========================================================================
Validates:
1. Only authenticated administrators can revoke entrance verification (401 on missing/bad token).
2. Correct database fields are cleared (verified=False, entrance_point=None, verification_source=None, last_verified=None).
3. Other building records remain completely unchanged.
4. The JSON durable verification store is updated (location removed).
5. Revoked entrances stay unverified after application restart / database hydration.
6. Audit history logs REVOKE_ENTRANCE and preserves all previous audit records.
7. Navigation strictly refuses to route to or from revoked building entrances as verified doorways.
8. Strict test database isolation: never mutates real database or real data/verification files.
"""

import sys
import os
import shutil
import tempfile
import hashlib
import json
import atexit
from pathlib import Path
from datetime import datetime, timedelta
from jose import jwt
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

# ---------------------------------------------------------------------------
# Strict Test Database & Verification Storage Isolation Setup
# ---------------------------------------------------------------------------
test_temp_dir = tempfile.mkdtemp(prefix="lpu_test_revoke_isolation_")
test_db_path = Path(test_temp_dir) / "test_revoke_wayfinder.db"
test_verification_dir = Path(test_temp_dir) / "verification"
test_verification_dir.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["VERIFICATION_DATA_DIR"] = str(test_verification_dir)

_env_path = project_root / ".env"
load_dotenv(dotenv_path=_env_path, override=False)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

def cleanup():
    try:
        shutil.rmtree(test_temp_dir, ignore_errors=True)
    except Exception:
        pass

atexit.register(cleanup)

# ---------------------------------------------------------------------------
# App & Test Client Setup
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.router import get_db
from app.db import init_db
from app import models
from app.verification_store import (
    save_durable_entrance,
    load_durable_entrances,
    append_durable_audit,
    load_durable_audit_logs,
    hydrate_database,
    get_entrance_store_path,
    get_audit_log_path
)

# Initialize schema in isolated test database
init_db()

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

# Helper to generate admin token
def make_admin_token(user: str = ADMIN_USERNAME, exp_minutes: int = 60) -> str:
    payload = {"sub": user, "exp": datetime.utcnow() + timedelta(minutes=exp_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Seed initial buildings into isolated test DB
def seed_test_buildings():
    db = TestSessionLocal()
    try:
        # Check if buildings exist
        if db.query(models.Location).count() == 0:
            blocks = [
                (1, "28", "Block 28", "Academic Block"),
                (2, "29", "Block 29", "Academic Block"),
                (3, "30", "Block 30", "Academic Block"),
                (4, "34", "Block 34", "Academic Block"),
                (5, "36", "Block 36", "Academic Block"),
            ]
            for bid, bnum, bname, bcat in blocks:
                loc = models.Location(
                    id=bid,
                    block_number=bnum,
                    name=bname,
                    category=bcat,
                    verified=False
                )
                db.add(loc)
            db.commit()
    finally:
        db.close()

seed_test_buildings()

results = []

def run_test(name, fn):
    try:
        fn()
        results.append((name, "PASSED", ""))
    except Exception as e:
        results.append((name, "FAILED", str(e)))

# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_1_auth_protection():
    """Only authenticated administrators can revoke entrance verification."""
    # 1. No token -> 401
    res1 = client.post("/api/admin/verification/entrance/4/revoke")
    assert res1.status_code == 401, f"Expected 401 for unauthenticated request, got {res1.status_code}"

    # 2. Invalid token -> 401
    res2 = client.post("/api/admin/verification/entrance/4/revoke", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert res2.status_code == 401, f"Expected 401 for invalid token, got {res2.status_code}"

    # 3. Non-existent location -> 404
    token = make_admin_token()
    res3 = client.post("/api/admin/verification/entrance/9999/revoke", headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 404, f"Expected 404 for non-existent location, got {res3.status_code}"


def test_2_verify_then_revoke_individual_entrance():
    """Verify two entrances, then revoke one, confirming database fields, durability, and non-targeted record safety."""
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Register entrances for Location 1 (Block 28) and Location 4 (Block 34)
    res_b28 = client.post("/api/admin/verification/entrance", json={
        "location_id": 1,
        "entrance_latitude": 31.252000,
        "entrance_longitude": 75.704000,
        "door_name": "Block 28 Main Door",
        "verification_source": "GPS Field Survey"
    }, headers=headers)
    assert res_b28.status_code == 200

    res_b34 = client.post("/api/admin/verification/entrance", json={
        "location_id": 4,
        "entrance_latitude": 31.251520,
        "entrance_longitude": 75.705050,
        "door_name": "Block 34 North Entrance",
        "verification_source": "GPS Field Survey"
    }, headers=headers)
    assert res_b34.status_code == 200

    # Confirm both are in durable entrance store
    entrances_before = load_durable_entrances()
    assert "1" in entrances_before
    assert "4" in entrances_before

    # 2. Revoke Location 4 (Block 34)
    revoke_res = client.post("/api/admin/verification/entrance/4/revoke", headers=headers)
    assert revoke_res.status_code == 200, f"Expected 200, got {revoke_res.status_code}: {revoke_res.text}"
    rev_data = revoke_res.json()
    assert rev_data["status"] == "success"
    assert rev_data["verified"] is False
    assert rev_data["entrance_latitude"] is None
    assert rev_data["entrance_longitude"] is None

    # 3. Check Location 4 in isolated test database
    db = TestSessionLocal()
    try:
        loc4 = db.query(models.Location).filter(models.Location.id == 4).first()
        assert loc4 is not None
        assert loc4.verified is False, f"Expected verified=False, got {loc4.verified}"
        assert loc4.entrance_point is None, f"Expected entrance_point=None, got {loc4.entrance_point}"
        assert loc4.verification_source is None, f"Expected verification_source=None, got {loc4.verification_source}"
        assert loc4.last_verified is None, f"Expected last_verified=None, got {loc4.last_verified}"
        
        # Confirm Location 4 non-verification metadata is preserved
        assert loc4.id == 4
        assert loc4.name == "Block 34"
        assert loc4.block_number == "34"
        assert loc4.category == "Academic Block"

        # 4. Check Location 1 (Block 28) is COMPLETELY UNTOUCHED and still verified
        loc1 = db.query(models.Location).filter(models.Location.id == 1).first()
        assert loc1 is not None
        assert loc1.verified is True, "Location 1 was unexpectedly modified!"
        assert loc1.entrance_point is not None
        assert abs(loc1.entrance_latitude - 31.252000) < 0.0001
    finally:
        db.close()

    # 5. Check durable JSON store: '4' must be removed, '1' must remain
    entrances_after = load_durable_entrances()
    assert "4" not in entrances_after, "Location 4 was not removed from durable JSON store!"
    assert "1" in entrances_after, "Location 1 was incorrectly removed from durable JSON store!"


def test_3_hydration_after_restart():
    """Ensure that after simulated application restart, revoked entrances stay unverified."""
    db = TestSessionLocal()
    try:
        # Simulate restart hydration
        hydrate_database(db)

        # Confirm Location 4 remains unverified
        loc4 = db.query(models.Location).filter(models.Location.id == 4).first()
        assert loc4.verified is False, "Revoked location 4 became verified after hydration!"
        assert loc4.entrance_point is None

        # Confirm Location 1 remains verified
        loc1 = db.query(models.Location).filter(models.Location.id == 1).first()
        assert loc1.verified is True
    finally:
        db.close()


def test_4_audit_history_preservation():
    """Confirm REVOKE_ENTRANCE action is logged and previous audit records remain intact."""
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/verification/history", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0

    # Look for the REVOKE_ENTRANCE action for target_id 4
    revoke_log = next((l for l in logs if l["action"] == "REVOKE_ENTRANCE" and str(l["target_id"]) == "4"), None)
    assert revoke_log is not None, "REVOKE_ENTRANCE audit log not found!"
    assert revoke_log["target_type"] == "entrance"
    assert revoke_log["admin_username"] == ADMIN_USERNAME

    # Check that earlier VERIFY_ENTRANCE logs are still preserved
    verify_logs = [l for l in logs if l["action"] == "VERIFY_ENTRANCE"]
    assert len(verify_logs) >= 2, f"Expected at least 2 VERIFY_ENTRANCE logs, found {len(verify_logs)}"


def test_5_navigation_safety_with_revoked_entrance():
    """Navigation must refuse to use a revoked entrance as a verified destination doorway."""
    # 1. Walking route to Location 4 (revoked) -> available: False, DESTINATION_UNMAPPED
    res = client.get("/api/route?origin_id=-1&destination_id=4")
    assert res.status_code == 200
    route = res.json()
    assert route["available"] is False, "Route to revoked location should not be available!"
    assert route["reason_code"] == "DESTINATION_UNMAPPED"
    assert route["destination"]["verified"] is False
    assert route["destination"]["latitude"] is None

    # 2. Walking route from Location 4 (revoked) -> available: False, ORIGIN_UNMAPPED
    res2 = client.get("/api/route?origin_id=4&destination_id=-2")
    assert res2.status_code == 200
    route2 = res2.json()
    assert route2["available"] is False
    assert route2["reason_code"] == "ORIGIN_UNMAPPED"


def test_6_pending_verification_list_reflects_revocation():
    """GET /api/admin/verification/pending shows Location 4 as unverified."""
    token = make_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/verification/pending", headers=headers)
    assert res.status_code == 200
    data = res.json()
    loc4 = next((l for l in data["locations"] if l["id"] == 4), None)
    assert loc4 is not None
    assert loc4["verified"] is False
    assert loc4["entrance_latitude"] is None
    assert loc4["entrance_longitude"] is None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("TEST SUITE: REVOKE ENTRANCE VERIFICATION FEATURE")
    print("=" * 70)

    run_test("1. Authentication & Authorization Protection (401 / 404)", test_1_auth_protection)
    run_test("2. Revoke Individual Entrance & Preserve Other Records", test_2_verify_then_revoke_individual_entrance)
    run_test("3. Application Restart & Database Hydration Safety", test_3_hydration_after_restart)
    run_test("4. Audit History Logging & Previous Log Preservation", test_4_audit_history_preservation)
    run_test("5. Navigation Rejection of Revoked Entrance as Destination", test_5_navigation_safety_with_revoked_entrance)
    run_test("6. Dashboard / Pending Verification List Updates", test_6_pending_verification_list_reflects_revocation)

    print()
    passed_count = 0
    for name, status, err in results:
        if status == "PASSED":
            print(f"[PASS] {name}")
            passed_count += 1
        else:
            print(f"[FAIL] {name}: {err}")

    print("=" * 70)
    print(f"Summary: {passed_count}/{len(results)} tests passed.")
    print("=" * 70)

    if passed_count != len(results):
        sys.exit(1)
