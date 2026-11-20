from pydantic import BaseModel, Field
from typing import Optional
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

