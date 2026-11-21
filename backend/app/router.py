from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt as _bcrypt_lib
from datetime import datetime, timedelta
from typing import Optional
import os, json
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded before reading any env vars
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

class _BcryptContext:
    """Minimal bcrypt wrapper — avoids passlib/bcrypt version mismatch."""
    @staticmethod
    def verify(plain: str, hashed: str) -> bool:
        try:
            return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False
    @staticmethod
    def hash(plain: str) -> str:
        return _bcrypt_lib.hashpw(plain.encode(), _bcrypt_lib.gensalt()).decode()

from . import crud, schemas, db
from . import models

api_router = APIRouter()

# ---- Auth setup ----
pwd_context = _BcryptContext()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/token", auto_error=False)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=8))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db_session = db.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

def get_current_admin(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        if username != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username

# ---- Admin token endpoint ----
@api_router.post("/admin/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    stored_hash = os.getenv("ADMIN_PASSWORD_HASH", ADMIN_PASSWORD_HASH)
    if not stored_hash or not verify_password(form_data.password, stored_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}

# ---- Locations ----
@api_router.get("/locations", response_model=list[schemas.Location])
def read_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_locations(db, skip=skip, limit=limit)

@api_router.get("/locations/{location_id}", response_model=schemas.Location)
def read_location(location_id: int, db: Session = Depends(get_db)):
    loc = crud.get_location(db, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc

@api_router.post("/locations", response_model=schemas.Location, status_code=status.HTTP_201_CREATED)
def create_location(location: schemas.LocationCreate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    return crud.create_location(db, location)

@api_router.put("/locations/{location_id}", response_model=schemas.Location)
def update_location(location_id: int, location: schemas.LocationUpdate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    loc = crud.get_location(db, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return crud.update_location(db, loc, location)

@api_router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(location_id: int, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    loc = crud.get_location(db, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    crud.delete_location(db, loc)
    return None

# ---- Walkways ----
@api_router.get("/walkways", response_model=list[schemas.Walkway])
def read_walkways(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_walkways(db, skip=skip, limit=limit)

@api_router.post("/walkways", response_model=schemas.Walkway, status_code=status.HTTP_201_CREATED)
def create_walkway(walkway: schemas.WalkwayCreate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    src = crud.get_location(db, walkway.source_id)
    tgt = crud.get_location(db, walkway.target_id)
    if not src or not tgt:
        raise HTTPException(status_code=400, detail="Source or target location does not exist")
    return crud.create_walkway(db, walkway)

# ---- Walking Route (Public) ----
@api_router.get("/route")
def get_walking_route(
    origin_id: Optional[int] = None,
    destination_id: Optional[int] = None,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    gps_accuracy: Optional[float] = None,
    db: Session = Depends(get_db)
):
    from .pedestrian_network import get_pedestrian_network
    network = get_pedestrian_network()

    # Destination is mandatory
    if destination_id is None:
        raise HTTPException(status_code=400, detail="destination_id is required")

    dest = crud.get_location(db, destination_id)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination location not found")

    # If origin_id is provided, resolve from location database
    if origin_id is not None:
        orig = crud.get_location(db, origin_id)
        if not orig:
            raise HTTPException(status_code=404, detail="Origin location not found")

        origin_meta = {"id": orig.id, "name": orig.name, "verified": orig.verified}

        # Strictly check if both locations are verified with ground-truth entrance coordinates
        if not orig.verified or not dest.verified or not orig.entrance_latitude or not dest.entrance_latitude:
            return {
                "available": False,
                "message": "Walking route not yet available. This area is awaiting mapping.",
                "origin": origin_meta,
                "destination": {"id": dest.id, "name": dest.name, "verified": dest.verified},
                "distance": None,
                "duration": None,
                "geometry": None
            }

        # Query database walkways graph
        import networkx as nx
        G = nx.Graph()
        walkways = crud.get_walkways(db, limit=1000)
        for w in walkways:
            G.add_edge(w.source_id, w.target_id, weight=w.distance, geometry=w.geometry_wkt)

        if not G.has_node(orig.id) or not G.has_node(dest.id) or not nx.has_path(G, orig.id, dest.id):
            return {
                "available": False,
                "message": "Walking route not yet available. This area is awaiting mapping.",
                "origin": origin_meta,
                "destination": {"id": dest.id, "name": dest.name, "verified": dest.verified},
                "distance": None,
                "duration": None,
                "geometry": None
            }

        path = nx.shortest_path(G, source=orig.id, target=dest.id, weight="weight")
        total_dist = nx.shortest_path_length(G, source=orig.id, target=dest.id, weight="weight")
        duration_sec = int(total_dist / 1.2)  # ~1.2 m/s average walking speed

        return {
            "available": True,
            "message": "Verified route found.",
            "origin": {"id": orig.id, "name": orig.name, "latitude": orig.entrance_latitude, "longitude": orig.entrance_longitude},
            "destination": {"id": dest.id, "name": dest.name, "latitude": dest.entrance_latitude, "longitude": dest.entrance_longitude},
            "distance": round(total_dist, 1),
            "duration": duration_sec,
            "path_node_ids": path,
        }

    # Otherwise origin is live GPS coordinates
    elif origin_lat is not None and origin_lon is not None:
        origin_meta = {
            "id": -1,
            "name": "Current Location",
            "verified": False,
            "latitude": origin_lat,
            "longitude": origin_lon
        }

        # Destination must be verified with real entrance
        if not dest.verified or not dest.entrance_latitude:
            return {
                "available": False,
                "message": "Walking route not yet available. This area is awaiting mapping.",
                "origin": origin_meta,
                "destination": {"id": dest.id, "name": dest.name, "verified": dest.verified},
                "distance": None,
                "duration": None,
                "geometry": None
            }

        # Snap GPS to verified network edges
        snap_result = network.snap_to_network(
            lat=origin_lat,
            lon=origin_lon,
            max_distance_m=30.0,
            accuracy_m=gps_accuracy,
            only_verified=True
        )

        if not snap_result["snapped"]:
            return {
                "available": False,
                "message": f"Walking route not yet available. {snap_result['reason']}",
                "origin": origin_meta,
                "destination": {"id": dest.id, "name": dest.name, "verified": dest.verified},
                "distance": None,
                "duration": None,
                "geometry": None
            }

        return {
            "available": False,
            "message": "Walking route not yet available. Pathway is awaiting verification.",
            "origin": origin_meta,
            "destination": {"id": dest.id, "name": dest.name, "verified": dest.verified},
            "distance": None,
            "duration": None,
            "geometry": None
        }

    else:
        raise HTTPException(status_code=400, detail="Either origin_id or origin_lat and origin_lon must be provided")


# ---- Pedestrian Network Status (Public) ----
@api_router.get("/network/status")
def get_network_status():
    """
    Return comprehensive pedestrian network topology and coverage statistics:
    - Recorded track count, point count, distance (meters)
    - Verified and unverified segment counts
    - Disconnected components count
    - Details of unrecorded physical gaps (e.g. Block 34 indoor passage)
    - Routing availability status
    """
    from .pedestrian_network import get_pedestrian_network
    network = get_pedestrian_network()
    return network.get_network_status()

# ---- Surveys (admin-protected) ----
@api_router.get("/admin/surveys")
def list_surveys(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    return db.query(models.Survey).all()

@api_router.post("/admin/surveys", status_code=status.HTTP_201_CREATED)
def create_survey(payload: dict, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    survey = models.Survey(
        name=payload.get("name", "Unnamed"),
        description=payload.get("description", ""),
        geojson=payload.get("geojson", "{}"),
        verified=False,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey

@api_router.delete("/admin/surveys/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_survey(survey_id: int, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    db.delete(survey)
    db.commit()
    return None


# ---- Public Survey Track Overlays (read-only GeoJSON) ----
@api_router.get("/survey-tracks")
def get_survey_tracks():
    """
    Serve the analysed GPX survey tracks as a GeoJSON FeatureCollection.
    This is a read-only endpoint that returns the pre-computed overlay data
    generated by the GPX analysis script. No database writes.
    """
    geojson_path = Path(__file__).resolve().parent.parent.parent / "data" / "survey_analysis" / "verified_tracks_overlay.geojson"
    if not geojson_path.exists():
        return JSONResponse(
            content={"type": "FeatureCollection", "features": []},
            media_type="application/geo+json"
        )
    with open(geojson_path, "r") as f:
        data = json.load(f)
    return JSONResponse(content=data, media_type="application/geo+json")


@api_router.get("/survey-tracks/analysis")
def get_survey_analysis():
    """
    Serve the full GPX analysis report (read-only).
    Contains per-track statistics, gap analysis, and quality checks.
    """
    report_path = Path(__file__).resolve().parent.parent.parent / "data" / "survey_analysis" / "gpx_analysis_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Analysis report not found. Run analyze_gpx_surveys.py first.")
    with open(report_path, "r") as f:
        data = json.load(f)
    return JSONResponse(content=data)
