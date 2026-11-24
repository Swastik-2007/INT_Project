import type {
  CampusLocation,
  RouteResponse,
  NetworkStatusResponse,
  VerificationPendingData,
  AuditLogItem,
  PublicVerificationStatus
} from './types'

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

// ----- Phase 2B Verification API Calls -----

export async function fetchPendingVerification(token: string): Promise<VerificationPendingData | null> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/pending`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Error fetching pending verification:', err)
    return null
  }
}

export async function submitVerificationEvidence(token: string, payload: any): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/evidence`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to submit evidence' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function reviewVerificationEvidence(token: string, payload: { evidence_id: number; action: string; review_notes: string }): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to review evidence' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function verifyBuildingEntrance(token: string, payload: { location_id: number; entrance_latitude: number; entrance_longitude: number; door_name?: string; verification_source: string }): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/entrance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to verify entrance' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function revokeBuildingEntrance(token: string, locationId: number): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/entrance/${locationId}/revoke`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`
      }
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to revoke entrance verification' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function fetchVerificationHistory(token: string, limit: number = 100): Promise<AuditLogItem[]> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/verification/history?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export async function fetchPublicVerificationStatus(): Promise<PublicVerificationStatus | null> {
  try {
    const res = await fetch(`${BACKEND}/api/verification/status`)
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Error fetching public verification status:', err)
    return null
  }
}

// ----- Confirmed Connections API Calls (Phase 2B/2C Navigation) -----

export async function fetchConfirmedConnections(): Promise<{ connections: any[] }> {
  try {
    const res = await fetch(`${BACKEND}/api/confirmed-connections`)
    if (!res.ok) return { connections: [] }
    return await res.json()
  } catch (err) {
    console.warn('Error fetching confirmed connections:', err)
    return { connections: [] }
  }
}

export async function updateConnectionGeometry(
  token: string,
  connectionId: string,
  waypoints: [number, number][],
  notes?: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/connections/${connectionId}/geometry`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        intermediate_waypoints: waypoints,
        notes: notes || 'Updated corridor / pathway waypoints'
      })
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to update connection geometry' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function confirmDirectConnection(
  token: string,
  connectionId: string,
  notes?: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/connections/${connectionId}/confirm-direct`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        notes: notes || 'Confirmed direct outdoor walkway link'
      })
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to confirm direct connection' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}

export async function resetConnectionGeometry(
  token: string,
  connectionId: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/admin/connections/${connectionId}/reset`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      }
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, error: data?.detail || 'Failed to reset connection geometry' }
    }
    return { success: true, data }
  } catch {
    return { success: false, error: 'Cannot connect to backend server.' }
  }
}
