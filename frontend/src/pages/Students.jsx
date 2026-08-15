import React, { useEffect, useState } from 'react'
import { getAllStudents } from '../api.js'

export default function Students({ onSelectStudent }) {
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await getAllStudents()
      setStudents(r.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filtered = students.filter(s =>
    s.user_id.toLowerCase().includes(search.toLowerCase())
  )

  const riskColor = {
    HIGH: 'var(--clr-danger)',
    MEDIUM: 'var(--clr-warning)',
    LOW: 'var(--clr-success)',
  }

  return (
    <div>
      <div className="page-title">
        <div className="page-title-icon">🎓</div>
        <div>
          <h1>Students</h1>
          <p style={{ marginTop: '0.2rem' }}>Reconciled behavioral profiles</p>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <button id="btn-refresh-students" className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      <div className="mb-4">
        <input
          id="search-students"
          className="form-input"
          style={{ maxWidth: 320 }}
          placeholder="Search by Student ID…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="empty-state"><div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📭</div>
          <p>{search ? 'No students match your search.' : 'No students yet. Ingest events first.'}</p>
        </div>
      ) : (
        <div className="student-grid">
          {filtered.map(s => {
            const risk = s.risk || {}
            const level = risk.risk_level || 'UNKNOWN'
            const score = risk.score ?? '—'
            const clr = riskColor[level] || 'var(--clr-text-muted)'
            return (
              <div
                key={s.user_id}
                className="student-card"
                id={`student-card-${s.user_id}`}
                onClick={() => onSelectStudent(s.user_id)}
              >
                <div className="student-id"># {s.user_id}</div>
                <div className="student-name">Student {s.user_id}</div>

                <div className="student-signals">
                  <span className={`signal-pill ${s.state.is_logged_in ? 'on' : 'off'}`}>
                    {s.state.is_logged_in ? '● LMS Online' : '○ LMS Offline'}
                  </span>
                  <span className={`signal-pill ${s.state.is_device_present ? 'on' : 'off'}`}>
                    {s.state.is_device_present ? '📡 Device Present' : '— Device Absent'}
                  </span>
                  <span className="signal-pill">
                    📝 {s.state.quiz_attempts} Quiz{s.state.quiz_attempts !== 1 ? 'es' : ''}
                  </span>
                  <span className="signal-pill badge-neutral">
                    v{s.state_version}
                  </span>
                </div>

                <div className="risk-bar-container">
                  <div className="risk-bar-track">
                    <div
                      className={`risk-bar-fill ${level.toLowerCase()}`}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <span className="risk-score-badge" style={{ color: clr }}>{score}</span>
                  <span className={`badge ${level === 'HIGH' ? 'badge-danger' : level === 'MEDIUM' ? 'badge-warning' : 'badge-success'}`}>{level}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
