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


# =====================================================================
# Phase 2B: Administrative Route Verification & Evidence Workflow
# =====================================================================

CAMPUS_LAT_MIN, CAMPUS_LAT_MAX = 31.2200, 31.2800
CAMPUS_LON_MIN, CAMPUS_LON_MAX = 75.6800, 75.7300

def validate_campus_coords(lat: Optional[float], lon: Optional[float], field_name: str = "GPS") -> None:
    if lat is None or lon is None:
        return
    if not (CAMPUS_LAT_MIN <= lat <= CAMPUS_LAT_MAX and CAMPUS_LON_MIN <= lon <= CAMPUS_LON_MAX):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} coordinates ({lat}, {lon}) are outside valid LPU campus boundaries."
        )


@api_router.get("/admin/verification/pending")
def list_pending_verification(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    """
    List all pending items requiring field evidence or administrative review:
    - 4 GPS survey recordings with current verification status and coordinates preview
    - 3 unrecorded physical gaps (e.g. Block 34 indoor passage)
    - Campus building locations awaiting verified doorway registration
    - Submitted evidence records pending approval
    """
    from .pedestrian_network import get_pedestrian_network
    network = get_pedestrian_network()

    # Query all evidence
    all_evidence = db.query(models.VerificationEvidence).all()
    evidence_by_target = {}
    for ev in all_evidence:
        key = f"{ev.target_type}:{ev.target_id}"
        if key not in evidence_by_target:
            evidence_by_target[key] = []
        evidence_by_target[key].append({
            "id": ev.id,
            "observer_name": ev.observer_name,
            "status": ev.status,
            "notes": ev.notes,
            "surface_type": ev.surface_type,
            "submitted_at": ev.submitted_at.isoformat() if ev.submitted_at else None,
            "reviewed_by": ev.reviewed_by,
            "review_notes": ev.review_notes,
        })

    # Tracks
    tracks_list = []
    for t in network.tracks_metadata:
        t_id = f"track_{t['track_index']}"
        s_node = network.graph.nodes.get(t["start_node"], {}) if t.get("start_node") else {}
        e_node = network.graph.nodes.get(t["end_node"], {}) if t.get("end_node") else {}
        tracks_list.append({
            "target_id": t_id,
            "track_index": t["track_index"],
            "name": t["name"],
            "segment_label": t["segment_label"],
            "point_count": t["point_count"],
            "distance_m": t["distance_m"],
            "verified": t.get("verified", False),
            "start_coords": {"lat": s_node.get("lat"), "lon": s_node.get("lon")},
            "end_coords": {"lat": e_node.get("lat"), "lon": e_node.get("lon")},
            "evidence": evidence_by_target.get(f"track:{t_id}", [])
        })

    # Gaps
    gaps_list = []
    for idx, g in enumerate(network.unrecorded_gaps):
        g_id = f"gap_{idx + 1}"
        gaps_list.append({
            "target_id": g_id,
            "gap_index": idx + 1,
            "from_recording": g.get("from_recording"),
            "to_recording": g.get("to_recording"),
            "displacement_meters": g.get("displacement_meters"),
            "is_indoor_corridor": g.get("is_indoor_corridor", False),
            "status": g.get("status", "unrecorded_physical_gap"),
            "verified": g.get("verified", False),
            "from_endpoint": g.get("from_endpoint"),
            "to_startpoint": g.get("to_startpoint"),
            "evidence": evidence_by_target.get(f"gap:{g_id}", [])
        })

    # Locations
    locations = crud.get_locations(db, limit=200)
    loc_list = [{
        "id": loc.id,
        "name": loc.name,
        "block_number": loc.block_number,
        "category": loc.category,
        "verified": loc.verified,
        "entrance_latitude": loc.entrance_latitude,
        "entrance_longitude": loc.entrance_longitude,
        "verification_source": loc.verification_source,
        "last_verified": loc.last_verified.isoformat() if loc.last_verified else None,
    } for loc in locations]

    pending_evidence = [ev for ev in all_evidence if ev.status == "pending"]

    return {
        "tracks": tracks_list,
        "gaps": gaps_list,
        "locations": loc_list,
        "pending_evidence_count": len(pending_evidence),
        "total_tracks_count": len(tracks_list),
        "verified_tracks_count": sum(1 for t in tracks_list if t["verified"]),
        "total_locations_count": len(loc_list),
        "verified_locations_count": sum(1 for l in loc_list if l["verified"]),
    }


@api_router.post("/admin/verification/evidence", status_code=status.HTTP_201_CREATED)
def submit_verification_evidence(
    payload: schemas.EvidenceCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Submit ground-truth field evidence for a recorded track, physical gap, or walkway.
    Requires substantive notes and validates any provided GPS coordinates against campus bounds.
    """
    # Validate target type
    valid_types = {"track", "gap", "walkway", "entrance"}
    if payload.target_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"Invalid target_type. Must be one of {valid_types}")

    # Validate non-empty substantive field notes
    if not payload.notes or len(payload.notes.strip()) < 5:
        raise HTTPException(
            status_code=422,
            detail="Field evidence notes must contain substantive observations (at least 5 characters)."
        )

    # Validate coordinate bounds
    validate_campus_coords(payload.gps_start_lat, payload.gps_start_lon, "Start")
    validate_campus_coords(payload.gps_end_lat, payload.gps_end_lon, "End")

    evidence = models.VerificationEvidence(
        target_type=payload.target_type,
        target_id=payload.target_id.strip(),
        observer_name=payload.observer_name.strip(),
        surface_type=payload.surface_type,
        is_accessible=payload.is_accessible,
        is_lit=payload.is_lit,
        gps_start_lat=payload.gps_start_lat,
        gps_start_lon=payload.gps_start_lon,
        gps_end_lat=payload.gps_end_lat,
        gps_end_lon=payload.gps_end_lon,
        notes=payload.notes.strip(),
        image_url=payload.image_url,
        status="pending",
        submitted_at=datetime.utcnow()
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Persist to durable store and append to audit log
    from .verification_store import save_durable_evidence, append_durable_audit
    evidence_dict = {
        "id": evidence.id,
        "target_type": evidence.target_type,
        "target_id": evidence.target_id,
        "observer_name": evidence.observer_name,
        "surface_type": evidence.surface_type,
        "is_accessible": evidence.is_accessible,
        "is_lit": evidence.is_lit,
        "gps_start_lat": evidence.gps_start_lat,
        "gps_start_lon": evidence.gps_start_lon,
        "gps_end_lat": evidence.gps_end_lat,
        "gps_end_lon": evidence.gps_end_lon,
        "notes": evidence.notes,
        "image_url": evidence.image_url,
        "status": evidence.status,
        "submitted_at": evidence.submitted_at.isoformat()
    }
    save_durable_evidence(evidence_dict)
    append_durable_audit(
        action="SUBMIT_EVIDENCE",
        admin_username=admin,
        target_type=evidence.target_type,
        target_id=evidence.target_id,
        details={"evidence_id": evidence.id, "observer": evidence.observer_name, "notes": evidence.notes}
    )

    audit_entry = models.AuditLog(
        action="SUBMIT_EVIDENCE",
        admin_username=admin,
        target_type=evidence.target_type,
        target_id=evidence.target_id,
        details=json.dumps({"evidence_id": evidence.id, "observer": evidence.observer_name, "notes": evidence.notes})
    )
    db.add(audit_entry)
    db.commit()

    return evidence_dict


@api_router.post("/admin/verification/review")
def review_verification_evidence(
    payload: schemas.EvidenceReview,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Approve or reject submitted field evidence with administrator rationale.
    Approved evidence immediately updates routing network eligibility.
    """
    if payload.action not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Action must be either 'approve' or 'reject'.")

    if not payload.review_notes or len(payload.review_notes.strip()) < 3:
        raise HTTPException(status_code=422, detail="Review rationale notes are required.")

    evidence = db.query(models.VerificationEvidence).filter(
        models.VerificationEvidence.id == payload.evidence_id
    ).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence record not found.")

    new_status = "approved" if payload.action == "approve" else "rejected"
    evidence.status = new_status
    evidence.reviewed_at = datetime.utcnow()
    evidence.reviewed_by = admin
    evidence.review_notes = payload.review_notes.strip()

    db.add(evidence)

    # Record Audit Log
    action_type = "APPROVE_EVIDENCE" if payload.action == "approve" else "REJECT_EVIDENCE"
    audit = models.AuditLog(
        action=action_type,
        admin_username=admin,
        target_type=evidence.target_type,
        target_id=evidence.target_id,
        details=json.dumps({
            "evidence_id": evidence.id,
            "action": payload.action,
            "rationale": payload.review_notes,
            "target_type": evidence.target_type,
            "target_id": evidence.target_id
        })
    )
    db.add(audit)
    db.commit()

    # Update durable file-backed persistence and reload network
    from .verification_store import save_durable_evidence, append_durable_audit
    from .pedestrian_network import reload_pedestrian_network

    save_durable_evidence({
        "id": evidence.id,
        "target_type": evidence.target_type,
        "target_id": evidence.target_id,
        "observer_name": evidence.observer_name,
        "surface_type": evidence.surface_type,
        "is_accessible": evidence.is_accessible,
        "is_lit": evidence.is_lit,
        "gps_start_lat": evidence.gps_start_lat,
        "gps_start_lon": evidence.gps_start_lon,
        "gps_end_lat": evidence.gps_end_lat,
        "gps_end_lon": evidence.gps_end_lon,
        "notes": evidence.notes,
        "image_url": evidence.image_url,
        "status": new_status,
        "reviewed_at": evidence.reviewed_at.isoformat() if evidence.reviewed_at else None,
        "reviewed_by": admin,
        "review_notes": evidence.review_notes
    })
    append_durable_audit(
        action=action_type,
        admin_username=admin,
        target_type=evidence.target_type,
        target_id=evidence.target_id,
        details={"evidence_id": evidence.id, "action": payload.action, "rationale": payload.review_notes}
    )

    reload_pedestrian_network()

    return {
        "status": "success",
        "evidence_id": evidence.id,
        "verification_status": new_status,
        "target_type": evidence.target_type,
        "target_id": evidence.target_id,
        "reviewed_by": admin,
        "reviewed_at": evidence.reviewed_at.isoformat()
    }


@api_router.post("/admin/verification/entrance")
def verify_building_entrance(
    payload: schemas.EntranceVerificationCreate,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Register and verify a campus building entrance with surveyed GPS coordinates.
    Validates coordinates against campus boundaries and updates the Location record.
    """
    loc = db.query(models.Location).filter(models.Location.id == payload.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail=f"Location id {payload.location_id} not found.")

    validate_campus_coords(payload.entrance_latitude, payload.entrance_longitude, "Building entrance")

    if not payload.verification_source or len(payload.verification_source.strip()) < 3:
        raise HTTPException(status_code=422, detail="Verification source must be specified.")

    loc.verified = True
    loc.entrance_point = f"POINT({payload.entrance_longitude} {payload.entrance_latitude})"
    loc.verification_source = payload.verification_source.strip()
    loc.last_verified = datetime.utcnow()

    # Record Audit Log
    audit = models.AuditLog(
        action="VERIFY_ENTRANCE",
        admin_username=admin,
        target_type="entrance",
        target_id=str(loc.id),
        details=json.dumps({
            "location_name": loc.name,
            "block_number": loc.block_number,
            "door_name": payload.door_name,
            "latitude": payload.entrance_latitude,
            "longitude": payload.entrance_longitude,
            "source": payload.verification_source
        })
    )
    db.add(loc)
    db.add(audit)
    db.commit()
    db.refresh(loc)

    # Persist in durable entrance store
    from .verification_store import save_durable_entrance, append_durable_audit
    save_durable_entrance(
        location_id=loc.id,
        block_number=loc.block_number,
        lat=payload.entrance_latitude,
        lon=payload.entrance_longitude,
        door_name=payload.door_name or "Main Entrance",
        source=payload.verification_source,
        verified_by=admin
    )
    append_durable_audit(
        action="VERIFY_ENTRANCE",
        admin_username=admin,
        target_type="entrance",
        target_id=str(loc.id),
        details={
            "location_name": loc.name,
            "door_name": payload.door_name,
            "latitude": payload.entrance_latitude,
            "longitude": payload.entrance_longitude,
            "source": payload.verification_source
        }
    )

    return {
        "status": "success",
        "location_id": loc.id,
        "name": loc.name,
        "block_number": loc.block_number,
        "verified": loc.verified,
        "entrance_latitude": loc.entrance_latitude,
        "entrance_longitude": loc.entrance_longitude,
        "verification_source": loc.verification_source,
        "last_verified": loc.last_verified.isoformat() if loc.last_verified else None
    }


@api_router.get("/admin/verification/history")
def get_verification_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Retrieve chronological audit history of all verification decisions.
    """
    from .verification_store import load_durable_audit_logs
    # Query database records
    db_logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    if db_logs:
        return [{
            "id": log.id,
            "action": log.action,
            "admin_username": log.admin_username,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": json.loads(log.details) if log.details else {},
            "created_at": log.created_at.isoformat() if log.created_at else None
        } for log in db_logs]

    # Fallback to durable file log if database audit log is empty
    return load_durable_audit_logs(limit=limit)


@api_router.get("/verification/status")
def get_public_verification_status(db: Session = Depends(get_db)):
    """
    Public read-only summary of verification progress across tracks,
    gaps, and campus building entrances. Powers Leaflet map progress widgets.
    """
    from .pedestrian_network import get_pedestrian_network
    network = get_pedestrian_network()

    locations = crud.get_locations(db, limit=200)
    total_locs = len(locations)
    verified_locs = sum(1 for loc in locations if loc.verified)

    total_tracks = len(network.tracks_metadata)
    verified_tracks = sum(1 for t in network.tracks_metadata if t.get("verified", False))

    total_gaps = len(network.unrecorded_gaps)
    resolved_gaps = sum(1 for g in network.unrecorded_gaps if g.get("verified", False))

    status_data = network.get_network_status()
    routing_status = status_data.get("routing_status", {})

    return {
        "tracks": {
            "total": total_tracks,
            "verified": verified_tracks,
            "unverified": total_tracks - verified_tracks,
            "percent_verified": round((verified_tracks / total_tracks * 100) if total_tracks else 0, 1)
        },
        "gaps": {
            "total": total_gaps,
            "resolved": resolved_gaps,
            "pending": total_gaps - resolved_gaps
        },
        "entrances": {
            "total": total_locs,
            "verified": verified_locs,
            "unverified": total_locs - verified_locs,
            "percent_verified": round((verified_locs / total_locs * 100) if total_locs else 0, 1)
        },
        "distance": {
            "total_meters": network.total_recorded_distance_m,
            "verified_meters": routing_status.get("verified_coverage_meters", 0.0),
            "unverified_meters": routing_status.get("unverified_coverage_meters", network.total_recorded_distance_m)
        },
        "routing_ready": routing_status.get("available", False)
    }
