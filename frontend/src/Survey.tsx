import { useEffect, useRef, useState, useCallback } from 'react'
import { set, get } from 'idb-keyval'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''
const DRAFT_KEY = 'lpu_survey_draft'
const INTERVAL_MS = 2500 // Record a point every 2.5 s

interface GpsPoint { lat: number; lon: number; acc: number; ts: number }

function toGeoJSON(points: GpsPoint[], name: string) {
  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { name, recorded_at: new Date().toISOString(), point_count: points.length },
      geometry: {
        type: 'LineString',
        coordinates: points.map(p => [p.lon, p.lat]),
      },
    }],
  }
}

function haversineMeters(a: GpsPoint, b: GpsPoint) {
  const R = 6371000
  const dLat = (b.lat - a.lat) * Math.PI / 180
  const dLon = (b.lon - a.lon) * Math.PI / 180
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s))
}

export default function Survey() {
  const [status, setStatus] = useState<'idle' | 'recording' | 'paused' | 'stopped'>('idle')
  const [points, setPoints] = useState<GpsPoint[]>([])
  const [current, setCurrent] = useState<GeolocationCoordinates | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [name, setName] = useState('')
  const [info, setInfo] = useState('')
  const [gpsError, setGpsError] = useState('')
  const [token] = useState(() => sessionStorage.getItem('lpu_token') || '')
  const watchId = useRef<number | null>(null)
  const lastPoint = useRef<GpsPoint | null>(null)
  const startTime = useRef<number>(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Restore draft on mount
  useEffect(() => {
    get(DRAFT_KEY).then((draft: any) => {
      if (draft && draft.points && draft.points.length > 0) {
        setPoints(draft.points)
        setName(draft.name || '')
        setStatus('stopped')
        setInfo(`✅ Draft restored: ${draft.points.length} point(s)`)
      }
    })
  }, [])

  const saveDraft = useCallback((pts: GpsPoint[], nm: string) => {
    set(DRAFT_KEY, { points: pts, name: nm, savedAt: Date.now() }).catch(() => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ points: pts, name: nm }))
    })
  }, [])

  function startRecording() {
    if (!navigator.geolocation) { setGpsError('Geolocation is not supported by this browser.'); return }
    setGpsError('')
    setStatus('recording')
    startTime.current = Date.now() - elapsed * 1000
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startTime.current) / 1000)), 500)

    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        setCurrent(pos.coords)
        setGpsError('')
        const now = Date.now()
        const p: GpsPoint = { lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy, ts: now }
        const last = lastPoint.current
        if (!last || (now - last.ts) >= INTERVAL_MS) {
          lastPoint.current = p
          setPoints(prev => {
            const next = [...prev, p]
            saveDraft(next, name)
            return next
          })
        }
      },
      (err) => setGpsError(`GPS Error: ${err.message}`),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
    )
  }

  function pauseRecording() {
    if (watchId.current !== null) { navigator.geolocation.clearWatch(watchId.current); watchId.current = null }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    setStatus('paused')
  }

  function resumeRecording() {
    setStatus('recording')
    startTime.current = Date.now() - elapsed * 1000
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startTime.current) / 1000)), 500)
    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        setCurrent(pos.coords)
        const now = Date.now()
        const p: GpsPoint = { lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy, ts: now }
        const last = lastPoint.current
        if (!last || (now - last.ts) >= INTERVAL_MS) {
          lastPoint.current = p
          setPoints(prev => {
            const next = [...prev, p]
            saveDraft(next, name)
            return next
          })
        }
      },
      (err) => setGpsError(`GPS Error: ${err.message}`),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
    )
  }

  function stopRecording() {
    if (watchId.current !== null) { navigator.geolocation.clearWatch(watchId.current); watchId.current = null }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    setStatus('stopped')
  }

  function exportGeoJSON() {
    if (points.length === 0) { setInfo('No points to export.'); return }
    const geo = toGeoJSON(points, name || 'LPU Survey')
    const blob = new Blob([JSON.stringify(geo, null, 2)], { type: 'application/geo+json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `lpu_survey_${Date.now()}.geojson`; a.click()
    URL.revokeObjectURL(url)
    setInfo('✅ GeoJSON exported to your downloads folder.')
  }

  async function saveToBackend() {
    if (points.length < 2) { setInfo('Need at least 2 GPS points to save.'); return }
    if (!name) { setInfo('Enter a name for this survey first.'); return }
    if (!token) { setInfo('Not logged in. Please log in first.'); return }
    const geo = toGeoJSON(points, name)
    try {
      const res = await fetch(`${BACKEND}/api/admin/surveys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, description: '', geojson: JSON.stringify(geo), verified: false }),
      })
      if (!res.ok) { setInfo('⚠️ Backend upload failed. Use Export to save locally.'); return }
      setInfo('✅ Survey saved to backend! Draft cleared.')
      set(DRAFT_KEY, null)
    } catch { setInfo('⚠️ Cannot reach backend. Use Export to save locally.') }
  }

  async function importGPX(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    const text = await file.text()
    const parser = new DOMParser()
    const doc = parser.parseFromString(text, 'application/xml')
    const trkpts = Array.from(doc.querySelectorAll('trkpt'))
    if (trkpts.length === 0) { setInfo('No track points found in GPX file.'); return }
    const imported: GpsPoint[] = trkpts.map(pt => ({
      lat: parseFloat(pt.getAttribute('lat') || '0'),
      lon: parseFloat(pt.getAttribute('lon') || '0'),
      acc: 5, ts: Date.now(),
    }))
    setPoints(imported)
    saveDraft(imported, name)
    setStatus('stopped')
    setInfo(`✅ GPX imported: ${imported.length} points.`)
  }

  function clearDraft() {
    setPoints([]); setStatus('idle'); setElapsed(0); lastPoint.current = null
    set(DRAFT_KEY, null); localStorage.removeItem(DRAFT_KEY)
    setInfo('Draft cleared.')
  }

  const totalDist = points.length >= 2
    ? points.reduce((acc, p, i) => i === 0 ? 0 : acc + haversineMeters(points[i - 1], p), 0)
    : 0
  const mins = Math.floor(elapsed / 60), secs = elapsed % 60

  const btn = (label: string, onClick: () => void, bg: string, disabled = false) => (
    <button onClick={onClick} disabled={disabled} style={{
      background: disabled ? '#ccc' : bg, color: '#fff', border: 'none',
      padding: '0.7rem 1.1rem', borderRadius: 8, fontSize: 15, fontWeight: 700,
      cursor: disabled ? 'not-allowed' : 'pointer', flex: '1 1 auto', minWidth: 110,
    }}>{label}</button>
  )

  return (
    <div style={{ fontFamily: 'var(--font-main, sans-serif)', maxWidth: 480, margin: '0 auto', padding: '1.25rem' }}>
      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <a href="/" style={{ color: '#E66A27', textDecoration: 'none', fontSize: 13, fontWeight: 700 }}>
          ← Back to Campus Navigation
        </a>
        <a href="/admin/verify" style={{ color: '#065F46', backgroundColor: '#ECFDF5', padding: '4px 10px', borderRadius: 6, textDecoration: 'none', fontSize: 12, fontWeight: 700, border: '1px solid #A7F3D0' }}>
          🛡️ Route Verification System →
        </a>
      </div>
      <h2 style={{ color: '#E66A27', margin: '0 0 0.35rem', fontWeight: 800 }}>📍 LPU GPS Survey Tool</h2>
      <p style={{ color: '#6B7280', marginBottom: '1rem', fontSize: 14 }}>Record an official walking route for LPU campus mapping.</p>

      {/* Name input */}
      <input
        placeholder="Survey name (e.g. BH4 to Block 34)"
        value={name} onChange={e => setName(e.target.value)}
        style={{ width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #ccc', fontSize: 15, marginBottom: '0.75rem', boxSizing: 'border-box' }}
      />

      {/* Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: '1rem' }}>
        {status === 'idle' || status === 'stopped'
          ? btn('▶ Start', startRecording, '#27ae60')
          : status === 'recording'
            ? btn('⏸ Pause', pauseRecording, '#e67e22')
            : btn('▶ Resume', resumeRecording, '#27ae60')}
        {btn('⏹ Stop', stopRecording, '#c0392b', status === 'idle' || status === 'stopped')}
        {btn('⬇ Export GeoJSON', exportGeoJSON, '#2980b9', points.length === 0)}
        {btn('☁ Save to Server', saveToBackend, '#7b2d8b', points.length < 2 || !token)}
        {btn('🗑 Clear Draft', clearDraft, '#7f8c8d', points.length === 0 && status === 'idle')}
      </div>

      {/* GPX import */}
      <label style={{ display: 'block', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: 14, color: '#555' }}>📂 Import GPX file: </span>
        <input type="file" accept=".gpx" onChange={importGPX} style={{ fontSize: 14 }} />
      </label>

      {/* Live stats */}
      <div style={{ background: '#f5f0fa', borderRadius: 10, padding: '0.75rem 1rem', marginBottom: '1rem', fontSize: 15 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <div>🔴 Status: <strong>{status}</strong></div>
          <div>⏱ Time: <strong>{String(mins).padStart(2,'0')}:{String(secs).padStart(2,'0')}</strong></div>
          <div>📍 Points: <strong>{points.length}</strong></div>
          <div>📏 Distance: <strong>{totalDist >= 1000 ? (totalDist/1000).toFixed(2)+' km' : Math.round(totalDist)+' m'}</strong></div>
          {current && <>
            <div>🌐 Lat: <strong>{current.latitude.toFixed(6)}</strong></div>
            <div>🌐 Lon: <strong>{current.longitude.toFixed(6)}</strong></div>
            <div>🎯 Accuracy: <strong>±{Math.round(current.accuracy)} m</strong></div>
          </>}
        </div>
        {gpsError && <p style={{ color: 'red', marginTop: 8, fontSize: 13 }}>{gpsError}</p>}
      </div>

      {/* Info / status messages */}
      {info && <p style={{ background: '#e8f5e9', borderRadius: 6, padding: '0.6rem', fontSize: 14, color: '#2e7d32' }}>{info}</p>}

      {/* Recent points preview */}
      {points.length > 0 && (
        <div>
          <h4 style={{ color: '#7b2d8b', margin: '0.5rem 0 0.3rem' }}>Recent points (last 5):</h4>
          <ul style={{ fontSize: 12, color: '#555', listStyle: 'none', padding: 0 }}>
            {points.slice(-5).map((p, i) => (
              <li key={i}>📍 {p.lat.toFixed(6)}, {p.lon.toFixed(6)} (±{Math.round(p.acc)}m)</li>
            ))}
          </ul>
        </div>
      )}

      {/* Instructions */}
      <details style={{ marginTop: '1rem' }}>
        <summary style={{ cursor: 'pointer', color: '#7b2d8b', fontWeight: 600, fontSize: 14 }}>📖 How to use on your phone</summary>
        <ol style={{ fontSize: 13, color: '#444', paddingLeft: '1.2rem', lineHeight: 1.7 }}>
          <li>Open this page in Chrome on your phone.</li>
          <li>Allow location access when prompted.</li>
          <li>Enter a survey name (e.g. "BH4 to Block 34").</li>
          <li>Tap <strong>Start</strong> and begin walking.</li>
          <li>GPS points record automatically every 2–3 seconds.</li>
          <li>Tap <strong>Stop</strong> when finished.</li>
          <li>Tap <strong>Export GeoJSON</strong> to save the file.</li>
          <li>Draft is auto-saved — a refresh won't erase your data.</li>
        </ol>
      </details>
    </div>
  )
}
