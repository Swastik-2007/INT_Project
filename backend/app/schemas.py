from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class LocationBase(BaseModel):
    block_number: Optional[str] = Field(None, description="Block number like '34'")
    name: str = Field(..., description="Human readable name, e.g., 'Block 34'")
    category: str = Field(..., description="Category such as Academic Block, Hostel, Library")
    description: Optional[str] = None
    image_url: Optional[str] = None
    verified: bool = False
    verification_source: Optional[str] = None
    last_verified: Optional[datetime] = None
    entrance_latitude: Optional[float] = None
    entrance_longitude: Optional[float] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    target_type: Optional[str] = "building_entrance"
    is_surveyed_waypoint: Optional[bool] = False

class LocationCreate(LocationBase):
    entrance_latitude: Optional[float] = None
    entrance_longitude: Optional[float] = None

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    verified: Optional[bool] = None
    verification_source: Optional[str] = None
    last_verified: Optional[datetime] = None
    entrance_latitude: Optional[float] = None
    entrance_longitude: Optional[float] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    target_type: Optional[str] = "building_entrance"
    is_surveyed_waypoint: Optional[bool] = False

class Location(LocationBase):
    id: int

    class Config:
        orm_mode = True

class WalkwayBase(BaseModel):
    source_id: int
    target_id: int
    distance: float
    landmark: Optional[str] = None
    geometry_wkt: str = Field(..., description="LINESTRING in WKT format")

class WalkwayCreate(WalkwayBase):
    pass

class Walkway(WalkwayBase):
    id: int

    class Config:
        orm_mode = True


# ----- Phase 2B Verification Schemas -----

class EvidenceCreate(BaseModel):
    target_type: str = Field(..., description="Target type: track, gap, walkway, entrance")
    target_id: str = Field(..., description="Target identifier, e.g. track_0, gap_3, location_4")
    observer_name: str = Field(..., min_length=2, description="Surveyor or observer full name")
    surface_type: Optional[str] = Field(None, description="paved, concrete, tile_corridor, gravel, etc.")
    is_accessible: bool = False
    is_lit: bool = False
    gps_start_lat: Optional[float] = None
    gps_start_lon: Optional[float] = None
    gps_end_lat: Optional[float] = None
    gps_end_lon: Optional[float] = None
    notes: str = Field(..., min_length=5, description="Field observations and ground-truth notes")
    image_url: Optional[str] = None


class EvidenceReview(BaseModel):
    evidence_id: int
    action: str = Field(..., description="'approve' or 'reject'")
    review_notes: str = Field(..., min_length=3, description="Administrator rationale for approval or rejection")


class EntranceVerificationCreate(BaseModel):
    location_id: int
    entrance_latitude: float
    entrance_longitude: float
    door_name: Optional[str] = "Main Entrance"
    verification_source: str = Field(..., min_length=3, description="On-site ground truth verification source")


class EvidenceResponse(BaseModel):
    id: int
    target_type: str
    target_id: str
    observer_name: str
    surface_type: Optional[str]
    is_accessible: bool
    is_lit: bool
    gps_start_lat: Optional[float]
    gps_start_lon: Optional[float]
    gps_end_lat: Optional[float]
    gps_end_lon: Optional[float]
    notes: str
    image_url: Optional[str]
    status: str
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    review_notes: Optional[str]

    class Config:
        orm_mode = True


class AuditLogResponse(BaseModel):
    id: int
    action: str
    admin_username: str
    target_type: str
    target_id: str
    details: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


# ----- Confirmed Connections Schemas -----

class ConnectionGeometryUpdate(BaseModel):
    intermediate_waypoints: List[List[float]] = Field(default_factory=list, description="Ordered [[lat, lon], ...] waypoints")
    notes: Optional[str] = None


class ConnectionDirectConfirm(BaseModel):
    notes: Optional[str] = "Confirmed direct walkway between recording endpoints"
