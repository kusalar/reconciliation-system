import React, { useEffect, useState } from 'react'
import { getAllStudents, getAllAudit, replayEvents } from '../api.js'

function StatCard({ label, value, sub, accentColor }) {
  return (
    <div className="stat-card" style={{ '--accent-gradient': `linear-gradient(90deg, ${accentColor}, transparent)` }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function RiskBadge({ level, score }) {
  const cls = { HIGH: 'badge-danger', MEDIUM: 'badge-warning', LOW: 'badge-success' }[level] || 'badge-neutral'
  return <span className={`badge ${cls}`}>{level} ({score})</span>
}

export default function Dashboard({ onSelectStudent }) {
  const [students, setStudents] = useState([])
  const [audits, setAudits] = useState([])
  const [loading, setLoading] = useState(true)
  const [replayMsg, setReplayMsg] = useState(null)
  const [replaying, setReplaying] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [sRes, aRes] = await Promise.all([getAllStudents(), getAllAudit()])
      setStudents(sRes.data)
      setAudits(aRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleReplayAll() {
    setReplaying(true)
    setReplayMsg(null)
    try {
      const r = await replayEvents(null)
      setReplayMsg({ type: 'success', text: `✓ Replayed ${r.data.replayed} events across all students.` })
      await load()
    } catch {
      setReplayMsg({ type: 'danger', text: '✗ Replay failed.' })
    } finally {
      setReplaying(false)
    }
  }

  const high = students.filter(s => s.risk?.risk_level === 'HIGH').length
  const medium = students.filter(s => s.risk?.risk_level === 'MEDIUM').length
  const low = students.filter(s => s.risk?.risk_level === 'LOW').length
  const recentAudits = [...audits].reverse().slice(0, 8)

  return (
    <div>
      <div className="page-title">
        <div className="page-title-icon">⬡</div>
        <div>
          <h1>Reconciliation Dashboard</h1>
          <p style={{ marginTop: '0.2rem' }}>Real-time student behavior intelligence</p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.75rem' }}>
          <button id="btn-refresh-dashboard" className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
          <button id="btn-replay-all" className="btn btn-outline btn-sm btn-danger" onClick={handleReplayAll} disabled={replaying}>
            {replaying ? <span className="spinner" /> : '⟳'} Replay All
          </button>
        </div>
      </div>

      {replayMsg && <div className={`alert alert-${replayMsg.type}`}>{replayMsg.text}</div>}

      {loading ? (
        <div className="empty-state"><div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} /></div>
      ) : (
        <>
          {/* Stats */}
          <div className="stats-grid">
            <StatCard label="Total Students" value={students.length} sub="Tracked in system" accentColor="var(--clr-primary)" />
            <StatCard label="High Risk" value={high} sub="Immediate attention" accentColor="var(--clr-danger)" />
            <StatCard label="Medium Risk" value={medium} sub="Monitor closely" accentColor="var(--clr-warning)" />
            <StatCard label="Low Risk" value={low} sub="Healthy engagement" accentColor="var(--clr-success)" />
            <StatCard label="Audit Records" value={audits.length} sub="Decision log entries" accentColor="var(--clr-info)" />
          </div>

          {/* Risk Overview Table */}
          <div className="card mb-6">
            <div className="card-header">
              <div className="card-title">🎓 Student Risk Overview</div>
            </div>
            <div className="table-wrapper">
              {students.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <p>No students yet. Ingest some events to get started.</p>
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Student ID</th>
                      <th>State Version</th>
                      <th>Login Status</th>
                      <th>Device</th>
                      <th>Quiz Attempts</th>
                      <th>Risk Score</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map(s => (
                      <tr key={s.user_id} onClick={() => onSelectStudent(s.user_id)} style={{ cursor: 'pointer' }}>
                        <td><span className="font-mono" style={{ color: 'var(--clr-primary-glow)' }}>{s.user_id}</span></td>
                        <td><span className="badge badge-neutral">v{s.state_version}</span></td>
                        <td>
                          <span className={`badge ${s.state.is_logged_in ? 'badge-success' : 'badge-neutral'}`}>
                            {s.state.is_logged_in ? '● Online' : '○ Offline'}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${s.state.is_device_present ? 'badge-info' : 'badge-neutral'}`}>
                            {s.state.is_device_present ? '📡 Present' : '— Absent'}
                          </span>
                        </td>
                        <td>{s.state.quiz_attempts}</td>
                        <td><RiskBadge level={s.risk?.risk_level} score={s.risk?.score} /></td>
                        <td><button className="btn btn-outline btn-sm" onClick={e => { e.stopPropagation(); onSelectStudent(s.user_id) }}>View →</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Recent Audit Activity */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">📋 Recent Reconciliation Decisions</div>
            </div>
            <div className="card-body">
              {recentAudits.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <p>No audit records yet.</p>
                </div>
              ) : (
                <div className="timeline">
                  {recentAudits.map((a, i) => {
                    const isGood = a.decision.includes('ACCEPTED') || a.decision.includes('WINS')
                    const isBad  = a.decision.includes('REJECTED') || a.decision.includes('FLAGGED')
                    const isDup  = a.decision.includes('duplicate') || a.decision.includes('IGNORED')
                    const dotClass = isGood ? 'success' : isBad ? 'danger' : isDup ? 'warning' : 'info'
                    return (
                      <div className="timeline-item" key={i}>
                        <div className={`timeline-dot ${dotClass}`} />
                        <div className="timeline-time">{new Date(a.timestamp).toLocaleString()}</div>
                        <div className="timeline-decision">{a.decision}</div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                          <span className="badge badge-primary">{a.user_id}</span>
                          <span className="badge badge-neutral">v{a.state_version}</span>
                          {a.is_replay && <span className="badge badge-info">replay</span>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
