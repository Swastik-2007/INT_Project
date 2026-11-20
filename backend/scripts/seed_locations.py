import sys, os
import pathlib, json
from dotenv import load_dotenv
from sqlalchemy.orm import Session
# Ensure the backend app package is on PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from app import db, crud, models, schemas

# Load .env (SQLite URL)
load_dotenv()

def get_db_session() -> Session:
    return db.SessionLocal()

def seed_data():
    data_path = pathlib.Path(os.getenv('INT_PROJECT_ROOT', '') or r"C:/Users/swast/OneDrive/Desktop/INT_PROJECT/data/blocks_unverified.json")
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        return
    with open(data_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    session = get_db_session()
    created = 0
    for entry in payload.get('blocks', []):
        # Check if already exists by block_number
        existing = session.query(models.Location).filter(models.Location.block_number == entry.get('block_number')).first()
        if existing:
            continue
        loc_create = schemas.LocationCreate(
            block_number=entry.get('block_number'),
            name=entry.get('name'),
            category='Academic Block',
            description='',
            image_url=None,
            verified=entry.get('verified', False),
            verification_source=entry.get('source'),
            last_verified=None,
            entrance_latitude=entry.get('latitude'),
            entrance_longitude=entry.get('longitude'),
            centroid_latitude=None,
            centroid_longitude=None,
        )
        crud.create_location(session, loc_create)
        created += 1
    session.close()
    print(f"Seeded {created} locations into the database.")

if __name__ == '__main__':
    seed_data()

