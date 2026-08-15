import React, { useState, useEffect, useCallback } from 'react'
import Dashboard from './pages/Dashboard.jsx'
import Students from './pages/Students.jsx'
import IngestEvent from './pages/IngestEvent.jsx'
import AuditTrail from './pages/AuditTrail.jsx'
import StudentDetail from './pages/StudentDetail.jsx'

const NAV = [
  { id: 'dashboard',  icon: '⬡', label: 'Dashboard',      section: 'Monitor' },
  { id: 'students',   icon: '🎓', label: 'Students',       section: 'Monitor' },
  { id: 'ingest',     icon: '↗', label: 'Ingest Event',   section: 'Control' },
  { id: 'audit',      icon: '📋', label: 'Audit Trail',    section: 'Control' },
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [apiOnline, setApiOnline] = useState(false)

  const checkApi = useCallback(async () => {
    try {
      const r = await fetch('/api/students/')
      setApiOnline(r.ok)
    } catch { setApiOnline(false) }
  }, [])

  useEffect(() => {
    checkApi()
    const id = setInterval(checkApi, 5000)
    return () => clearInterval(id)
  }, [checkApi])

  function openStudent(uid) {
    setSelectedStudent(uid)
    setPage('student-detail')
  }

  function renderPage() {
    switch (page) {
      case 'dashboard':      return <Dashboard onSelectStudent={openStudent} />
      case 'students':       return <Students onSelectStudent={openStudent} />
      case 'ingest':         return <IngestEvent />
      case 'audit':          return <AuditTrail />
      case 'student-detail': return <StudentDetail userId={selectedStudent} onBack={() => setPage('students')} />
      default:               return <Dashboard onSelectStudent={openStudent} />
    }
  }

  const sections = [...new Set(NAV.map(n => n.section))]

  return (
    <div className="app-layout">
      {/* Ambient glow */}
      <div className="glow-hero" />

      {/* Header */}
      <header className="app-header">
        <div className="app-logo">
          <div className="app-logo-icon">⚡</div>
          <div className="app-logo-text">
            <strong>Vidhya Rakshak</strong>
            <span>Real-Time Reconciliation Engine</span>
          </div>
        </div>
        <div className="header-status">
          <div className={`status-dot`} style={{ background: apiOnline ? 'var(--clr-success)' : 'var(--clr-danger)', boxShadow: `0 0 8px ${apiOnline ? 'var(--clr-success)' : 'var(--clr-danger)'}` }} />
          <span>{apiOnline ? 'API Connected' : 'API Offline'}</span>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="app-sidebar">
        {sections.map(section => (
          <React.Fragment key={section}>
            <div className="nav-section-label">{section}</div>
            {NAV.filter(n => n.section === section).map(item => (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item ${page === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                <span className="nav-item-icon">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </React.Fragment>
        ))}

        <div style={{ marginTop: 'auto', padding: '1rem 0.75rem', borderTop: '1px solid var(--clr-border-soft)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--clr-text-faint)', lineHeight: 1.6 }}>
            <div style={{ fontWeight: 600, marginBottom: '0.2rem', color: 'var(--clr-text-muted)' }}>Smart India Hackathon</div>
            <div>Vidhya Rakshak v2.0</div>
            <div>Dropout Prediction Engine</div>
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="app-main content-z">
        {renderPage()}
      </main>
    </div>
  )
}
