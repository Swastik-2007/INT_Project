"""
Durable Verification Store & Hydration Engine (Phase 2B)
=========================================================
Provides file-backed persistence for verification evidence, entrance registrations,
and audit logs. Solves Render free-tier ephemeral /tmp storage without requiring
external credentials or deleting existing database records.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_verification_dir() -> Path:
    override = os.getenv("VERIFICATION_DATA_DIR")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "verification"


def get_evidence_store_path() -> Path:
    return get_verification_dir() / "evidence_store.json"


def get_audit_log_path() -> Path:
    return get_verification_dir() / "audit_log.jsonl"


def get_entrance_store_path() -> Path:
    return get_verification_dir() / "entrance_verifications.json"


# Backward compatibility aliases
VERIFICATION_DIR = get_verification_dir()
EVIDENCE_STORE_PATH = get_evidence_store_path()
AUDIT_LOG_PATH = get_audit_log_path()
ENTRANCE_STORE_PATH = get_entrance_store_path()


def ensure_verification_dir() -> None:
    get_verification_dir().mkdir(parents=True, exist_ok=True)


def load_durable_entrances() -> Dict[str, Any]:
    ensure_verification_dir()
    path = get_entrance_store_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_durable_entrance(
    location_id: int,
    block_number: Optional[str],
    lat: float,
    lon: float,
    door_name: str,
    source: str,
    verified_by: str
) -> Dict[str, Any]:
    ensure_verification_dir()
    entrances = load_durable_entrances()
    record = {
        "location_id": location_id,
        "block_number": block_number,
        "entrance_latitude": lat,
        "entrance_longitude": lon,
        "door_name": door_name,
        "verification_source": source,
        "verified_by": verified_by,
        "verified_at": datetime.utcnow().isoformat()
    }
    entrances[str(location_id)] = record
    with open(get_entrance_store_path(), "w", encoding="utf-8") as f:
        json.dump(entrances, f, indent=2)
    return record


def load_durable_evidence() -> List[Dict[str, Any]]:
    ensure_verification_dir()
    path = get_evidence_store_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_durable_evidence(evidence: Dict[str, Any]) -> None:
    ensure_verification_dir()
    items = load_durable_evidence()
    # Check if existing item needs update or append new
    existing_idx = next((i for i, item in enumerate(items) if item.get("id") == evidence.get("id")), None)
    if existing_idx is not None:
        items[existing_idx] = evidence
    else:
        items.append(evidence)
    with open(get_evidence_store_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def append_durable_audit(action: str, admin_username: str, target_type: str, target_id: str, details: Any) -> Dict[str, Any]:
    ensure_verification_dir()
    entry = {
        "action": action,
        "admin_username": admin_username,
        "target_type": target_type,
        "target_id": str(target_id),
        "details": details if isinstance(details, dict) else {"info": str(details)},
        "created_at": datetime.utcnow().isoformat()
    }
    with open(get_audit_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def load_durable_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    ensure_verification_dir()
    path = get_audit_log_path()
    if not path.exists():
        return []
    logs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
    except Exception:
        pass
    # Return most recent first
    return list(reversed(logs))[:limit]


def hydrate_database(db) -> None:
    """
    Hydrate SQLite database with durable verification records upon startup.
    Protects against data loss when Render creates a fresh /tmp database.
    Does not overwrite or damage existing rows.
    """
    from . import models

    # 1. Hydrate verified entrances into Location table
    entrances = load_durable_entrances()
    for loc_id_str, data in entrances.items():
        loc_id = int(loc_id_str)
        loc = db.query(models.Location).filter(models.Location.id == loc_id).first()
        if loc and not loc.verified:
            loc.verified = True
            loc.entrance_point = f"POINT({data['entrance_longitude']} {data['entrance_latitude']})"
            loc.verification_source = data.get("verification_source", "Administrator Field Survey")
            try:
                loc.last_verified = datetime.fromisoformat(data["verified_at"])
            except Exception:
                loc.last_verified = datetime.utcnow()
            db.add(loc)

    # 2. Hydrate verification evidence if table is empty
    ev_count = db.query(models.VerificationEvidence).count()
    if ev_count == 0:
        durable_items = load_durable_evidence()
        for item in durable_items:
            db_ev = models.VerificationEvidence(
                id=item.get("id"),
                target_type=item["target_type"],
                target_id=item["target_id"],
                observer_name=item["observer_name"],
                surface_type=item.get("surface_type"),
                is_accessible=item.get("is_accessible", False),
                is_lit=item.get("is_lit", False),
                gps_start_lat=item.get("gps_start_lat"),
                gps_start_lon=item.get("gps_start_lon"),
                gps_end_lat=item.get("gps_end_lat"),
                gps_end_lon=item.get("gps_end_lon"),
                notes=item["notes"],
                image_url=item.get("image_url"),
                status=item.get("status", "pending"),
                reviewed_by=item.get("reviewed_by"),
                review_notes=item.get("review_notes"),
            )
            db.add(db_ev)

    # 3. Hydrate audit logs if table is empty
    audit_count = db.query(models.AuditLog).count()
    if audit_count == 0:
        durable_logs = load_durable_audit_logs(limit=1000)
        for log in reversed(durable_logs):
            db_log = models.AuditLog(
                action=log["action"],
                admin_username=log["admin_username"],
                target_type=log["target_type"],
                target_id=str(log["target_id"]),
                details=json.dumps(log.get("details", {})),
            )
            db.add(db_log)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
