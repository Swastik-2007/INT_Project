import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import { HomePage } from './HomePage'
import { MapPage } from './MapPage'
import Login from './Login'
import Survey from './Survey'
import VerificationPage from './VerificationPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/admin/login" element={<Login />} />
        <Route path="/admin/survey" element={<Survey />} />
        <Route path="/admin/verify" element={<VerificationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
