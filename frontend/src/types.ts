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
}

export interface RouteResponse {
  available: boolean
  message: string
  origin: {
    id: number
    name: string
    verified: boolean
    latitude?: number | null
    longitude?: number | null
  }
  destination: {
    id: number
    name: string
    verified: boolean
    latitude?: number | null
    longitude?: number | null
  }
  distance?: number | null // meters
  duration?: number | null // seconds
  path_node_ids?: number[]
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
