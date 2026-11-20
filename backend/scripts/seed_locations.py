"""Idempotently populate missing, unverified location records.

Works on Windows and cloud hosts; never overwrites user data or GPX files.
"""
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import db, crud, schemas, models


def seed_data():
    override = os.getenv("INT_PROJECT_LOCATIONS_FILE")
    data_path = Path(override) if override else PROJECT_ROOT / "data" / "blocks_unverified.json"
    if not data_path.is_file():
        raise FileNotFoundError(f"Seed data file not found: {data_path}")

    with data_path.open("r", encoding="utf-8") as f:
        entries = json.load(f).get("blocks", [])

    created = 0
    with db.SessionLocal() as session:
        for entry in entries:
            block_number = entry.get("block_number")
            if not block_number:
                continue
            existing = session.query(models.Location).filter_by(
                block_number=block_number
            ).first()
            if existing:
                continue
            loc = schemas.LocationCreate(
                block_number=block_number,
                name=entry.get("name") or f"Block {block_number}",
                category="Academic Block",
                description="",
                verified=False,
                entrance_latitude=None,
                entrance_longitude=None,
            )
            crud.create_location(session, loc)
            created += 1
    print(f"Seeded {created} missing unverified campus locations.")


if __name__ == "__main__":
    seed_data()

