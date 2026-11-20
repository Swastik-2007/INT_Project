import React, { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Compass,
  Search,
  ArrowRight,
  Crosshair,
  Footprints,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Building,
  Map as MapIcon,
  ChevronRight,
  X
} from 'lucide-react'
import { Navbar } from './Navbar'
import { fetchLocations } from './api'
import type { CampusLocation, UserPosition } from './types'

export const HomePage: React.FC = () => {
  const navigate = useNavigate()

  // Campus Data
  const [locations, setLocations] = useState<CampusLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState<string>('All')

  // Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchFocused, setIsSearchFocused] = useState(false)

  // Route Quick Finder State
  const [selectedOrigin, setSelectedOrigin] = useState<string>('gps')
  const [selectedDestination, setSelectedDestination] = useState<string>('')

  // User GPS State
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'acquiring' | 'ready' | 'denied'>('idle')
  const [userPos, setUserPos] = useState<UserPosition | null>(null)
  const [gpsMsg, setGpsMsg] = useState<string>('')

  // Load locations on mount
  useEffect(() => {
    fetchLocations().then(data => {
      setLocations(data)
      setLoading(false)
    })
  }, [])

  // Acquire User GPS
  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setGpsStatus('denied')
      setGpsMsg('Geolocation is not supported by your device browser.')
      return
    }

    setGpsStatus('acquiring')
    setGpsMsg('Acquiring high-accuracy GPS fix...')

    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude, longitude, accuracy } = pos.coords
        setUserPos({
          lat: latitude,
          lon: longitude,
          accuracy,
          timestamp: pos.timestamp
        })
        setGpsStatus('ready')
        setGpsMsg(`Location acquired! (Accuracy: ±${Math.round(accuracy)}m)`)
        setSelectedOrigin('gps')
      },
      err => {
        setGpsStatus('denied')
        if (err.code === 1) {
          setGpsMsg('Location permission denied. Please enable location access in browser settings.')
        } else {
          setGpsMsg('Unable to retrieve GPS position. Please check your device location settings.')
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 5000
      }
    )
  }

  // Categories list
  const categories = ['All', 'Academic Block', 'Hostel', 'Gates & Entrances', 'Facilities']

  // Filtered locations
  const filteredLocations = useMemo(() => {
    let result = locations

    if (activeCategory !== 'All') {
      if (activeCategory === 'Academic Block') {
        result = result.filter(l => l.category.toLowerCase().includes('academic') || l.name.toLowerCase().includes('block'))
      } else if (activeCategory === 'Hostel') {
        result = result.filter(l => l.category.toLowerCase().includes('hostel') || l.name.toLowerCase().includes('bh') || l.name.toLowerCase().includes('gh'))
      } else if (activeCategory === 'Gates & Entrances') {
        result = result.filter(l => l.category.toLowerCase().includes('gate') || l.name.toLowerCase().includes('gate'))
      } else {
        result = result.filter(l => !l.category.toLowerCase().includes('academic') && !l.name.toLowerCase().includes('block'))
      }
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      result = result.filter(
        l =>
          l.name.toLowerCase().includes(q) ||
          (l.block_number && l.block_number.toLowerCase().includes(q)) ||
          l.category.toLowerCase().includes(q)
      )
    }

    return result
  }, [locations, activeCategory, searchQuery])

  // Navigate to map with selection
  const handleFindRoute = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDestination) return
    navigate(`/map?orig=${selectedOrigin}&dest=${selectedDestination}`)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: '#FAF8F5' }}>
      <Navbar />

      {/* Hero Section */}
      <section
        style={{
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid #E5E7EB',
          padding: '2rem 1.25rem 2.25rem',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        {/* Subtle decorative background gradient */}
        <div
          style={{
            position: 'absolute',
            top: -120,
            right: -120,
            width: 320,
            height: 320,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(230, 106, 39, 0.08) 0%, rgba(255, 255, 255, 0) 70%)',
            pointerEvents: 'none'
          }}
        />

        <div style={{ maxWidth: 800, margin: '0 auto', textAlign: 'center', position: 'relative', zIndex: 2 }}>
          {/* Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 12px',
              borderRadius: 999,
              backgroundColor: '#FFF2E8',
              color: '#E66A27',
              fontSize: '0.82rem',
              fontWeight: 700,
              marginBottom: '0.75rem',
              letterSpacing: '0.02em'
            }}
          >
            <Compass size={14} />
            LPU Campus Navigation
          </div>

          {/* Heading */}
          <h1
            style={{
              fontSize: 'clamp(2rem, 5vw, 2.75rem)',
              fontWeight: 800,
              color: '#20252D',
              lineHeight: 1.15,
              letterSpacing: '-0.03em',
              marginBottom: '0.75rem'
            }}
          >
            Find Your Way Around LPU
          </h1>

          {/* Subheading */}
          <p
            style={{
              fontSize: 'clamp(1rem, 2.5vw, 1.15rem)',
              color: '#6B7280',
              maxWidth: 540,
              margin: '0 auto 2rem',
              lineHeight: 1.5
            }}
          >
            Simple, smart walking navigation for students, faculty, and campus visitors.
          </p>

          {/* Main Hero Destination Search Input */}
          <div
            style={{
              maxWidth: 580,
              margin: '0 auto',
              position: 'relative',
              textAlign: 'left'
            }}
          >
            <div
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                backgroundColor: '#FFFFFF',
                borderRadius: 16,
                border: '2px solid #E5E7EB',
                boxShadow: '0 8px 30px rgba(0, 0, 0, 0.08)',
                padding: '0.35rem 0.5rem',
                transition: 'border-color 0.2s, box-shadow 0.2s'
              }}
            >
              <div style={{ padding: '0 0.75rem', color: '#E66A27', display: 'flex', alignItems: 'center' }}>
                <Search size={22} strokeWidth={2.4} />
              </div>

              <input
                type="text"
                placeholder="Where to? (e.g. Block 34, BH4, Gate 1...)"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onFocus={() => setIsSearchFocused(true)}
                style={{
                  flex: 1,
                  border: 'none',
                  backgroundColor: 'transparent',
                  padding: '0.75rem 0.25rem',
                  fontSize: '1.05rem',
                  fontWeight: 600,
                  color: '#20252D'
                }}
              />

              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{ padding: '0.5rem', color: '#9CA3AF' }}
                  aria-label="Clear search"
                >
                  <X size={18} />
                </button>
              )}

              <button
                onClick={() => {
                  if (filteredLocations.length > 0) {
                    navigate(`/map?dest=${filteredLocations[0].id}`)
                  } else {
                    navigate('/map')
                  }
                }}
                style={{
                  backgroundColor: '#E66A27',
                  color: '#FFFFFF',
                  padding: '0.75rem 1.25rem',
                  borderRadius: 12,
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  boxShadow: '0 4px 12px rgba(230, 106, 39, 0.35)'
                }}
              >
                <span>Navigate</span>
                <ArrowRight size={16} />
              </button>
            </div>

            {/* Instant Suggestions Dropdown when typing */}
            {isSearchFocused && searchQuery.trim() && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: 8,
                  backgroundColor: '#FFFFFF',
                  borderRadius: 16,
                  boxShadow: '0 12px 36px rgba(0, 0, 0, 0.15)',
                  border: '1px solid #E5E7EB',
                  zIndex: 200,
                  maxHeight: 280,
                  overflowY: 'auto',
                  padding: '0.5rem'
                }}
                className="animate-fade-in"
              >
                {filteredLocations.length > 0 ? (
                  filteredLocations.map(loc => (
                    <div
                      key={loc.id}
                      onClick={() => navigate(`/map?dest=${loc.id}`)}
                      style={{
                        padding: '0.75rem 1rem',
                        borderRadius: 10,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        transition: 'background-color 0.15s ease'
                      }}
                      onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#FFF8F1')}
                      onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 8,
                            backgroundColor: loc.verified ? '#ECFDF5' : '#FFF2E8',
                            color: loc.verified ? '#10B981' : '#E66A27',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 800,
                            fontSize: '0.85rem'
                          }}
                        >
                          {loc.block_number || '•'}
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: '0.92rem', color: '#20252D' }}>
                            {loc.name}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                            {loc.category}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span
                          style={{
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            color: loc.verified ? '#10B981' : '#F59E0B'
                          }}
                        >
                          {loc.verified ? 'Verified' : 'Survey Pending'}
                        </span>
                        <ChevronRight size={16} color="#9CA3AF" />
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ padding: '1.25rem', textAlign: 'center', color: '#6B7280', fontSize: '0.88rem' }}>
                    No matching location in current database.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Primary Actions Grid */}
      <section style={{ maxWidth: 1080, width: '100%', margin: '-1rem auto 2rem', padding: '0 1.25rem', position: 'relative', zIndex: 10 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1rem'
          }}
        >
          {/* Card 1: Use My Location */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: 18,
              padding: '1.25rem 1.4rem',
              boxShadow: '0 4px 15px rgba(0, 0, 0, 0.06)',
              border: '1px solid #E5E7EB',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease'
            }}
          >
            <div>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  backgroundColor: '#FFF2E8',
                  color: '#E66A27',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem'
                }}
              >
                <Crosshair size={22} />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#20252D', marginBottom: 4 }}>
                1. Use My Location
              </h3>
              <p style={{ fontSize: '0.88rem', color: '#6B7280', marginBottom: '1rem', lineHeight: 1.4 }}>
                Automatically detect your current campus walking position via phone GPS.
              </p>
            </div>

            <div>
              {gpsMsg && (
                <div
                  style={{
                    fontSize: '0.78rem',
                    padding: '6px 10px',
                    borderRadius: 8,
                    marginBottom: '0.75rem',
                    backgroundColor: gpsStatus === 'ready' ? '#ECFDF5' : '#FEF3C7',
                    color: gpsStatus === 'ready' ? '#065F46' : '#92400E',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}
                >
                  {gpsStatus === 'ready' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                  <span>{gpsMsg} {userPos && `(${userPos.lat.toFixed(4)}, ${userPos.lon.toFixed(4)})`}</span>
                </div>
              )}

              <button
                onClick={handleUseMyLocation}
                style={{
                  width: '100%',
                  padding: '0.7rem',
                  borderRadius: 10,
                  backgroundColor: gpsStatus === 'ready' ? '#ECFDF5' : '#20252D',
                  color: gpsStatus === 'ready' ? '#059669' : '#FFFFFF',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  border: gpsStatus === 'ready' ? '1px solid #A7F3D0' : 'none'
                }}
              >
                <Crosshair size={16} />
                <span>{gpsStatus === 'ready' ? 'GPS Active' : 'Acquire My GPS'}</span>
              </button>
            </div>
          </div>

          {/* Card 2: Interactive Campus Map */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: 18,
              padding: '1.25rem 1.4rem',
              boxShadow: '0 4px 15px rgba(0, 0, 0, 0.06)',
              border: '1px solid #E5E7EB',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  backgroundColor: '#ECFDF5',
                  color: '#10B981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem'
                }}
              >
                <MapIcon size={22} />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#20252D', marginBottom: 4 }}>
                2. Explore Campus Map
              </h3>
              <p style={{ fontSize: '0.88rem', color: '#6B7280', marginBottom: '1rem', lineHeight: 1.4 }}>
                Browse full interactive map with academic blocks, gates, and verified entrance pins.
              </p>
            </div>

            <Link
              to="/map"
              style={{
                width: '100%',
                padding: '0.7rem',
                borderRadius: 10,
                backgroundColor: '#E66A27',
                color: '#FFFFFF',
                fontWeight: 700,
                fontSize: '0.9rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                textDecoration: 'none',
                boxShadow: '0 3px 10px rgba(230, 106, 39, 0.25)'
              }}
            >
              <span>Open Campus Map</span>
              <ArrowRight size={16} />
            </Link>
          </div>

          {/* Card 3: Quick Walking Route */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: 18,
              padding: '1.25rem 1.4rem',
              boxShadow: '0 4px 15px rgba(0, 0, 0, 0.06)',
              border: '1px solid #E5E7EB',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  backgroundColor: '#EFF6FF',
                  color: '#3B82F6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem'
                }}
              >
                <Footprints size={22} />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#20252D', marginBottom: 4 }}>
                3. Find Walking Route
              </h3>
              <p style={{ fontSize: '0.88rem', color: '#6B7280', marginBottom: '1rem', lineHeight: 1.4 }}>
                Choose start and end locations to inspect routes, distance, and walking times.
              </p>
            </div>

            <form onSubmit={handleFindRoute} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <select
                value={selectedDestination}
                onChange={e => setSelectedDestination(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.65rem 0.8rem',
                  borderRadius: 10,
                  border: '1px solid #E5E7EB',
                  backgroundColor: '#F9FAFB',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  color: '#20252D'
                }}
              >
                <option value="">Select destination...</option>
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.category})
                  </option>
                ))}
              </select>

              <button
                type="submit"
                disabled={!selectedDestination}
                style={{
                  width: '100%',
                  padding: '0.7rem',
                  borderRadius: 10,
                  backgroundColor: selectedDestination ? '#20252D' : '#E5E7EB',
                  color: selectedDestination ? '#FFFFFF' : '#9CA3AF',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8
                }}
              >
                <span>View Route on Map</span>
                <ArrowRight size={16} />
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* Campus Blocks Directory Section */}
      <section style={{ maxWidth: 1080, width: '100%', margin: '0 auto 2.25rem', padding: '0 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#20252D' }}>
              Campus Locations Directory
            </h2>
            <p style={{ fontSize: '0.88rem', color: '#6B7280' }}>
              Real academic blocks and buildings registered in the LPU Wayfinder system.
            </p>
          </div>

          {/* Category Filter Pills */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  padding: '0.4rem 0.85rem',
                  borderRadius: 999,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  backgroundColor: activeCategory === cat ? '#E66A27' : '#FFFFFF',
                  color: activeCategory === cat ? '#FFFFFF' : '#4B5563',
                  border: `1px solid ${activeCategory === cat ? '#E66A27' : '#E5E7EB'}`,
                  boxShadow: activeCategory === cat ? '0 2px 6px rgba(230, 106, 39, 0.3)' : 'none'
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Locations Grid */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#6B7280' }}>
            Loading campus locations from database...
          </div>
        ) : filteredLocations.length > 0 ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: '1rem'
            }}
          >
            {filteredLocations.map(loc => (
              <div
                key={loc.id}
                onClick={() => navigate(`/map?dest=${loc.id}`)}
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: 14,
                  padding: '1.1rem 1.2rem',
                  border: '1px solid #E5E7EB',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  transition: 'all 0.18s ease'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#E66A27'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 6px 18px rgba(0, 0, 0, 0.08)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = '#E5E7EB'
                  e.currentTarget.style.transform = 'none'
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        backgroundColor: '#FFF2E8',
                        color: '#E66A27',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '0.9rem'
                      }}
                    >
                      {loc.block_number || <Building size={18} />}
                    </div>

                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 999,
                        backgroundColor: loc.verified ? '#ECFDF5' : '#FFFBEB',
                        color: loc.verified ? '#065F46' : '#B45309',
                        border: `1px solid ${loc.verified ? '#A7F3D0' : '#FDE68A'}`
                      }}
                    >
                      {loc.verified ? 'Verified' : 'Survey Pending'}
                    </span>
                  </div>

                  <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#20252D', marginBottom: 2 }}>
                    {loc.name}
                  </h4>
                  <div style={{ fontSize: '0.8rem', color: '#6B7280' }}>
                    {loc.category}
                  </div>
                </div>

                <div
                  style={{
                    marginTop: '1rem',
                    paddingTop: '0.75rem',
                    borderTop: '1px solid #F3F4F6',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.82rem',
                    color: '#E66A27',
                    fontWeight: 700
                  }}
                >
                  <span>View on Map</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: 16,
              padding: '3rem 1.5rem',
              textAlign: 'center',
              border: '1px solid #E5E7EB'
            }}
          >
            <Building size={40} color="#D1D5DB" style={{ margin: '0 auto 1rem' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#20252D', marginBottom: 4 }}>
              No locations match your filter
            </h3>
            <p style={{ fontSize: '0.88rem', color: '#6B7280' }}>
              Try searching for "Block 34" or select "All" categories.
            </p>
          </div>
        )}
      </section>

      {/* Helpful GPS & Campus Guide Section */}
      <section style={{ maxWidth: 1080, width: '100%', margin: '0 auto 2.5rem', padding: '0 1.25rem' }}>
        <div
          style={{
            backgroundColor: '#20252D',
            borderRadius: 20,
            padding: '2rem 1.75rem',
            color: '#FFFFFF',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1.75rem',
            alignItems: 'center'
          }}
        >
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 10px',
                borderRadius: 999,
                backgroundColor: 'rgba(230, 106, 39, 0.25)',
                color: '#FF9E66',
                fontSize: '0.78rem',
                fontWeight: 700,
                marginBottom: '0.75rem'
              }}
            >
              <HelpCircle size={14} />
              GPS & Permissions Guide
            </div>
            <h3 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '0.75rem' }}>
              Getting Accurate Campus Navigation
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#9CA3AF', lineHeight: 1.6 }}>
              LPU Wayfinder uses high-accuracy GPS directly in your smartphone browser. Follow these recommendations for best accuracy while walking:
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div
              style={{
                backgroundColor: '#2B313A',
                borderRadius: 12,
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12
              }}
            >
              <CheckCircle2 size={18} color="#10B981" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.85rem', color: '#D1D5DB' }}>
                <strong>Enable Location in Chrome/Safari:</strong> When prompted, tap "Allow While Visiting Site" to view your live position.
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#2B313A',
                borderRadius: 12,
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12
              }}
            >
              <CheckCircle2 size={18} color="#10B981" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.85rem', color: '#D1D5DB' }}>
                <strong>Keep Screen Awake:</strong> Mobile browsers may pause GPS background updates when the phone screen is locked.
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#2B313A',
                borderRadius: 12,
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12
              }}
            >
              <CheckCircle2 size={18} color="#10B981" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.85rem', color: '#D1D5DB' }}>
                <strong>Verified Entrances:</strong> Only surveyed walkways show connected routes. Unverified blocks display survey pending status.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        style={{
          marginTop: 'auto',
          backgroundColor: '#FFFFFF',
          borderTop: '1px solid #E5E7EB',
          padding: '2rem 1.25rem 2.5rem'
        }}
      >
        <div
          style={{
            maxWidth: 1080,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
            alignItems: 'center',
            textAlign: 'center'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800, color: '#20252D' }}>
            <Compass size={20} color="#E66A27" />
            <span>LPU Wayfinder</span>
          </div>

          <p style={{ fontSize: '0.82rem', color: '#6B7280', maxWidth: 480 }}>
            Lovely Professional University Campus Walking Navigation System. Designed for ease of use, high accuracy, and safety.
          </p>

          <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', fontWeight: 600, color: '#4B5563' }}>
            <Link to="/" style={{ textDecoration: 'none', color: '#4B5563' }}>Home</Link>
            <Link to="/map" style={{ textDecoration: 'none', color: '#4B5563' }}>Campus Map</Link>
            <Link to="/admin/login" style={{ textDecoration: 'none', color: '#9CA3AF' }}>Admin Survey</Link>
          </div>

          <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '0.5rem' }}>
            &copy; {new Date().getFullYear()} LPU Wayfinder. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
