import type { CampusLocation, RouteResponse, NetworkStatusResponse } from './types'

// Use relative path by default to work seamlessly with Vite proxy on desktop, LAN and Cloudflare tunnels
const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export async function fetchLocations(): Promise<CampusLocation[]> {
  try {
    const res = await fetch(`${BACKEND}/api/locations`)
    if (!res.ok) {
      throw new Error(`Failed to fetch locations: ${res.statusText}`)
    }
    const data = await res.json()
    return Array.isArray(data) ? data : data.value || []
  } catch (err) {
    console.warn('Using local fallback or error fetching locations:', err)
    return []
  }
}

export async function fetchLocation(id: number): Promise<CampusLocation | null> {
  try {
    const res = await fetch(`${BACKEND}/api/locations/${id}`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export async function fetchWalkingRoute(
  originId: number | string,
  destinationId: number,
  gpsCoords?: { lat: number; lon: number; accuracy?: number }
): Promise<RouteResponse> {
  try {
    let url = `${BACKEND}/api/route?destination_id=${destinationId}`
    if (originId === 'gps' && gpsCoords) {
      url += `&origin_lat=${gpsCoords.lat}&origin_lon=${gpsCoords.lon}`
      if (gpsCoords.accuracy) {
        url += `&gps_accuracy=${gpsCoords.accuracy}`
      }
    } else {
      url += `&origin_id=${originId}`
    }

    const res = await fetch(url)
    if (!res.ok) {
      return {
        available: false,
        message: 'Walking route not yet available. This area is awaiting mapping.',
        origin: { id: Number(originId) || -1, name: 'Origin', verified: false },
        destination: { id: destinationId, name: 'Destination', verified: false }
      }
    }
    return await res.json()
  } catch {
    return {
      available: false,
      message: 'Walking route not yet available. This area is awaiting mapping.',
      origin: { id: Number(originId) || -1, name: 'Origin', verified: false },
      destination: { id: destinationId, name: 'Destination', verified: false }
    }
  }
}

// Survey track GeoJSON overlay
export interface SurveyTrackFeature {
  type: 'Feature'
  properties: {
    type: string
    name?: string
    segment_label?: string
    point_count?: number
    distance_m?: number
    duration_sec?: number
    color?: string
    stroke?: string
    'stroke-width'?: number
    'stroke-opacity'?: number
    verified?: boolean
    source?: string
    track_name?: string
    label?: string
    'marker-color'?: string
    'marker-symbol'?: string
  }
  geometry: {
    type: 'Point' | 'LineString'
    coordinates: number[] | number[][]
  }
}

export interface SurveyTracksGeoJSON {
  type: 'FeatureCollection'
  features: SurveyTrackFeature[]
}

export async function fetchSurveyTracks(): Promise<SurveyTracksGeoJSON> {
  try {
    const res = await fetch(`${BACKEND}/api/survey-tracks`)
    if (!res.ok) {
      return { type: 'FeatureCollection', features: [] }
    }
    return await res.json()
  } catch {
    return { type: 'FeatureCollection', features: [] }
  }
}

export async function fetchNetworkStatus(): Promise<NetworkStatusResponse | null> {
  try {
    const res = await fetch(`${BACKEND}/api/network/status`)
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Error fetching pedestrian network status:', err)
    return null
  }
}
