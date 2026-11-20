from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

# ----- Location CRUD -----

def get_locations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Location).offset(skip).limit(limit).all()

def get_location(db: Session, location_id: int):
    return db.query(models.Location).filter(models.Location.id == location_id).first()

def create_location(db: Session, location: schemas.LocationCreate):
    db_location = models.Location(
        block_number=location.block_number,
        name=location.name,
        category=location.category,
        description=location.description,
        image_url=location.image_url,
        verified=location.verified,
        verification_source=location.verification_source,
        last_verified=location.last_verified,
    )
    if location.entrance_latitude is not None and location.entrance_longitude is not None:
        point_wkt = f"POINT({location.entrance_longitude} {location.entrance_latitude})"
        db_location.entrance_point = point_wkt
    if location.centroid_latitude is not None and location.centroid_longitude is not None:
        centroid_wkt = f"POINT({location.centroid_longitude} {location.centroid_latitude})"
        db_location.centroid_point = centroid_wkt
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location

def update_location(db: Session, db_location: models.Location, updates: schemas.LocationUpdate):
    for attr, value in updates.dict(exclude_unset=True).items():
        if attr in {"entrance_latitude", "entrance_longitude"}:
            # handled after loop
            continue
        setattr(db_location, attr, value)
    # Update entrance point if coordinates provided
    if updates.entrance_latitude is not None and updates.entrance_longitude is not None:
        db_location.entrance_point = f"POINT({updates.entrance_longitude} {updates.entrance_latitude})"
    if updates.centroid_latitude is not None and updates.centroid_longitude is not None:
        db_location.centroid_point = f"POINT({updates.centroid_longitude} {updates.centroid_latitude})"
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location

def delete_location(db: Session, db_location: models.Location):
    db.delete(db_location)
    db.commit()

# ----- Walkway CRUD -----

def get_walkways(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Walkway).offset(skip).limit(limit).all()

def create_walkway(db: Session, walkway: schemas.WalkwayCreate):
    db_walkway = models.Walkway(
        source_id=walkway.source_id,
        target_id=walkway.target_id,
        distance=walkway.distance,
        landmark=walkway.landmark,
        geometry=walkway.geometry_wkt,
    )
    db.add(db_walkway)
    db.commit()
    db.refresh(db_walkway)
    return db_walkway

