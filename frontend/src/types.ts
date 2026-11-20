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
