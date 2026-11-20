import React, { useEffect, useRef, useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import L from 'leaflet'
import {
  Search,
  Navigation,
  MapPin,
  Crosshair,
  ArrowRight,
  Clock,
  Footprints,
  AlertTriangle,
  CheckCircle,
  X,
  Compass,
  ArrowLeft,
  Info,
  ChevronUp,
  ChevronDown,
  Layers
} from 'lucide-react'
import { Navbar } from './Navbar'
import { fetchLocations, fetchWalkingRoute, fetchSurveyTracks } from './api'
import type { CampusLocation, RouteResponse, UserPosition } from './types'
import type { SurveyTracksGeoJSON } from './api'

// LPU Campus Approximate Center (Phagwara, Punjab)
const LPU_CAMPUS_CENTER: [number, number] = [31.2534, 75.7037]

// Haversine formula for distance in meters
function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const MapPage: React.FC = () => {
  const [searchParams] = useSearchParams()

  // Campus Data State
  const [locations, setLocations] = useState<CampusLocation[]>([])
  const [loadingLocations, setLoadingLocations] = useState(true)

  // Selection State
  const [originId, setOriginId] = useState<string>('gps') // 'gps' or location ID
  const [destinationId, setDestinationId] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [searchMode, setSearchMode] = useState<'origin' | 'destination'>('destination')

  // Route State
  const [routeData, setRouteData] = useState<RouteResponse | null>(null)
  const [loadingRoute, setLoadingRoute] = useState(false)

  // Navigation Mode
  const [isNavigating, setIsNavigating] = useState(false)
  const [hasArrived, setHasArrived] = useState(false)
  const [remainingDistance, setRemainingDistance] = useState<number | null>(null)

  // User GPS State
  const [userPos, setUserPos] = useState<UserPosition | null>(null)
  const [gpsError, setGpsError] = useState<string | null>(null)
  const [trackingGps, setTrackingGps] = useState(false)
  const watchIdRef = useRef<number | null>(null)

  // Mobile Bottom Sheet
  const [isSheetExpanded, setIsSheetExpanded] = useState(true)

  // Survey Track Overlay State
  const [surveyTracks, setSurveyTracks] = useState<SurveyTracksGeoJSON | null>(null)
  const [showSurveyTracks, setShowSurveyTracks] = useState(true)
  const [showTrackLegend, setShowTrackLegend] = useState(false)
  const surveyTrackLayerRef = useRef<L.LayerGroup | null>(null)

  // Leaflet Map Refs
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const userMarkerRef = useRef<L.Marker | null>(null)
  const userAccuracyCircleRef = useRef<L.Circle | null>(null)
  const routeLayerRef = useRef<L.Polyline | null>(null)
  const locationMarkersLayerRef = useRef<L.LayerGroup | null>(null)

  // Load locations on mount
  useEffect(() => {
    fetchLocations().then(data => {
      setLocations(data)
      setLoadingLocations(false)

      // If URL has dest param, pre-select it
      const destParam = searchParams.get('dest')
      if (destParam) {
        setDestinationId(destParam)
      }
      const origParam = searchParams.get('orig')
      if (origParam) {
        setOriginId(origParam)
      }
    })
    // Load survey track overlays
    fetchSurveyTracks().then(data => {
      if (data && data.features && data.features.length > 0) {
        setSurveyTracks(data)
      }
    })
  }, [searchParams])

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return

    // Clean, modern map tiles (CartoDB Positron)
    const map = L.map(mapContainerRef.current, {
      center: LPU_CAMPUS_CENTER,
      zoom: 16,
      zoomControl: false,
      maxZoom: 19,
      minZoom: 14
    })

    // Official OpenStreetMap Standard basemap (free, reliable, no API key required)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
    }).addTo(map)

    L.control.zoom({ position: 'topright' }).addTo(map)

    const markersGroup = L.layerGroup().addTo(map)
    locationMarkersLayerRef.current = markersGroup
    mapInstanceRef.current = map

    // Fix map container size upon render
    setTimeout(() => {
      map.invalidateSize()
    }, 250)

    return () => {
      map.remove()
      mapInstanceRef.current = null
    }
  }, [])

  // Start watching user GPS position
  const startGpsWatch = () => {
    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your browser.')
      return
    }

    setTrackingGps(true)
    setGpsError(null)

    watchIdRef.current = navigator.geolocation.watchPosition(
      pos => {
        const { latitude, longitude, accuracy, heading, speed } = pos.coords
        const newPos: UserPosition = {
          lat: latitude,
          lon: longitude,
          accuracy,
          heading,
          speed,
          timestamp: pos.timestamp
        }
        setUserPos(newPos)
        setGpsError(null)

        // Update map marker
        if (mapInstanceRef.current) {
          const map = mapInstanceRef.current
          const latLng = L.latLng(latitude, longitude)

          if (!userMarkerRef.current) {
            const userIcon = L.divIcon({
              className: 'user-gps-marker',
              iconSize: [22, 22],
              iconAnchor: [11, 11]
            })
            userMarkerRef.current = L.marker(latLng, { icon: userIcon, zIndexOffset: 1000 }).addTo(map)
            userAccuracyCircleRef.current = L.circle(latLng, {
              radius: accuracy,
              color: '#3B82F6',
              fillColor: '#60A5FA',
              fillOpacity: 0.12,
              weight: 1
            }).addTo(map)
          } else {
            userMarkerRef.current.setLatLng(latLng)
            if (userAccuracyCircleRef.current) {
              userAccuracyCircleRef.current.setLatLng(latLng)
              userAccuracyCircleRef.current.setRadius(accuracy)
            }
          }
        }
      },
      err => {
        console.warn('GPS watch error:', err)
        if (err.code === 1) {
          setGpsError('Location permission denied. Please allow location access in your browser settings.')
        } else if (err.code === 2) {
          setGpsError('Location unavailable. Please check your device GPS.')
        } else {
          setGpsError('Location request timed out. Retrying...')
        }
        setTrackingGps(false)
      },
      {
        enableHighAccuracy: true,
        maximumAge: 2000,
        timeout: 10000
      }
    )
  }

  // Auto-request GPS on mount
  useEffect(() => {
    startGpsWatch()
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
      }
    }
  }, [])

  // Recenter map on user GPS
  const handleRecenter = () => {
    if (userPos && mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([userPos.lat, userPos.lon], 18, { duration: 1 })
    } else {
      startGpsWatch()
    }
  }

  // Draw location markers on the map
  useEffect(() => {
    if (!mapInstanceRef.current || !locationMarkersLayerRef.current) return
    const layer = locationMarkersLayerRef.current
    layer.clearLayers()

    locations.forEach(loc => {
      // Use verified coordinates if present
      if (loc.entrance_latitude && loc.entrance_longitude) {
        const isSelected = String(loc.id) === destinationId
        const markerColor = isSelected ? '#E66A27' : loc.verified ? '#10B981' : '#6B7280'

        const customIcon = L.divIcon({
          className: 'custom-campus-pin',
          html: `
            <div style="
              background-color: ${markerColor};
              width: 32px;
              height: 32px;
              border-radius: 50% 50% 50% 0;
              transform: rotate(-45deg);
              border: 2px solid white;
              box-shadow: 0 4px 10px rgba(0,0,0,0.25);
              display: flex;
              align-items: center;
              justify-content: center;
            ">
              <span style="transform: rotate(45deg); color: white; font-size: 11px; font-weight: 800;">
                ${loc.block_number || '•'}
              </span>
            </div>
          `,
          iconSize: [32, 32],
          iconAnchor: [16, 32],
          popupAnchor: [0, -30]
        })

        const marker = L.marker([loc.entrance_latitude, loc.entrance_longitude], { icon: customIcon })
        marker.bindPopup(`
          <div style="font-family: var(--font-main); padding: 4px;">
            <div style="font-weight: 700; font-size: 14px; color: #20252D;">${loc.name}</div>
            <div style="font-size: 12px; color: #6B7280; margin-top: 2px;">${loc.category}</div>
            <div style="margin-top: 6px; font-size: 11px;">
              ${loc.verified
                ? '<span style="color: #10B981; font-weight: 700;">✓ Verified Entrance</span>'
                : '<span style="color: #F59E0B; font-weight: 600;">⚠ Awaiting Field Survey</span>'
              }
            </div>
          </div>
        `)

        marker.on('click', () => {
          setDestinationId(String(loc.id))
        })

        layer.addLayer(marker)
      }
    })
  }, [locations, destinationId])

  // Draw survey track overlays on the map
  useEffect(() => {
    if (!mapInstanceRef.current) return

    // Remove old survey track layer
    if (surveyTrackLayerRef.current) {
      mapInstanceRef.current.removeLayer(surveyTrackLayerRef.current)
      surveyTrackLayerRef.current = null
    }

    if (!surveyTracks || !showSurveyTracks) return

    const group = L.layerGroup()

    for (const feature of surveyTracks.features) {
      if (feature.geometry.type === 'LineString' && feature.properties.type === 'recorded_track') {
        // Track polyline
        const coords = (feature.geometry.coordinates as number[][]).map(c => [c[1], c[0]] as [number, number])
        const color = feature.properties.stroke || feature.properties.color || '#E66A27'
        const polyline = L.polyline(coords, {
          color,
          weight: 4,
          opacity: 0.85,
          dashArray: '8, 6',  // Dashed to indicate "unverified survey data"
          lineCap: 'round',
          lineJoin: 'round',
        })

        const distM = feature.properties.distance_m
        const label = feature.properties.segment_label || feature.properties.name || 'Survey Track'
        const pts = feature.properties.point_count || 0
        const distStr = distM ? (distM >= 1000 ? `${(distM / 1000).toFixed(2)} km` : `${Math.round(distM)} m`) : 'unknown'

        polyline.bindPopup(`
          <div style="font-family: var(--font-main); padding: 4px; min-width: 200px;">
            <div style="font-weight: 700; font-size: 13px; color: #20252D; margin-bottom: 4px;">
              📍 ${label}
            </div>
            <div style="font-size: 11px; color: #6B7280; line-height: 1.6;">
              <div>Distance: <strong>${distStr}</strong></div>
              <div>GPS Points: <strong>${pts}</strong></div>
              <div>Source: <strong>OsmAnd GPX Recording</strong></div>
            </div>
            <div style="margin-top: 6px; padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700;
              background-color: #FFFBEB; color: #B45309; display: inline-block;">
              ⚠ Unverified Survey Track
            </div>
          </div>
        `)

        group.addLayer(polyline)
      } else if (feature.geometry.type === 'Point') {
        // Start/End markers
        const [lon, lat] = feature.geometry.coordinates as number[]
        const isStart = feature.properties.type === 'track_start'
        const markerColor = feature.properties['marker-color'] || '#E66A27'
        const label = feature.properties.label || (isStart ? 'Start' : 'End')

        const icon = L.divIcon({
          className: 'survey-track-marker',
          html: `
            <div style="
              width: 18px; height: 18px; border-radius: 50%;
              background-color: ${markerColor};
              border: 2.5px solid white;
              box-shadow: 0 2px 6px rgba(0,0,0,0.3);
              display: flex; align-items: center; justify-content: center;
            ">
              <span style="color: white; font-size: 9px; font-weight: 900;">
                ${isStart ? 'S' : 'E'}
              </span>
            </div>
          `,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        })

        const marker = L.marker([lat, lon], { icon, zIndexOffset: 500 })
        marker.bindTooltip(label, {
          permanent: false,
          direction: 'top',
          offset: [0, -12],
          className: 'survey-marker-tooltip',
        })

        group.addLayer(marker)
      }
    }

    group.addTo(mapInstanceRef.current)
    surveyTrackLayerRef.current = group
  }, [surveyTracks, showSurveyTracks])

  // Selected Destination and Origin objects
  const selectedDestination = useMemo(() => {
    return locations.find(l => String(l.id) === destinationId) || null
  }, [locations, destinationId])

  const selectedOrigin = useMemo(() => {
    if (originId === 'gps') {
      return {
        id: -1,
        name: userPos ? 'My Current Location' : 'Your GPS Location',
        category: 'GPS',
        verified: Boolean(userPos),
        entrance_latitude: userPos?.lat,
        entrance_longitude: userPos?.lon
      } as CampusLocation
    }
    return locations.find(l => String(l.id) === originId) || null
  }, [locations, originId, userPos])

  // Handle Route Calculation when Origin or Destination changes
  useEffect(() => {
    if (!destinationId) {
      setRouteData(null)
      if (routeLayerRef.current && mapInstanceRef.current) {
        mapInstanceRef.current.removeLayer(routeLayerRef.current)
        routeLayerRef.current = null
      }
      return
    }

    // If origin is a specific campus location
    if (originId !== 'gps') {
      setLoadingRoute(true)
      fetchWalkingRoute(Number(originId), Number(destinationId)).then(res => {
        setRouteData(res)
        setLoadingRoute(false)
      })
    } else {
      // Origin is user's current GPS location
      // Check if destination has verified entrance
      if (!selectedDestination?.verified || !selectedDestination?.entrance_latitude) {
        setRemainingDistance(null)
        setRouteData({
          available: false,
          message: 'Walking route not yet available. This area is awaiting mapping.',
          origin: { id: -1, name: 'Current Location', verified: Boolean(userPos) },
          destination: {
            id: Number(destinationId),
            name: selectedDestination?.name || 'Destination',
            verified: false
          },
          distance: null,
          duration: null
        })
      } else {
        // Destination has verified entrance, but pedestrian walkway path between GPS and entrance awaits survey
        setRemainingDistance(null)
        setRouteData({
          available: false,
          message: 'Walking route not yet available. This area is awaiting mapping.',
          origin: { id: -1, name: 'Current Location', verified: Boolean(userPos) },
          destination: {
            id: selectedDestination.id,
            name: selectedDestination.name,
            verified: true,
            latitude: selectedDestination.entrance_latitude,
            longitude: selectedDestination.entrance_longitude
          },
          distance: null,
          duration: null
        })
      }
    }
  }, [originId, destinationId, selectedDestination, userPos])

  // Live Navigation updates
  useEffect(() => {
    if (!isNavigating || !selectedDestination) return

    if (userPos && selectedDestination.entrance_latitude && selectedDestination.entrance_longitude) {
      const dist = calculateDistance(
        userPos.lat,
        userPos.lon,
        selectedDestination.entrance_latitude,
        selectedDestination.entrance_longitude
      )
      setRemainingDistance(Math.round(dist))

      // Check arrival within 15 meters
      if (dist <= 18) {
        setHasArrived(true)
      }
    }
  }, [isNavigating, userPos, selectedDestination])

  // Filtered search list
  const filteredLocations = useMemo(() => {
    if (!searchQuery.trim()) return locations
    const q = searchQuery.toLowerCase().trim()
    return locations.filter(
      l =>
        l.name.toLowerCase().includes(q) ||
        (l.block_number && l.block_number.toLowerCase().includes(q)) ||
        l.category.toLowerCase().includes(q)
    )
  }, [locations, searchQuery])

  // Select location from search
  const handleSelectSearchResult = (loc: CampusLocation) => {
    if (searchMode === 'destination') {
      setDestinationId(String(loc.id))
      // Pan to destination if coordinates exist
      if (loc.entrance_latitude && loc.entrance_longitude && mapInstanceRef.current) {
        mapInstanceRef.current.flyTo([loc.entrance_latitude, loc.entrance_longitude], 17)
      }
    } else {
      setOriginId(String(loc.id))
    }
    setIsSearchOpen(false)
    setSearchQuery('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100%', overflow: 'hidden' }}>
      <Navbar />

      {/* Main Map Container */}
      <div style={{ position: 'relative', flex: 1, width: '100%', height: '100%' }}>
        <div ref={mapContainerRef} style={{ width: '100%', height: '100%', zIndex: 1 }} />

        {/* Floating Top Search Bar (when not in full search modal) */}
        {!isNavigating && (
          <div
            style={{
              position: 'absolute',
              top: 16,
              left: 16,
              right: 16,
              maxWidth: 460,
              zIndex: 500,
              margin: '0 auto'
            }}
          >
            <div
              onClick={() => {
                setSearchMode('destination')
                setIsSearchOpen(true)
              }}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: 14,
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
                cursor: 'pointer',
                border: '1px solid #E5E7EB'
              }}
            >
              <Search size={20} color="#E66A27" />
              <div style={{ flex: 1 }}>
                {selectedDestination ? (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#6B7280', fontWeight: 600 }}>Destination</div>
                    <div style={{ fontSize: '0.95rem', color: '#20252D', fontWeight: 700 }}>
                      {selectedDestination.name}
                    </div>
                  </div>
                ) : (
                  <span style={{ color: '#9CA3AF', fontSize: '0.95rem' }}>
                    Where do you want to go? (e.g. Block 34)
                  </span>
                )}
              </div>
              {selectedDestination && (
                <button
                  onClick={e => {
                    e.stopPropagation()
                    setDestinationId('')
                    setRouteData(null)
                  }}
                  style={{ padding: 4, color: '#9CA3AF' }}
                >
                  <X size={18} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Live Navigation Top HUD */}
        {isNavigating && selectedDestination && (
          <div
            style={{
              position: 'absolute',
              top: 16,
              left: 16,
              right: 16,
              maxWidth: 500,
              margin: '0 auto',
              zIndex: 500,
              backgroundColor: '#20252D',
              color: '#FFFFFF',
              borderRadius: 18,
              padding: '1rem 1.25rem',
              boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
            className="animate-slide-up"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 12,
                  backgroundColor: '#E66A27',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Footprints size={26} color="#FFFFFF" />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Walking to
                </div>
                <div style={{ fontSize: '1.15rem', fontWeight: 800 }}>{selectedDestination.name}</div>
                {remainingDistance !== null && (
                  <div style={{ fontSize: '0.88rem', color: '#10B981', fontWeight: 700, marginTop: 2 }}>
                    {remainingDistance >= 1000
                      ? `${(remainingDistance / 1000).toFixed(2)} km remaining`
                      : `${remainingDistance} meters remaining`}
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={() => {
                setIsNavigating(false)
                setHasArrived(false)
              }}
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                color: '#EF4444',
                border: '1px solid #EF4444',
                padding: '0.5rem 0.9rem',
                borderRadius: 10,
                fontSize: '0.85rem',
                fontWeight: 700
              }}
            >
              Stop
            </button>
          </div>
        )}

        {/* Floating Controls (Recenter & GPS Accuracy) */}
        <div
          style={{
            position: 'absolute',
            bottom: isSheetExpanded ? (isNavigating ? 190 : 260) : 90,
            right: 16,
            zIndex: 400,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            transition: 'bottom 0.3s ease'
          }}
        >
          {/* Survey Tracks Layer Toggle Button */}
          {surveyTracks && surveyTracks.features.length > 0 && (
            <button
              onClick={() => {
                setShowSurveyTracks(prev => !prev)
                setShowTrackLegend(prev => !prev)
              }}
              title={showSurveyTracks ? "Hide GPS survey tracks" : "Show GPS survey tracks"}
              style={{
                width: 46,
                height: 46,
                borderRadius: 12,
                backgroundColor: showSurveyTracks ? '#FFF2E8' : '#FFFFFF',
                color: showSurveyTracks ? '#E66A27' : '#6B7280',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 15px rgba(0, 0, 0, 0.15)',
                border: `1px solid ${showSurveyTracks ? '#E66A27' : '#E5E7EB'}`
              }}
            >
              <Layers size={22} />
            </button>
          )}

          <button
            onClick={handleRecenter}
            title={trackingGps ? "Recenter on active GPS position" : "Recenter on my location"}
            style={{
              width: 46,
              height: 46,
              borderRadius: 12,
              backgroundColor: '#FFFFFF',
              color: userPos ? '#E66A27' : '#6B7280',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 15px rgba(0, 0, 0, 0.15)',
              border: '1px solid #E5E7EB'
            }}
          >
            <Crosshair size={22} />
          </button>
        </div>

        {/* Survey Tracks Legend (when toggled on) */}
        {showSurveyTracks && showTrackLegend && (
          <div
            style={{
              position: 'absolute',
              top: 76,
              right: 16,
              zIndex: 490,
              backgroundColor: '#FFFFFF',
              borderRadius: 12,
              padding: '0.75rem 1rem',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
              border: '1px solid #E5E7EB',
              maxWidth: 270,
              fontSize: '0.8rem'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontWeight: 700, color: '#20252D' }}>GPS Survey Tracks</span>
              <button onClick={() => setShowTrackLegend(false)} style={{ color: '#9CA3AF', padding: 2 }}>
                <X size={14} />
              </button>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#B45309', backgroundColor: '#FFFBEB', padding: '3px 6px', borderRadius: 6, marginBottom: 8, fontWeight: 600 }}>
              ⚠ 4 Unverified Field Recordings
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 14, height: 3, backgroundColor: '#E63946', borderRadius: 2 }} />
                <span style={{ color: '#4B5563' }}>A: Main Gate → Academic</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 14, height: 3, backgroundColor: '#2A9D8F', borderRadius: 2 }} />
                <span style={{ color: '#4B5563' }}>B: Block 30 → 32</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 14, height: 3, backgroundColor: '#E9C46A', borderRadius: 2 }} />
                <span style={{ color: '#4B5563' }}>C: Block 32 → 34</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 14, height: 3, backgroundColor: '#264653', borderRadius: 2 }} />
                <span style={{ color: '#4B5563' }}>D: Block 34 → BH4</span>
              </div>
            </div>
            <div style={{ fontSize: '0.7rem', color: '#9CA3AF', marginTop: 8, borderTop: '1px solid #F3F4F6', paddingTop: 6 }}>
              Block 34 indoor passage: Unrecorded gap (73.6m)
            </div>
          </div>
        )}

        {/* GPS Permission / Inaccuracy Notification Pill */}
        {gpsError && (
          <div
            style={{
              position: 'absolute',
              top: 80,
              left: 16,
              right: 16,
              maxWidth: 440,
              margin: '0 auto',
              zIndex: 490,
              backgroundColor: '#FEF3C7',
              border: '1px solid #F59E0B',
              borderRadius: 12,
              padding: '0.65rem 0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
              boxShadow: '0 4px 15px rgba(0, 0, 0, 0.08)'
            }}
          >
            <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0 }} />
            <div style={{ fontSize: '0.82rem', color: '#92400E', flex: 1 }}>{gpsError}</div>
            <button onClick={() => setGpsError(null)} style={{ color: '#92400E' }}>
              <X size={16} />
            </button>
          </div>
        )}

        {/* Arrival Celebration Card */}
        {hasArrived && (
          <div
            style={{
              position: 'absolute',
              top: '40%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 600,
              backgroundColor: '#FFFFFF',
              borderRadius: 20,
              padding: '2rem',
              maxWidth: 360,
              width: '90%',
              textAlign: 'center',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
              border: '2px solid #10B981'
            }}
            className="animate-slide-up"
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: '50%',
                backgroundColor: '#ECFDF5',
                color: '#10B981',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1rem'
              }}
            >
              <CheckCircle size={36} />
            </div>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#20252D', marginBottom: 6 }}>
              You Have Arrived!
            </h3>
            <p style={{ fontSize: '0.92rem', color: '#6B7280', marginBottom: '1.5rem' }}>
              You have reached your destination: <strong>{selectedDestination?.name}</strong>.
            </p>
            <button
              onClick={() => {
                setIsNavigating(false)
                setHasArrived(false)
              }}
              style={{
                width: '100%',
                backgroundColor: '#E66A27',
                color: '#FFFFFF',
                padding: '0.85rem',
                borderRadius: 12,
                fontSize: '1rem',
                fontWeight: 700
              }}
            >
              Finish Navigation
            </button>
          </div>
        )}

        {/* Bottom Route Preview & Details Sheet */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 450,
            backgroundColor: '#FFFFFF',
            borderTopLeftRadius: 22,
            borderTopRightRadius: 22,
            boxShadow: '0 -6px 30px rgba(0, 0, 0, 0.12)',
            padding: isSheetExpanded ? '1rem 1.25rem 1.25rem' : '0.75rem 1.25rem',
            maxHeight: isSheetExpanded ? 'clamp(220px, 36vh, 340px)' : '54px',
            overflowY: 'auto',
            transition: 'max-height 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
          }}
        >
          {/* Sheet Header / Drag Pill */}
          <div
            onClick={() => setIsSheetExpanded(!isSheetExpanded)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              marginBottom: isSheetExpanded ? '0.75rem' : 0
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: '#E66A27', letterSpacing: '0.05em' }}>
                Navigation Details
              </span>
              {userPos && (
                <span
                  style={{
                    fontSize: '0.72rem',
                    backgroundColor: '#ECFDF5',
                    color: '#065F46',
                    padding: '2px 8px',
                    borderRadius: 999,
                    fontWeight: 600
                  }}
                >
                  GPS ±{Math.round(userPos.accuracy)}m
                </span>
              )}
            </div>
            <button style={{ color: '#6B7280', padding: 4 }}>
              {isSheetExpanded ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
            </button>
          </div>

          {/* When Destination is Selected */}
          {selectedDestination ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#20252D' }}>
                    {selectedDestination.name}
                  </h3>
                  <div style={{ fontSize: '0.85rem', color: '#6B7280' }}>
                    {selectedDestination.category} • Block {selectedDestination.block_number || 'N/A'}
                  </div>
                </div>

                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '4px 10px',
                    borderRadius: 999,
                    backgroundColor: selectedDestination.verified ? '#ECFDF5' : '#FFFBEB',
                    color: selectedDestination.verified ? '#065F46' : '#B45309',
                    border: `1px solid ${selectedDestination.verified ? '#A7F3D0' : '#FDE68A'}`
                  }}
                >
                  {selectedDestination.verified ? '✓ Verified' : '⚠ Survey Pending'}
                </span>
              </div>

              {/* Origin to Destination indicator */}
              <div style={{ fontSize: '0.8rem', color: '#6B7280', marginBottom: '0.65rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 600 }}>From:</span>
                <span style={{ color: '#20252D', fontWeight: 700 }}>{selectedOrigin ? selectedOrigin.name : 'GPS'}</span>
                <span>→</span>
                <span style={{ fontWeight: 600 }}>To:</span>
                <span style={{ color: '#20252D', fontWeight: 700 }}>{selectedDestination.name}</span>
              </div>

              {loadingRoute && (
                <div style={{ fontSize: '0.82rem', color: '#E66A27', marginBottom: '0.5rem', fontWeight: 600 }}>
                  Calculating pedestrian route...
                </div>
              )}

              {/* Route status callout */}
              {routeData && (
                <div
                  style={{
                    backgroundColor: routeData.available ? '#FFF8F1' : '#F9FAFB',
                    border: `1px solid ${routeData.available ? '#FED7AA' : '#E5E7EB'}`,
                    borderRadius: 14,
                    padding: '0.85rem 1rem',
                    marginBottom: '1rem'
                  }}
                >
                  {routeData.available ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#6B7280', display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
                          <Footprints size={14} /> Distance
                        </div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#20252D', marginTop: 2 }}>
                          {routeData.distance ? (routeData.distance >= 1000 ? `${(routeData.distance/1000).toFixed(2)} km` : `${Math.round(routeData.distance)} m`) : '--'}
                        </div>
                      </div>

                      <div style={{ width: 1, height: 32, backgroundColor: '#E5E7EB' }} />

                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#6B7280', display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
                          <Clock size={14} /> Walking Time
                        </div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#E66A27', marginTop: 2 }}>
                          {routeData.duration ? `~${Math.ceil(routeData.duration / 60)} min` : '--'}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                      <Info size={18} color="#E66A27" style={{ flexShrink: 0, marginTop: 2 }} />
                      <div style={{ fontSize: '0.85rem', color: '#4B5563', lineHeight: 1.4 }}>
                        <div style={{ fontWeight: 700, color: '#20252D' }}>
                          Walking route not yet available. This area is awaiting mapping.
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: 10 }}>
                {!isNavigating ? (
                  <button
                    disabled={!routeData?.available}
                    onClick={() => {
                      if (routeData?.available) {
                        setIsNavigating(true)
                        setIsSheetExpanded(false)
                      }
                    }}
                    style={{
                      flex: 1,
                      backgroundColor: routeData?.available ? '#E66A27' : '#9CA3AF',
                      color: '#FFFFFF',
                      padding: '0.85rem',
                      borderRadius: 12,
                      fontSize: '0.95rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      cursor: routeData?.available ? 'pointer' : 'not-allowed',
                      boxShadow: routeData?.available ? '0 4px 14px rgba(230, 106, 39, 0.35)' : 'none',
                      border: 'none'
                    }}
                  >
                    <Navigation size={18} />
                    {routeData?.available ? 'Start Walking Navigation' : 'Route Awaiting Survey'}
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setIsNavigating(false)
                    }}
                    style={{
                      flex: 1,
                      backgroundColor: '#EF4444',
                      color: '#FFFFFF',
                      padding: '0.85rem',
                      borderRadius: 12,
                      fontSize: '1rem',
                      fontWeight: 700
                    }}
                  >
                    Exit Navigation
                  </button>
                )}

                <button
                  onClick={() => {
                    setDestinationId('')
                    setRouteData(null)
                  }}
                  style={{
                    backgroundColor: '#F3F4F6',
                    color: '#4B5563',
                    padding: '0.85rem 1.1rem',
                    borderRadius: 12,
                    fontSize: '0.9rem',
                    fontWeight: 600
                  }}
                >
                  Clear
                </button>
              </div>

              <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#9CA3AF', textAlign: 'center' }}>
                Tip: Keep your screen on while walking. Mobile browsers may suspend GPS if phone locks.
              </div>
            </div>
          ) : (
            /* When no destination selected */
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#20252D' }}>
                  Select a campus block to navigate
                </span>
                <span style={{ fontSize: '0.8rem', color: '#6B7280' }}>
                  {loadingLocations ? 'Loading...' : `${locations.length} locations`}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 180, overflowY: 'auto' }}>
                {locations.slice(0, 5).map(loc => (
                  <div
                    key={loc.id}
                    onClick={() => setDestinationId(String(loc.id))}
                    style={{
                      padding: '0.65rem 0.85rem',
                      borderRadius: 10,
                      backgroundColor: '#F9FAFB',
                      border: '1px solid #E5E7EB',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer'
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#20252D' }}>{loc.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6B7280' }}>{loc.category}</div>
                    </div>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        padding: '2px 8px',
                        borderRadius: 999,
                        backgroundColor: loc.verified ? '#ECFDF5' : '#F3F4F6',
                        color: loc.verified ? '#059669' : '#6B7280',
                        fontWeight: 600
                      }}
                    >
                      {loc.verified ? 'Verified' : 'Unverified'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen Search Modal */}
      {isSearchOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1100,
            backgroundColor: '#FFFFFF',
            display: 'flex',
            flexDirection: 'column'
          }}
          className="animate-fade-in"
        >
          {/* Search Header */}
          <div
            style={{
              padding: '1rem 1.25rem',
              borderBottom: '1px solid #E5E7EB',
              display: 'flex',
              alignItems: 'center',
              gap: 12
            }}
          >
            <button
              onClick={() => setIsSearchOpen(false)}
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                backgroundColor: '#F3F4F6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#4B5563'
              }}
            >
              <ArrowLeft size={20} />
            </button>

            <div
              style={{
                flex: 1,
                position: 'relative',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              <Search
                size={18}
                color="#9CA3AF"
                style={{ position: 'absolute', left: 12 }}
              />
              <input
                type="text"
                autoFocus
                placeholder="Search Block 34, BH4, Gate 1..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem 0.75rem 2.4rem',
                  borderRadius: 12,
                  border: '1px solid #E5E7EB',
                  backgroundColor: '#F9FAFB',
                  fontSize: '1rem',
                  fontWeight: 500
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{ position: 'absolute', right: 12, color: '#9CA3AF' }}
                >
                  <X size={18} />
                </button>
              )}
            </div>
          </div>

          {/* Search Results */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', color: '#6B7280', marginBottom: '0.75rem', letterSpacing: '0.04em' }}>
              Campus Locations ({filteredLocations.length})
            </div>

            {filteredLocations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {filteredLocations.map(loc => (
                  <div
                    key={loc.id}
                    onClick={() => handleSelectSearchResult(loc)}
                    style={{
                      padding: '0.85rem 1rem',
                      borderRadius: 12,
                      border: '1px solid #E5E7EB',
                      backgroundColor: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = '#E66A27')}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = '#E5E7EB')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div
                        style={{
                          width: 38,
                          height: 38,
                          borderRadius: 10,
                          backgroundColor: loc.verified ? '#ECFDF5' : '#FFF2E8',
                          color: loc.verified ? '#10B981' : '#E66A27',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 800,
                          fontSize: '0.9rem'
                        }}
                      >
                        {loc.block_number || <MapPin size={18} />}
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '0.98rem', color: '#20252D' }}>
                          {loc.name}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#6B7280' }}>
                          {loc.category}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          padding: '3px 8px',
                          borderRadius: 999,
                          backgroundColor: loc.verified ? '#ECFDF5' : '#F3F4F6',
                          color: loc.verified ? '#065F46' : '#6B7280',
                          fontWeight: 600
                        }}
                      >
                        {loc.verified ? 'Verified' : 'Survey Pending'}
                      </span>
                      <ArrowRight size={16} color="#9CA3AF" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#6B7280' }}>
                <Compass size={40} color="#D1D5DB" style={{ margin: '0 auto 1rem' }} />
                <div style={{ fontWeight: 700, color: '#20252D', fontSize: '1.05rem', marginBottom: 4 }}>
                  No campus locations found
                </div>
                <div style={{ fontSize: '0.88rem' }}>
                  No block matching "{searchQuery}". Try searching for "Block 34" or "Block 28".
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
