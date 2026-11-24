import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Shield,
  AlertTriangle,
  MapPin,
  Layers,
  ArrowLeft,
  Building,
  History,
  Compass,
  Footprints,
  LogOut,
  RefreshCw
} from 'lucide-react'
import {
  fetchPendingVerification,
  submitVerificationEvidence,
  reviewVerificationEvidence,
  verifyBuildingEntrance,
  fetchVerificationHistory
} from './api'
import type {
  VerificationPendingData,
  AuditLogItem
} from './types'

export default function VerificationPage() {
  const navigate = useNavigate()
  const [token] = useState(() => sessionStorage.getItem('lpu_token') || '')
  const [activeTab, setActiveTab] = useState<'tracks' | 'gaps' | 'entrances' | 'audit'>('tracks')

  // Data state
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<VerificationPendingData | null>(null)
  const [history, setHistory] = useState<AuditLogItem[]>([])
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  // Evidence modal / form state
  const [evidenceModalTarget, setEvidenceModalTarget] = useState<{ type: string; id: string; title: string } | null>(null)
  const [observerName, setObserverName] = useState('')
  const [surfaceType, setSurfaceType] = useState('paved_concrete')
  const [isAccessible, setIsAccessible] = useState(true)
  const [isLit, setIsLit] = useState(true)
  const [notes, setNotes] = useState('')
  const [gpsStartLat, setGpsStartLat] = useState('')
  const [gpsStartLon, setGpsStartLon] = useState('')
  const [gpsEndLat, setGpsEndLat] = useState('')
  const [gpsEndLon, setGpsEndLon] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [submittingEvidence, setSubmittingEvidence] = useState(false)

  // Review modal state
  const [reviewModalTarget, setReviewModalTarget] = useState<{ evidenceId: number; title: string; action: 'approve' | 'reject' } | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')
  const [submittingReview, setSubmittingReview] = useState(false)

  // Entrance registration form state
  const [selectedLocationId, setSelectedLocationId] = useState<number>(4) // default Block 34
  const [entranceLat, setEntranceLat] = useState('31.251520')
  const [entranceLon, setEntranceLon] = useState('75.705050')
  const [doorName, setDoorName] = useState('Main North Entrance')
  const [verificationSource, setVerificationSource] = useState('Physical Doorway GPS Reading')
  const [submittingEntrance, setSubmittingEntrance] = useState(false)

  // Check authentication
  useEffect(() => {
    if (!token) {
      navigate('/admin/login')
    }
  }, [token, navigate])

  const loadData = async () => {
    if (!token) return
    setLoading(true)
    const pendingData = await fetchPendingVerification(token)
    if (pendingData) {
      setData(pendingData)
    }
    const auditLogs = await fetchVerificationHistory(token, 100)
    setHistory(auditLogs)
    setLoading(false)
  }

  useEffect(() => {
    loadData()
  }, [token])

  const handleLogout = () => {
    sessionStorage.removeItem('lpu_token')
    navigate('/admin/login')
  }

  // Handle Evidence Submission
  const handleSubmitEvidence = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!evidenceModalTarget || !token) return
    if (!notes || notes.trim().length < 5) {
      setMessage({ text: 'Field observation notes must contain at least 5 characters.', type: 'error' })
      return
    }

    setSubmittingEvidence(true)
    const payload: any = {
      target_type: evidenceModalTarget.type,
      target_id: evidenceModalTarget.id,
      observer_name: observerName.trim() || 'Administrator Surveyor',
      surface_type: surfaceType,
      is_accessible: isAccessible,
      is_lit: isLit,
      notes: notes.trim(),
      image_url: imageUrl.trim() || null
    }

    if (gpsStartLat && gpsStartLon) {
      payload.gps_start_lat = parseFloat(gpsStartLat)
      payload.gps_start_lon = parseFloat(gpsStartLon)
    }
    if (gpsEndLat && gpsEndLon) {
      payload.gps_end_lat = parseFloat(gpsEndLat)
      payload.gps_end_lon = parseFloat(gpsEndLon)
    }

    const res = await submitVerificationEvidence(token, payload)
    setSubmittingEvidence(false)
    if (res.success) {
      setMessage({ text: `Field evidence for ${evidenceModalTarget.title} submitted successfully!`, type: 'success' })
      setEvidenceModalTarget(null)
      setNotes('')
      loadData()
    } else {
      setMessage({ text: res.error || 'Failed to submit evidence.', type: 'error' })
    }
  }

  // Handle Review (Approve/Reject)
  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!reviewModalTarget || !token) return
    if (!reviewNotes || reviewNotes.trim().length < 3) {
      setMessage({ text: 'Review rationale is required (at least 3 characters).', type: 'error' })
      return
    }

    setSubmittingReview(true)
    const res = await reviewVerificationEvidence(token, {
      evidence_id: reviewModalTarget.evidenceId,
      action: reviewModalTarget.action,
      review_notes: reviewNotes.trim()
    })
    setSubmittingReview(false)
    if (res.success) {
      setMessage({
        text: `Evidence ${reviewModalTarget.action === 'approve' ? 'approved' : 'rejected'} successfully.`,
        type: 'success'
      })
      setReviewModalTarget(null)
      setReviewNotes('')
      loadData()
    } else {
      setMessage({ text: res.error || 'Failed to process review.', type: 'error' })
    }
  }

  // Handle Entrance Registration
  const handleSubmitEntrance = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    const lat = parseFloat(entranceLat)
    const lon = parseFloat(entranceLon)

    if (isNaN(lat) || isNaN(lon)) {
      setMessage({ text: 'Please enter valid numerical latitude and longitude.', type: 'error' })
      return
    }

    setSubmittingEntrance(true)
    const res = await verifyBuildingEntrance(token, {
      location_id: selectedLocationId,
      entrance_latitude: lat,
      entrance_longitude: lon,
      door_name: doorName.trim() || 'Main Entrance',
      verification_source: verificationSource.trim()
    })
    setSubmittingEntrance(false)
    if (res.success) {
      setMessage({ text: `Building entrance verified and registered successfully for Block ${res.data?.block_number || ''}!`, type: 'success' })
      loadData()
    } else {
      setMessage({ text: res.error || 'Failed to verify entrance.', type: 'error' })
    }
  }

  // Use current GPS coordinates for entrance
  const useCurrentGps = () => {
    if (!navigator.geolocation) {
      setMessage({ text: 'Geolocation is not supported by your browser.', type: 'error' })
      return
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        setEntranceLat(pos.coords.latitude.toFixed(6))
        setEntranceLon(pos.coords.longitude.toFixed(6))
        setMessage({ text: `Captured device GPS coordinates (±${Math.round(pos.coords.accuracy)}m).`, type: 'success' })
      },
      err => {
        setMessage({ text: `GPS error: ${err.message}`, type: 'error' })
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FAF8F5', fontFamily: 'var(--font-main, sans-serif)', padding: '1.5rem 1rem' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        
        {/* Navigation Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <Link to="/" style={{ color: '#6B7280', textDecoration: 'none', fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              <ArrowLeft size={16} /> Campus Map
            </Link>
            <span style={{ color: '#D1D5DB' }}>|</span>
            <Link to="/admin/survey" style={{ color: '#E66A27', textDecoration: 'none', fontSize: '0.88rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Compass size={16} /> GPS Survey Tool
            </Link>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '0.82rem', backgroundColor: '#ECFDF5', color: '#065F46', padding: '4px 10px', borderRadius: 999, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Shield size={14} /> Administrator Verified Session
            </span>
            <button
              onClick={handleLogout}
              style={{
                backgroundColor: '#F3F4F6',
                border: '1px solid #E5E7EB',
                color: '#4B5563',
                padding: '5px 10px',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                cursor: 'pointer'
              }}
            >
              <LogOut size={14} /> Logout
            </button>
          </div>
        </div>

        {/* Page Title & Mission */}
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: 16, padding: '1.5rem', marginBottom: '1.5rem', border: '1px solid #E5E7EB', boxShadow: '0 4px 15px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#20252D', margin: '0 0 4px' }}>
                Pedestrian Route Verification System
              </h1>
              <p style={{ color: '#6B7280', fontSize: '0.9rem', margin: 0 }}>
                Review GPS recordings, record ground-truth field observations, register building entrances, and maintain decision audits.
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              style={{
                backgroundColor: '#FFF2E8',
                border: '1px solid #FED7AA',
                color: '#E66A27',
                padding: '7px 12px',
                borderRadius: 8,
                fontSize: '0.85rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> {loading ? 'Loading...' : 'Refresh Data'}
            </button>
          </div>

          {/* Quick Metrics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: '1.25rem' }}>
            <div style={{ backgroundColor: '#F9FAFB', padding: '12px 14px', borderRadius: 10, border: '1px solid #E5E7EB' }}>
              <div style={{ fontSize: '0.75rem', color: '#6B7280', textTransform: 'uppercase', fontWeight: 700 }}>Survey Tracks</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#20252D', marginTop: 2 }}>
                {data ? `${data.verified_tracks_count} / ${data.total_tracks_count}` : '--'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#B45309', fontWeight: 600, marginTop: 2 }}>
                {data?.verified_tracks_count === data?.total_tracks_count && data?.total_tracks_count ? '✓ Fully Verified' : '⚠ Survey Review Pending'}
              </div>
            </div>

            <div style={{ backgroundColor: '#F9FAFB', padding: '12px 14px', borderRadius: 10, border: '1px solid #E5E7EB' }}>
              <div style={{ fontSize: '0.75rem', color: '#6B7280', textTransform: 'uppercase', fontWeight: 700 }}>Unrecorded Gaps</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#20252D', marginTop: 2 }}>
                {data ? `${data.gaps.filter(g => g.verified).length} / ${data.gaps.length}` : '0 / 3'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6B7280', fontWeight: 600, marginTop: 2 }}>
                Includes 73.6m Block 34 indoor passage
              </div>
            </div>

            <div style={{ backgroundColor: '#F9FAFB', padding: '12px 14px', borderRadius: 10, border: '1px solid #E5E7EB' }}>
              <div style={{ fontSize: '0.75rem', color: '#6B7280', textTransform: 'uppercase', fontWeight: 700 }}>Building Entrances</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#20252D', marginTop: 2 }}>
                {data ? `${data.verified_locations_count} / ${data.total_locations_count}` : '--'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600, marginTop: 2 }}>
                Blocks 28, 29, 30, 34, 36
              </div>
            </div>

            <div style={{ backgroundColor: '#F9FAFB', padding: '12px 14px', borderRadius: 10, border: '1px solid #E5E7EB' }}>
              <div style={{ fontSize: '0.75rem', color: '#6B7280', textTransform: 'uppercase', fontWeight: 700 }}>Routing Safety Status</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#B45309', marginTop: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
                <AlertTriangle size={16} /> Restricted to Ground Truth
              </div>
              <div style={{ fontSize: '0.72rem', color: '#6B7280', marginTop: 2 }}>
                No automated interpolation allowed
              </div>
            </div>
          </div>
        </div>

        {/* Feedback Alert Pill */}
        {message && (
          <div
            style={{
              padding: '0.85rem 1rem',
              borderRadius: 10,
              marginBottom: '1.25rem',
              backgroundColor: message.type === 'success' ? '#ECFDF5' : '#FEF2F2',
              color: message.type === 'success' ? '#065F46' : '#991B1B',
              border: `1px solid ${message.type === 'success' ? '#A7F3D0' : '#FECACA'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.9rem',
              fontWeight: 600
            }}
          >
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 800 }}>
              ✕
            </button>
          </div>
        )}

        {/* Main Tab Navigation */}
        <div style={{ display: 'flex', borderBottom: '2px solid #E5E7EB', marginBottom: '1.5rem', gap: 8 }}>
          <button
            onClick={() => setActiveTab('tracks')}
            style={{
              padding: '0.75rem 1.25rem',
              border: 'none',
              borderBottom: activeTab === 'tracks' ? '3px solid #E66A27' : '3px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'tracks' ? '#E66A27' : '#6B7280',
              fontWeight: 700,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Layers size={17} /> GPS Survey Tracks ({data?.total_tracks_count || 4})
          </button>

          <button
            onClick={() => setActiveTab('gaps')}
            style={{
              padding: '0.75rem 1.25rem',
              border: 'none',
              borderBottom: activeTab === 'gaps' ? '3px solid #E66A27' : '3px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'gaps' ? '#E66A27' : '#6B7280',
              fontWeight: 700,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Footprints size={17} /> Unrecorded Gaps (3)
          </button>

          <button
            onClick={() => setActiveTab('entrances')}
            style={{
              padding: '0.75rem 1.25rem',
              border: 'none',
              borderBottom: activeTab === 'entrances' ? '3px solid #E66A27' : '3px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'entrances' ? '#E66A27' : '#6B7280',
              fontWeight: 700,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Building size={17} /> Building Entrances ({data?.total_locations_count || 5})
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            style={{
              padding: '0.75rem 1.25rem',
              border: 'none',
              borderBottom: activeTab === 'audit' ? '3px solid #E66A27' : '3px solid transparent',
              backgroundColor: 'transparent',
              color: activeTab === 'audit' ? '#E66A27' : '#6B7280',
              fontWeight: 700,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <History size={17} /> Audit History ({history.length})
          </button>
        </div>

        {/* Tab 1: Survey Tracks */}
        {activeTab === 'tracks' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <p style={{ color: '#4B5563', fontSize: '0.9rem', margin: 0 }}>
                Original OsmAnd GPS survey recordings. Verification requires explicit review supported by real field observations.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {data?.tracks.map(track => (
                <div
                  key={track.target_id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: 14,
                    padding: '1.25rem',
                    border: '1px solid #E5E7EB',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.03)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#20252D', margin: 0 }}>
                          {track.segment_label}
                        </h3>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: 6,
                            backgroundColor: track.verified ? '#ECFDF5' : '#FFFBEB',
                            color: track.verified ? '#065F46' : '#B45309',
                            border: `1px solid ${track.verified ? '#A7F3D0' : '#FDE68A'}`
                          }}
                        >
                          {track.verified ? '✓ Verified Pathway' : '⚠ Survey Review Pending'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.82rem', color: '#6B7280', marginTop: 4 }}>
                        Source File: <code>{track.name}</code> • Length: <strong>{track.distance_m} m</strong> • Points: <strong>{track.point_count} pts</strong>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => {
                          setEvidenceModalTarget({
                            type: 'track',
                            id: track.target_id,
                            title: track.segment_label
                          })
                        }}
                        style={{
                          backgroundColor: '#FFF2E8',
                          border: '1px solid #FED7AA',
                          color: '#E66A27',
                          padding: '6px 12px',
                          borderRadius: 8,
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          cursor: 'pointer'
                        }}
                      >
                        + Record Observation
                      </button>
                    </div>
                  </div>

                  {/* Endpoints & Coordinates */}
                  {track.start_coords && track.end_coords && (
                    <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.78rem', color: '#6B7280', backgroundColor: '#F9FAFB', padding: '6px 10px', borderRadius: 8 }}>
                      <div>Start: <strong>{track.start_coords.lat?.toFixed(6)}, {track.start_coords.lon?.toFixed(6)}</strong></div>
                      <div>End: <strong>{track.end_coords.lat?.toFixed(6)}, {track.end_coords.lon?.toFixed(6)}</strong></div>
                    </div>
                  )}

                  {/* Submitted Field Evidence list */}
                  {track.evidence && track.evidence.length > 0 && (
                    <div style={{ marginTop: 12, borderTop: '1px solid #F3F4F6', paddingTop: 10 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', marginBottom: 6 }}>
                        Field Observations & Review ({track.evidence.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {track.evidence.map(ev => (
                          <div
                            key={ev.id}
                            style={{
                              backgroundColor: '#FAF8F5',
                              borderRadius: 8,
                              padding: '8px 12px',
                              fontSize: '0.82rem',
                              border: '1px solid #E5E7EB'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                              <span style={{ fontWeight: 700, color: '#20252D' }}>By {ev.observer_name}</span>
                              <span
                                style={{
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  backgroundColor: ev.status === 'approved' ? '#ECFDF5' : ev.status === 'rejected' ? '#FEF2F2' : '#FFFBEB',
                                  color: ev.status === 'approved' ? '#065F46' : ev.status === 'rejected' ? '#991B1B' : '#B45309'
                                }}
                              >
                                {ev.status}
                              </span>
                            </div>
                            <div style={{ color: '#4B5563', lineHeight: 1.4 }}>{ev.notes}</div>

                            {/* Pending actions for review */}
                            {ev.status === 'pending' && (
                              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                <button
                                  onClick={() => setReviewModalTarget({ evidenceId: ev.id, title: track.segment_label, action: 'approve' })}
                                  style={{ backgroundColor: '#10B981', color: '#fff', border: 'none', padding: '4px 10px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer' }}
                                >
                                  ✓ Approve Evidence
                                </button>
                                <button
                                  onClick={() => setReviewModalTarget({ evidenceId: ev.id, title: track.segment_label, action: 'reject' })}
                                  style={{ backgroundColor: '#EF4444', color: '#fff', border: 'none', padding: '4px 10px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer' }}
                                >
                                  ✕ Reject Evidence
                                </button>
                              </div>
                            )}

                            {ev.review_notes && (
                              <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: 4, fontStyle: 'italic' }}>
                                Reviewer note ({ev.reviewed_by}): {ev.review_notes}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 2: Unrecorded Gaps */}
        {activeTab === 'gaps' && (
          <div>
            <div style={{ backgroundColor: '#FFFBEB', border: '1px solid #FDE68A', padding: '12px 16px', borderRadius: 12, marginBottom: '1.25rem', fontSize: '0.88rem', color: '#92400E' }}>
              <strong>Important Geospatial Rule:</strong> Gaps between consecutive GPS survey recordings represent deliberate pauses or indoor physical passages. Do not interpolate across them automatically. Connections require explicit on-site evidence and endpoint validation.
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {data?.gaps.map(gap => (
                <div
                  key={gap.target_id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: 14,
                    padding: '1.25rem',
                    border: '1px solid #E5E7EB',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.03)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#20252D', margin: 0 }}>
                          Gap {gap.gap_index}: {gap.from_recording.replace('.gpx', '')} → {gap.to_recording.replace('.gpx', '')}
                        </h3>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: 6,
                            backgroundColor: gap.verified ? '#ECFDF5' : '#FEF3C7',
                            color: gap.verified ? '#065F46' : '#92400E',
                            border: `1px solid ${gap.verified ? '#A7F3D0' : '#FDE68A'}`
                          }}
                        >
                          {gap.verified ? '✓ Verified Connection' : '⚠ Unrecorded Physical Gap'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.85rem', color: '#4B5563', marginTop: 4 }}>
                        Physical Displacement: <strong>{gap.displacement_meters} meters</strong>
                        {gap.is_indoor_corridor && (
                          <span style={{ marginLeft: 8, color: '#B45309', fontWeight: 700 }}>
                            (Block 34 Ground Floor Indoor Passage)
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setEvidenceModalTarget({
                          type: 'gap',
                          id: gap.target_id,
                          title: `Gap ${gap.gap_index} (${gap.displacement_meters}m)`
                        })
                        if (gap.from_endpoint) {
                          setGpsStartLat(gap.from_endpoint.lat.toString())
                          setGpsStartLon(gap.from_endpoint.lon.toString())
                        }
                        if (gap.to_startpoint) {
                          setGpsEndLat(gap.to_startpoint.lat.toString())
                          setGpsEndLon(gap.to_startpoint.lon.toString())
                        }
                      }}
                      style={{
                        backgroundColor: '#FFF2E8',
                        border: '1px solid #FED7AA',
                        color: '#E66A27',
                        padding: '6px 12px',
                        borderRadius: 8,
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      + Record Gap Observation
                    </button>
                  </div>

                  {gap.from_endpoint && gap.to_startpoint && (
                    <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.78rem', color: '#6B7280', backgroundColor: '#F9FAFB', padding: '6px 10px', borderRadius: 8 }}>
                      <div>From: <strong>{gap.from_endpoint.lat.toFixed(6)}, {gap.from_endpoint.lon.toFixed(6)}</strong></div>
                      <div>To: <strong>{gap.to_startpoint.lat.toFixed(6)}, {gap.to_startpoint.lon.toFixed(6)}</strong></div>
                    </div>
                  )}

                  {/* Submitted Field Evidence list */}
                  {gap.evidence && gap.evidence.length > 0 && (
                    <div style={{ marginTop: 12, borderTop: '1px solid #F3F4F6', paddingTop: 10 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', marginBottom: 6 }}>
                        Field Observations ({gap.evidence.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {gap.evidence.map(ev => (
                          <div
                            key={ev.id}
                            style={{
                              backgroundColor: '#FAF8F5',
                              borderRadius: 8,
                              padding: '8px 12px',
                              fontSize: '0.82rem',
                              border: '1px solid #E5E7EB'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                              <span style={{ fontWeight: 700, color: '#20252D' }}>By {ev.observer_name}</span>
                              <span
                                style={{
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  backgroundColor: ev.status === 'approved' ? '#ECFDF5' : ev.status === 'rejected' ? '#FEF2F2' : '#FFFBEB',
                                  color: ev.status === 'approved' ? '#065F46' : ev.status === 'rejected' ? '#991B1B' : '#B45309'
                                }}
                              >
                                {ev.status}
                              </span>
                            </div>
                            <div style={{ color: '#4B5563', lineHeight: 1.4 }}>{ev.notes}</div>

                            {ev.status === 'pending' && (
                              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                <button
                                  onClick={() => setReviewModalTarget({ evidenceId: ev.id, title: `Gap ${gap.gap_index}`, action: 'approve' })}
                                  style={{ backgroundColor: '#10B981', color: '#fff', border: 'none', padding: '4px 10px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer' }}
                                >
                                  ✓ Approve Evidence
                                </button>
                                <button
                                  onClick={() => setReviewModalTarget({ evidenceId: ev.id, title: `Gap ${gap.gap_index}`, action: 'reject' })}
                                  style={{ backgroundColor: '#EF4444', color: '#fff', border: 'none', padding: '4px 10px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer' }}
                                >
                                  ✕ Reject Evidence
                                </button>
                              </div>
                            )}

                            {ev.review_notes && (
                              <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: 4, fontStyle: 'italic' }}>
                                Reviewer note ({ev.reviewed_by}): {ev.review_notes}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: Building Entrances */}
        {activeTab === 'entrances' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
            {/* Registration Form */}
            <div style={{ backgroundColor: '#FFFFFF', borderRadius: 16, padding: '1.5rem', border: '1px solid #E5E7EB', boxShadow: '0 4px 15px rgba(0,0,0,0.04)' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#20252D', marginTop: 0, marginBottom: 6 }}>
                Register Verified Doorway
              </h3>
              <p style={{ color: '#6B7280', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
                Record verified ground-truth GPS doorway coordinates for campus buildings.
              </p>

              <form onSubmit={handleSubmitEntrance} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                    Select Building / Facility
                  </label>
                  <select
                    value={selectedLocationId}
                    onChange={e => setSelectedLocationId(Number(e.target.value))}
                    style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.9rem' }}
                  >
                    {data?.locations.map(loc => (
                      <option key={loc.id} value={loc.id}>
                        {loc.name} {loc.block_number ? `(Block ${loc.block_number})` : ''} - {loc.category}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                      Entrance Latitude
                    </label>
                    <input
                      type="text"
                      value={entranceLat}
                      onChange={e => setEntranceLat(e.target.value)}
                      placeholder="e.g. 31.251520"
                      style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.85rem', boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                      Entrance Longitude
                    </label>
                    <input
                      type="text"
                      value={entranceLon}
                      onChange={e => setEntranceLon(e.target.value)}
                      placeholder="e.g. 75.705050"
                      style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.85rem', boxSizing: 'border-box' }}
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={useCurrentGps}
                  style={{
                    backgroundColor: '#F3F4F6',
                    border: '1px solid #D1D5DB',
                    color: '#374151',
                    padding: '6px 10px',
                    borderRadius: 8,
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6
                  }}
                >
                  <MapPin size={14} color="#E66A27" /> Use Current Device GPS Coordinates
                </button>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                    Doorway / Portal Name
                  </label>
                  <input
                    type="text"
                    value={doorName}
                    onChange={e => setDoorName(e.target.value)}
                    placeholder="e.g. North Main Entrance"
                    style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.85rem', boxSizing: 'border-box' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                    Verification Source
                  </label>
                  <input
                    type="text"
                    value={verificationSource}
                    onChange={e => setVerificationSource(e.target.value)}
                    placeholder="e.g. On-site GPS Survey"
                    style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.85rem', boxSizing: 'border-box' }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={submittingEntrance}
                  style={{
                    backgroundColor: '#E66A27',
                    color: '#FFFFFF',
                    border: 'none',
                    padding: '0.75rem',
                    borderRadius: 10,
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    cursor: submittingEntrance ? 'not-allowed' : 'pointer',
                    marginTop: 6
                  }}
                >
                  {submittingEntrance ? 'Saving...' : 'Register Verified Entrance'}
                </button>
              </form>
            </div>

            {/* List of Locations & Entrance Status */}
            <div style={{ backgroundColor: '#FFFFFF', borderRadius: 16, padding: '1.5rem', border: '1px solid #E5E7EB', boxShadow: '0 4px 15px rgba(0,0,0,0.04)' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#20252D', marginTop: 0, marginBottom: 12 }}>
                Campus Buildings ({data?.locations.length || 0})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data?.locations.map(loc => (
                  <div
                    key={loc.id}
                    style={{
                      border: '1px solid #E5E7EB',
                      borderRadius: 10,
                      padding: '10px 14px',
                      backgroundColor: loc.verified ? '#F0FDF4' : '#F9FAFB'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 800, color: '#20252D', fontSize: '0.92rem' }}>
                        {loc.name}
                      </span>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 999,
                          backgroundColor: loc.verified ? '#DCFCE7' : '#FEF3C7',
                          color: loc.verified ? '#166534' : '#92400E',
                          border: `1px solid ${loc.verified ? '#BBF7D0' : '#FDE68A'}`
                        }}
                      >
                        {loc.verified ? '✓ Verified Doorway' : '⚠ Survey Pending'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: '#6B7280', marginTop: 4 }}>
                      {loc.category} • Block {loc.block_number || 'N/A'}
                    </div>

                    {loc.entrance_latitude && loc.entrance_longitude ? (
                      <div style={{ fontSize: '0.78rem', color: '#374151', marginTop: 4, fontFamily: 'monospace' }}>
                        Doorway: {loc.entrance_latitude.toFixed(6)}, {loc.entrance_longitude.toFixed(6)}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: 4, fontStyle: 'italic' }}>
                        No verified doorway registered yet.
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Audit History */}
        {activeTab === 'audit' && (
          <div style={{ backgroundColor: '#FFFFFF', borderRadius: 16, padding: '1.5rem', border: '1px solid #E5E7EB', boxShadow: '0 4px 15px rgba(0,0,0,0.04)' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#20252D', marginTop: 0, marginBottom: 6 }}>
              Verification Decision Audit Log
            </h3>
            <p style={{ color: '#6B7280', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              Immutable chronological record of administrator field evidence reviews, doorway registrations, and approvals.
            </p>

            {history.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#9CA3AF', fontSize: '0.9rem' }}>
                No audit events recorded yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {history.map(item => (
                  <div
                    key={item.id}
                    style={{
                      border: '1px solid #E5E7EB',
                      borderRadius: 10,
                      padding: '10px 14px',
                      backgroundColor: '#FAF8F5'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 800,
                            padding: '3px 8px',
                            borderRadius: 6,
                            textTransform: 'uppercase',
                            backgroundColor:
                              item.action === 'APPROVE_EVIDENCE'
                                ? '#DCFCE7'
                                : item.action === 'REJECT_EVIDENCE'
                                ? '#FEE2E2'
                                : '#E0E7FF',
                            color:
                              item.action === 'APPROVE_EVIDENCE'
                                ? '#166534'
                                : item.action === 'REJECT_EVIDENCE'
                                ? '#991B1B'
                                : '#3730A3'
                          }}
                        >
                          {item.action}
                        </span>
                        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#20252D' }}>
                          Target: {item.target_type} ({item.target_id})
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        By <strong>{item.admin_username}</strong> • {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                      </div>
                    </div>

                    {item.details && (
                      <div style={{ fontSize: '0.8rem', color: '#4B5563', marginTop: 6, backgroundColor: '#FFFFFF', padding: '6px 10px', borderRadius: 6, border: '1px solid #F3F4F6' }}>
                        {item.details.rationale && <div><strong>Rationale:</strong> {item.details.rationale}</div>}
                        {item.details.door_name && <div><strong>Doorway:</strong> {item.details.door_name} ({item.details.latitude}, {item.details.longitude})</div>}
                        {item.details.notes && <div><strong>Observations:</strong> {item.details.notes}</div>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Evidence Submission Modal */}
      {evidenceModalTarget && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 16
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 16,
            padding: '1.75rem',
            maxWidth: 500,
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#20252D', marginTop: 0 }}>
              Record Field Evidence: {evidenceModalTarget.title}
            </h3>
            <form onSubmit={handleSubmitEvidence} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                  Surveyor / Observer Name *
                </label>
                <input
                  type="text"
                  required
                  value={observerName}
                  onChange={e => setObserverName(e.target.value)}
                  placeholder="e.g. Swastik (Lead Surveyor)"
                  style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.9rem', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                  Surface Type
                </label>
                <select
                  value={surfaceType}
                  onChange={e => setSurfaceType(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.9rem' }}
                >
                  <option value="paved_concrete">Paved Concrete Pavers</option>
                  <option value="tile_indoor_corridor">Ground Floor Tile Corridor</option>
                  <option value="asphalt">Asphalt Roadway / Walkway</option>
                  <option value="gravel">Gravel / Unpaved</option>
                  <option value="stairs">Staircase (Non-accessible)</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={isAccessible} onChange={e => setIsAccessible(e.target.checked)} />
                  Step-free Accessible
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={isLit} onChange={e => setIsLit(e.target.checked)} />
                  Night Lighting Available
                </label>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                  Detailed Field Observations *
                </label>
                <textarea
                  required
                  rows={3}
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Describe ground conditions, obstacles, doorway width, pavement quality..."
                  style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.9rem', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                  Photo / Document Reference URL (Optional)
                </label>
                <input
                  type="text"
                  value={imageUrl}
                  onChange={e => setImageUrl(e.target.value)}
                  placeholder="https://..."
                  style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.85rem', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                <button
                  type="button"
                  onClick={() => setEvidenceModalTarget(null)}
                  style={{ flex: 1, backgroundColor: '#F3F4F6', color: '#4B5563', border: '1px solid #D1D5DB', padding: '0.75rem', borderRadius: 8, fontWeight: 700, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingEvidence}
                  style={{ flex: 1, backgroundColor: '#E66A27', color: '#fff', border: 'none', padding: '0.75rem', borderRadius: 8, fontWeight: 700, cursor: submittingEvidence ? 'not-allowed' : 'pointer' }}
                >
                  {submittingEvidence ? 'Submitting...' : 'Submit Evidence'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Review Modal */}
      {reviewModalTarget && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 16
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: 16,
            padding: '1.75rem',
            maxWidth: 460,
            width: '100%'
          }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#20252D', marginTop: 0 }}>
              {reviewModalTarget.action === 'approve' ? 'Approve' : 'Reject'} Verification: {reviewModalTarget.title}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#6B7280' }}>
              Please provide the official administrator rationale. Decisions are permanently logged in the audit trail.
            </p>

            <form onSubmit={handleSubmitReview} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                  Administrator Review Rationale *
                </label>
                <textarea
                  required
                  rows={3}
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  placeholder={
                    reviewModalTarget.action === 'approve'
                      ? 'e.g. Field observations verified on-site; pathway is safe and step-free.'
                      : 'e.g. Inadequate pedestrian surface; path requires campus maintenance before approval.'
                  }
                  style={{ width: '100%', padding: '0.65rem', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: '0.9rem', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                <button
                  type="button"
                  onClick={() => setReviewModalTarget(null)}
                  style={{ flex: 1, backgroundColor: '#F3F4F6', color: '#4B5563', border: '1px solid #D1D5DB', padding: '0.75rem', borderRadius: 8, fontWeight: 700, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReview}
                  style={{
                    flex: 1,
                    backgroundColor: reviewModalTarget.action === 'approve' ? '#10B981' : '#EF4444',
                    color: '#fff',
                    border: 'none',
                    padding: '0.75rem',
                    borderRadius: 8,
                    fontWeight: 700,
                    cursor: submittingReview ? 'not-allowed' : 'pointer'
                  }}
                >
                  {submittingReview ? 'Processing...' : `Confirm ${reviewModalTarget.action === 'approve' ? 'Approval' : 'Rejection'}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}
