import React, { useEffect, useState } from 'react'
import { getStudentState, getStudentTimeline, getStudentAudit, getStudentRisk, replayEvents } from '../api.js'

function RiskCircle({ score, level }) {
  const color = level === 'HIGH' ? '#ef4444' : level === 'MEDIUM' ? '#f59e0b' : '#10b981'
  const r = 48
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--clr-surface-2)" strokeWidth="8" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 60 60)"
          style={{ filter: `drop-shadow(0 0 8px ${color})`, transition: 'stroke-dashoffset 0.6s ease' }}
        />
        <text x="60" y="56" textAnchor="middle" fill={color} fontSize="22" fontWeight="800" fontFamily="Inter">{score}</text>
        <text x="60" y="72" textAnchor="middle" fill="var(--clr-text-faint)" fontSize="10" fontFamily="Inter" textTransform="uppercase">{level}</text>
      </svg>
      <div style={{ fontSize: '0.75rem', color: 'var(--clr-text-faint)' }}>Dropout Risk Score</div>
    </div>
  )
}

function dotClass(decision) {
  if (decision.includes('ACCEPTED') || decision.includes('WINS')) return 'success'
  if (decision.includes('REJECTED')) return 'danger'
  if (decision.includes('FLAGGED') || decision.includes('out-of-order')) return 'warning'
  if (decision.includes('IGNORED') || decision.includes('duplicate')) return 'info'
  return ''
}

export default function StudentDetail({ userId, onBack }) {
  const [state, setState] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [audit, setAudit] = useState([])
  const [risk, setRisk] = useState(null)
  const [loading, setLoading] = useState(true)
  const [replaying, setReplaying] = useState(false)
  const [replayMsg, setReplayMsg] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const [sRes, tRes, aRes, rRes] = await Promise.all([
        getStudentState(userId),
        getStudentTimeline(userId),
        getStudentAudit(userId),
        getStudentRisk(userId),
      ])
      setState(sRes.data)
      setTimeline(tRes.data)
      setAudit(aRes.data)
      setRisk(rRes.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { if (userId) load() }, [userId])

  async function handleReplay() {
    setReplaying(true)
    setReplayMsg(null)
    try {
      const r = await replayEvents(userId)
      setReplayMsg({ type: 'success', text: `✓ Replayed ${r.data.replayed} events for ${userId}.` })
      await load()
    } catch {
      setReplayMsg({ type: 'danger', text: '✗ Replay failed.' })
    } finally { setReplaying(false) }
  }

  if (loading) return (
    <div className="empty-state" style={{ marginTop: '4rem' }}>
      <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
    </div>
  )
  if (!state) return <div className="empty-state"><p>Student not found.</p></div>

  const currentTimeline = state?.timeline || []

  return (
    <div>
      <div className="page-title">
        <button id="btn-back-students" className="btn btn-outline btn-sm btn-icon" onClick={onBack}>←</button>
        <div className="page-title-icon">🎓</div>
        <div>
          <h1 style={{ fontFamily: 'JetBrains Mono' }}>{userId}</h1>
          <p style={{ marginTop: '0.2rem' }}>Student Detail — State v{state?.version}</p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
          <button id="btn-refresh-detail" className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
          <button id="btn-replay-student" className="btn btn-outline btn-sm btn-danger" onClick={handleReplay} disabled={replaying}>
            {replaying ? <span className="spinner" /> : '⟳'} Replay
          </button>
        </div>
      </div>

      {replayMsg && <div className={`alert alert-${replayMsg.type}`}>{replayMsg.text}</div>}

      {/* Top Row: State + Risk */}
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '1.25rem', marginBottom: '1.25rem' }}>
        {/* Risk Circle */}
        <div className="card">
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
            <RiskCircle score={risk?.score ?? 0} level={risk?.risk_level ?? 'N/A'} />
            {risk?.factors && (
              <div style={{ width: '100%', minWidth: 240 }}>
                {risk.factors.map((f, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.35rem 0', borderBottom: '1px solid var(--clr-border-soft)', fontSize: '0.78rem' }}>
                    <span style={{ color: 'var(--clr-text-muted)' }}>{f.factor}</span>
                    <span style={{ fontWeight: 700, color: f.delta > 0 ? 'var(--clr-danger)' : 'var(--clr-success)', fontFamily: 'JetBrains Mono', minWidth: '2.5rem', textAlign: 'right' }}>
                      {f.delta > 0 ? '+' : ''}{f.delta}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Current State */}
        <div className="card">
          <div className="card-header"><div className="card-title">⚡ Current Reconciled State</div></div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              {[
                { label: 'Login Status', value: state.is_logged_in ? '● Online' : '○ Offline', cls: state.is_logged_in ? 'badge-success' : 'badge-neutral' },
                { label: 'Device', value: state.is_device_present ? '📡 Present' : '— Absent', cls: state.is_device_present ? 'badge-info' : 'badge-neutral' },
                { label: 'Quiz Attempts', value: state.quiz_attempts, cls: 'badge-neutral' },
                { label: 'State Version', value: `v${state.version}`, cls: 'badge-primary' },
              ].map(f => (
                <div key={f.label} style={{ padding: '0.875rem', background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--clr-border-soft)' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--clr-text-faint)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.4rem' }}>{f.label}</div>
                  <span className={`badge ${f.cls}`} style={{ fontSize: '0.82rem' }}>{f.value}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '1rem' }}>
              {[
                ['Last Login', state.last_login],
                ['Last Logout', state.last_logout],
                ['Last Quiz', state.last_quiz_attempt],
                ['Last Device Present', state.last_device_present],
              ].map(([label, val]) => val ? (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', borderBottom: '1px solid var(--clr-border-soft)', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--clr-text-faint)' }}>{label}</span>
                  <span className="font-mono" style={{ color: 'var(--clr-text-muted)', fontSize: '0.75rem' }}>{new Date(val).toLocaleString()}</span>
                </div>
              ) : null)}
            </div>
          </div>
        </div>
      </div>

      {/* Timeline + Audit */}
      <div className="detail-panel">
        {/* Reconciled Timeline */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">🕐 Reconciled Event Timeline</div>
            <span className="badge badge-neutral">{currentTimeline.length} events</span>
          </div>
          <div className="card-body">
            {currentTimeline.length === 0 ? (
              <div className="empty-state" style={{ padding: '1.5rem' }}>
                <p>No events in timeline yet.</p>
              </div>
            ) : (
              <div className="timeline">
                {currentTimeline.map((ev, i) => (
                  <div className="timeline-item" key={i}>
                    <div className={`timeline-dot ${dotClass(ev.decision)}`} />
                    <div className="timeline-time">{new Date(ev.timestamp).toLocaleString()}</div>
                    <div className="timeline-decision">{ev.event_type?.replace('_', ' ').toUpperCase()}</div>
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
                      <span className={`badge ${ev.source === 'LMS' ? 'badge-primary' : ev.source === 'IOT' ? 'badge-info' : 'badge-neutral'}`}>{ev.source}</span>
                      <span className={`badge ${ev.decision.includes('ACCEPTED') || ev.decision.includes('WINS') ? 'badge-success' : ev.decision.includes('IGNORED') ? 'badge-warning' : 'badge-danger'}`} style={{ fontSize: '0.65rem' }}>
                        {ev.decision}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Audit Log */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📋 Audit Log</div>
            <span className="badge badge-neutral">{audit.length} entries</span>
          </div>
          <div className="card-body" style={{ maxHeight: '500px', overflowY: 'auto' }}>
            {audit.length === 0 ? (
              <div className="empty-state" style={{ padding: '1.5rem' }}><p>No audit records.</p></div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {[...audit].reverse().map((a, i) => (
                  <div key={i} style={{ background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--clr-border-soft)', padding: '0.75rem 1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.3rem' }}>
                      <span className={`badge ${a.decision.includes('ACCEPTED') || a.decision.includes('WINS') ? 'badge-success' : a.decision.includes('REJECTED') ? 'badge-danger' : a.decision.includes('IGNORED') ? 'badge-info' : 'badge-warning'}`}>
                        {a.decision}
                      </span>
                      <div style={{ display: 'flex', gap: '0.3rem' }}>
                        <span className="badge badge-neutral">v{a.state_version}</span>
                        {a.is_replay && <span className="badge badge-info">replay</span>}
                      </div>
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--clr-text-faint)', marginBottom: '0.4rem' }}>
                      {new Date(a.timestamp).toLocaleString()}
                    </div>
                    <div className="logic-text">{a.resolution_logic}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
