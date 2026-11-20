import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Compass, Map, Home, Shield, Menu, X } from 'lucide-react'

export const Navbar: React.FC = () => {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isAdmin = Boolean(sessionStorage.getItem('lpu_token'))

  const isActive = (path: string) => location.pathname === path

  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 1000,
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      backdropFilter: 'blur(10px)',
      borderBottom: '1px solid #E5E7EB',
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
      width: '100%'
    }}>
      <div style={{
        maxWidth: 1200,
        margin: '0 auto',
        padding: '0.75rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        {/* Brand */}
        <Link to="/" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          textDecoration: 'none',
          color: '#20252D'
        }}>
          <div style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            backgroundColor: '#E66A27',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: '0 4px 10px rgba(230, 106, 39, 0.3)'
          }}>
            <Compass size={24} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{
              fontSize: '1.2rem',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <span>LPU Wayfinder</span>
              <span style={{
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                backgroundColor: '#FFF2E8',
                color: '#E66A27',
                padding: '2px 7px',
                borderRadius: 999,
                letterSpacing: '0.04em'
              }}>
                Campus
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: -2 }}>
              Lovely Professional University
            </div>
          </div>
        </Link>

        {/* Desktop Navigation */}
        <nav style={{
          display: 'none',
          alignItems: 'center',
          gap: '1.5rem',
        }} className="desktop-nav">
          <Link
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              textDecoration: 'none',
              fontSize: '0.92rem',
              fontWeight: 600,
              color: isActive('/') ? '#E66A27' : '#4B5563',
              padding: '0.4rem 0.8rem',
              borderRadius: 8,
              backgroundColor: isActive('/') ? '#FFF2E8' : 'transparent',
              transition: 'all 0.15s ease'
            }}
          >
            <Home size={18} />
            Home
          </Link>

          <Link
            to="/map"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              textDecoration: 'none',
              fontSize: '0.92rem',
              fontWeight: 600,
              color: isActive('/map') ? '#E66A27' : '#4B5563',
              padding: '0.4rem 0.8rem',
              borderRadius: 8,
              backgroundColor: isActive('/map') ? '#FFF2E8' : 'transparent',
              transition: 'all 0.15s ease'
            }}
          >
            <Map size={18} />
            Campus Map
          </Link>

          <div style={{ width: 1, height: 20, backgroundColor: '#E5E7EB', margin: '0 0.25rem' }} />

          {/* Small unobtrusive Admin link */}
          <Link
            to={isAdmin ? '/admin/survey' : '/admin/login'}
            title="Administrator Portal"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              textDecoration: 'none',
              fontSize: '0.78rem',
              fontWeight: 600,
              color: '#9CA3AF',
              padding: '0.35rem 0.7rem',
              borderRadius: 6,
              border: '1px solid #E5E7EB',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = '#E66A27'
              e.currentTarget.style.borderColor = '#E66A27'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = '#9CA3AF'
              e.currentTarget.style.borderColor = '#E5E7EB'
            }}
          >
            <Shield size={14} />
            Admin
          </Link>
        </nav>

        {/* Mobile Hamburger Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 40,
            height: 40,
            borderRadius: 8,
            backgroundColor: '#F3F4F6',
            color: '#20252D'
          }}
          className="mobile-menu-btn"
        >
          {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div style={{
          backgroundColor: '#FFFFFF',
          borderTop: '1px solid #E5E7EB',
          padding: '1rem 1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem'
        }} className="animate-fade-in">
          <Link
            to="/"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              textDecoration: 'none',
              padding: '0.75rem',
              borderRadius: 10,
              fontWeight: 600,
              fontSize: '1rem',
              color: isActive('/') ? '#E66A27' : '#20252D',
              backgroundColor: isActive('/') ? '#FFF2E8' : '#F9FAFB'
            }}
          >
            <Home size={20} color={isActive('/') ? '#E66A27' : '#6B7280'} />
            Home
          </Link>

          <Link
            to="/map"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              textDecoration: 'none',
              padding: '0.75rem',
              borderRadius: 10,
              fontWeight: 600,
              fontSize: '1rem',
              color: isActive('/map') ? '#E66A27' : '#20252D',
              backgroundColor: isActive('/map') ? '#FFF2E8' : '#F9FAFB'
            }}
          >
            <Map size={20} color={isActive('/map') ? '#E66A27' : '#6B7280'} />
            Campus Map
          </Link>

          <div style={{ height: 1, backgroundColor: '#E5E7EB', margin: '0.25rem 0' }} />

          <Link
            to={isAdmin ? '/admin/survey' : '/admin/login'}
            onClick={() => setMobileMenuOpen(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              textDecoration: 'none',
              padding: '0.6rem 0.75rem',
              borderRadius: 8,
              fontSize: '0.85rem',
              fontWeight: 500,
              color: '#6B7280',
              backgroundColor: '#F9FAFB'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={16} />
              <span>Admin Portal {isAdmin && '(Signed In)'}</span>
            </div>
            <span style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Staff only</span>
          </Link>
        </div>
      )}

      <style>{`
        @media (min-width: 641px) {
          .desktop-nav {
            display: flex !important;
          }
          .mobile-menu-btn {
            display: none !important;
          }
        }
      `}</style>
    </header>
  )
}
