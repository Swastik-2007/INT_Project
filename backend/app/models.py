"""SQLAlchemy models for LPU Wayfinder.

We store academic blocks (and other facilities) in the `location` table.
Each location has a PostGIS POINT geometry for the entrance (and optional centroid).
We also store pedestrian walkways as edges in the `walkway` table, each edge has a
LINESTRING geometry and a length (meters)."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Text
from geoalchemy2 import Geometry
import os

# Determine if we are using SQLite (fallback) – SQLite does not support PostGIS Geometry types.
USE_SQLITE = os.getenv('DATABASE_URL', '').startswith('sqlite')

# Helper to choose column type for geometries
def GeometryColumn():
    return Text if USE_SQLITE else Geometry
from datetime import datetime

from .database import Base

class Location(Base):
    __tablename__ = "location"

    id = Column(Integer, primary_key=True, index=True)
    block_number = Column(String, nullable=True, index=True)  # e.g. "34"
    name = Column(String, nullable=False)  # e.g. "Block 34"
    category = Column(String, nullable=False)  # Academic Block, Hostel, Library, ...
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    verification_source = Column(String, nullable=True)
    last_verified = Column(DateTime, nullable=True)
    # Geometry columns (PostGIS)
    entrance_point = Column(GeometryColumn(), nullable=True)
    centroid_point = Column(GeometryColumn(), nullable=True)

    @property
    def entrance_latitude(self):
        if not self.entrance_point:
            return None
        try:
            pt_str = str(self.entrance_point)
            if "POINT" in pt_str.upper():
                coords = pt_str.upper().replace("POINT", "").replace("(", "").replace(")", "").strip().split()
                return float(coords[1])
        except Exception:
            pass
        return None

    @property
    def entrance_longitude(self):
        if not self.entrance_point:
            return None
        try:
            pt_str = str(self.entrance_point)
            if "POINT" in pt_str.upper():
                coords = pt_str.upper().replace("POINT", "").replace("(", "").replace(")", "").strip().split()
                return float(coords[0])
        except Exception:
            pass
        return None

    @property
    def centroid_latitude(self):
        if not self.centroid_point:
            return None
        try:
            pt_str = str(self.centroid_point)
            if "POINT" in pt_str.upper():
                coords = pt_str.upper().replace("POINT", "").replace("(", "").replace(")", "").strip().split()
                return float(coords[1])
        except Exception:
            pass
        return None

    @property
    def centroid_longitude(self):
        if not self.centroid_point:
            return None
        try:
            pt_str = str(self.centroid_point)
            if "POINT" in pt_str.upper():
                coords = pt_str.upper().replace("POINT", "").replace("(", "").replace(")", "").strip().split()
                return float(coords[0])
        except Exception:
            pass
        return None

    # Relationships
    outgoing = relationship("Walkway", back_populates="source", foreign_keys="Walkway.source_id")
    incoming = relationship("Walkway", back_populates="target", foreign_keys="Walkway.target_id")

# --- Walkway model ---
class Walkway(Base):
    __tablename__ = "walkway"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("location.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("location.id"), nullable=False)
    geometry = Column(GeometryColumn(), nullable=False)  # Stored as TEXT for SQLite fallback
    distance = Column(Float, nullable=False)  # meters
    landmark = Column(String, nullable=True)

    @property
    def geometry_wkt(self):
        return str(self.geometry) if self.geometry else ""

    source = relationship("Location", back_populates="outgoing", foreign_keys=[source_id])
    target = relationship("Location", back_populates="incoming", foreign_keys=[target_id])

# --- Survey model ---
class Survey(Base):
    __tablename__ = "survey"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # Store the full GeoJSON (LineString) as text
    geojson = Column(Text, nullable=False)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String, nullable=True)


class VerificationEvidence(Base):
    """
    Field evidence submitted for GPS tracks, unrecorded gaps, and surveyed walkways.
    Requires explicit review and approval before segments are integrated into routing graph.
    """
    __tablename__ = "verification_evidence"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String, nullable=False, index=True)  # "track", "gap", "entrance", "walkway"
    target_id = Column(String, nullable=False, index=True)    # e.g. "track_0", "gap_3", "location_4"
    observer_name = Column(String, nullable=False)
    surface_type = Column(String, nullable=True)             # "paved", "tile_corridor", "concrete", etc.
    is_accessible = Column(Boolean, default=False)
    is_lit = Column(Boolean, default=False)
    gps_start_lat = Column(Float, nullable=True)
    gps_start_lon = Column(Float, nullable=True)
    gps_end_lat = Column(Float, nullable=True)
    gps_end_lon = Column(Float, nullable=True)
    notes = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)   # "pending", "approved", "rejected"
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, nullable=True)
    review_notes = Column(Text, nullable=True)


class AuditLog(Base):
    """
    Immutable audit history recording all verification decisions,
    entrance registrations, approvals, and rejections.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False, index=True)       # "SUBMIT_EVIDENCE", "APPROVE_EVIDENCE", "REJECT_EVIDENCE", "VERIFY_ENTRANCE"
    admin_username = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    details = Column(Text, nullable=True)                    # JSON string with metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


