import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Shield, ArrowLeft, Lock, User, AlertCircle } from 'lucide-react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('username', username)
      form.append('password', password)
      const res = await fetch(`${BACKEND}/api/admin/token`, {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        setError('Invalid administrator username or password.')
        setLoading(false)
        return
      }
      const data = await res.json()
      sessionStorage.setItem('lpu_token', data.access_token)
      window.location.href = '/admin/survey'
    } catch {
      setError('Cannot reach the backend server. Please verify network connection.')
    }
    setLoading(false)
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      backgroundColor: '#FAF8F5',
      padding: '1.5rem',
      fontFamily: 'var(--font-main, sans-serif)'
    }}>
      <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
        <Link to="/" style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          color: '#6B7280',
          fontSize: '0.88rem',
          fontWeight: 600,
          textDecoration: 'none',
          marginBottom: '1rem'
        }}>
          <ArrowLeft size={16} />
          Back to Campus Navigation
        </Link>
      </div>

      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: 20,
        padding: '2.25rem 2rem',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.08)',
        width: '100%',
        maxWidth: 400,
        border: '1px solid #E5E7EB'
      }} className="animate-fade-in">
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div style={{
            width: 52,
            height: 52,
            borderRadius: 14,
            backgroundColor: '#FFF2E8',
            color: '#E66A27',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '0.75rem',
            boxShadow: '0 4px 12px rgba(230, 106, 39, 0.2)'
          }}>
            <Shield size={28} />
          </div>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#20252D', marginBottom: 4 }}>
            LPU Administrator Login
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#6B7280' }}>
            Authorized campus surveyors and administrators only.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', fontWeight: 700, color: '#374151' }}>
              Username
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <User size={18} color="#9CA3AF" style={{ position: 'absolute', left: 12 }} />
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoComplete="username"
                placeholder="Admin username"
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem 0.75rem 2.4rem',
                  borderRadius: 10,
                  border: '1px solid #D1D5DB',
                  fontSize: '0.95rem',
                  backgroundColor: '#F9FAFB'
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', fontWeight: 700, color: '#374151' }}>
              Password
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <Lock size={18} color="#9CA3AF" style={{ position: 'absolute', left: 12 }} />
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem 0.75rem 2.4rem',
                  borderRadius: 10,
                  border: '1px solid #D1D5DB',
                  fontSize: '0.95rem',
                  backgroundColor: '#F9FAFB'
                }}
              />
            </div>
          </div>

          {error && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '0.7rem 0.9rem',
              borderRadius: 10,
              backgroundColor: '#FEE2E2',
              color: '#991B1B',
              fontSize: '0.85rem',
              fontWeight: 500
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              backgroundColor: '#E66A27',
              color: '#FFFFFF',
              padding: '0.85rem',
              borderRadius: 10,
              fontSize: '1rem',
              fontWeight: 700,
              boxShadow: '0 4px 12px rgba(230, 106, 39, 0.3)',
              marginTop: '0.5rem'
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Portal'}
          </button>
        </form>
      </div>
    </div>
  )
}
