export interface CampusLocation {
  id: number
  block_number: string | null
  name: string
  category: string
  description?: string | null
  image_url?: string | null
  verified: boolean
  verification_source?: string | null
  last_verified?: string | null
  entrance_latitude?: number | null
  entrance_longitude?: number | null
  centroid_latitude?: number | null
  centroid_longitude?: number | null
  is_surveyed_waypoint?: boolean
  target_type?: string
}

export interface RouteSegment {
  label: string
  type: string
  is_indoor: boolean
  distance_m: number
  instruction: string
  coordinates: [number, number][]
}

export interface RouteResponse {
  available: boolean
  message: string
  reason_code?: string
  connection_id?: string
  connection_name?: string
  is_indoor?: boolean
  straight_line_gap_m?: number
  origin: {
    id: number
    name: string
    verified?: boolean
    latitude?: number | null
    longitude?: number | null
    snapped_node?: string
    snap_distance_m?: number
  }
  destination: {
    id: number
    name: string
    verified?: boolean
    latitude?: number | null
    longitude?: number | null
    is_surveyed_waypoint?: boolean
  }
  distance?: number | null // meters
  duration?: number | null // seconds
  duration_text?: string
  path_node_ids?: string[]
  geometry?: {
    type: 'LineString'
    coordinates: [number, number][]
  } | null
  segments?: RouteSegment[]
  has_indoor?: boolean
}

export interface ConfirmedConnectionItem {
  id: string
  name: string
  from_track: string
  from_node: string
  from_coords: [number, number]
  to_track: string
  to_node: string
  to_coords: [number, number]
  straight_line_gap_m: number
  classification: string
  is_indoor: boolean
  status: string
  has_explicit_geometry: boolean
  traversable_confirmed_by?: string | null
  intermediate_waypoints: [number, number][]
  measured_distance_m?: number | null
  notes?: string | null
}

export interface UserPosition {
  lat: number
  lon: number
  accuracy: number
  heading?: number | null
  speed?: number | null
  timestamp: number
}

export interface UnrecordedGap {
  from_recording: string
  to_recording: string
  displacement_meters: number
  bearing_degrees?: number
  time_gap_seconds?: number
  is_indoor_corridor?: boolean
  status: string
  note: string
}

export interface NetworkTrackMeta {
  track_index: number
  name: string
  segment_label: string
  point_count: number
  distance_m: number
  verified: boolean
}

export interface NetworkStatusResponse {
  recorded_track_count: number
  recorded_point_count: number
  recorded_distance_meters: number
  verified_segment_count: number
  unverified_segment_count: number
  disconnected_components_count: number
  tracks: NetworkTrackMeta[]
  unrecorded_gaps: UnrecordedGap[]
  routing_status: {
    available: boolean
    public_navigation_ready: boolean
    reason: string
    verified_coverage_meters: number
    unverified_coverage_meters: number
  }
}

// ----- Phase 2B Verification Types -----

export interface VerificationEvidenceItem {
  id: number
  observer_name: string
  status: 'pending' | 'approved' | 'rejected'
  notes: string
  surface_type?: string | null
  submitted_at: string
  reviewed_by?: string | null
  review_notes?: string | null
}

export interface VerificationTrackItem {
  target_id: string
  track_index: number
  name: string
  segment_label: string
  point_count: number
  distance_m: number
  verified: boolean
  start_coords?: { lat: number; lon: number }
  end_coords?: { lat: number; lon: number }
  evidence: VerificationEvidenceItem[]
}

export interface VerificationGapItem {
  target_id: string
  gap_index: number
  from_recording: string
  to_recording: string
  displacement_meters: number
  is_indoor_corridor: boolean
  status: string
  verified: boolean
  from_endpoint?: { lat: number; lon: number }
  to_startpoint?: { lat: number; lon: number }
  evidence: VerificationEvidenceItem[]
}

export interface VerificationPendingData {
  tracks: VerificationTrackItem[]
  gaps: VerificationGapItem[]
  locations: CampusLocation[]
  pending_evidence_count: number
  total_tracks_count: number
  verified_tracks_count: number
  total_locations_count: number
  verified_locations_count: number
}

export interface AuditLogItem {
  id: number
  action: string
  admin_username: string
  target_type: string
  target_id: string
  details: Record<string, any>
  created_at: string
}

export interface PublicVerificationStatus {
  tracks: {
    total: number
    verified: number
    unverified: number
    percent_verified: number
  }
  gaps: {
    total: number
    resolved: number
    pending: number
  }
  entrances: {
    total: number
    verified: number
    unverified: number
    percent_verified: number
  }
  distance: {
    total_meters: number
    verified_meters: number
    unverified_meters: number
  }
  routing_ready: boolean
}
