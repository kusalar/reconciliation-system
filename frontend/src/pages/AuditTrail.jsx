import React, { useEffect, useState } from 'react'
import { getAllAudit } from '../api.js'

const DECISION_FILTERS = ['ALL', 'ACCEPTED', 'REJECTED', 'IGNORED', 'FLAGGED', 'REPLAY']

function decisionBadge(decision) {
  if (decision.includes('ACCEPTED') || decision.includes('WINS') || decision.includes('RECORDED'))
    return 'badge-success'
  if (decision.includes('REJECTED'))
    return 'badge-danger'
  if (decision.includes('FLAGGED') || decision.includes('out-of-order'))
    return 'badge-warning'
  if (decision.includes('IGNORED') || decision.includes('duplicate'))
    return 'badge-info'
  return 'badge-neutral'
}

export default function AuditTrail() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await getAllAudit()
      setLogs(r.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filtered = logs.filter(a => {
    const matchFilter =
      filter === 'ALL' ? true :
      filter === 'REPLAY' ? a.is_replay :
      a.decision.toUpperCase().includes(filter)
    const matchSearch = search === '' ||
      a.user_id.toLowerCase().includes(search.toLowerCase()) ||
      a.decision.toLowerCase().includes(search.toLowerCase())
    return matchFilter && matchSearch
  })

  return (
    <div>
      <div className="page-title">
        <div className="page-title-icon">📋</div>
        <div>
          <h1>Audit Trail</h1>
          <p style={{ marginTop: '0.2rem' }}>All reconciliation decisions, fully explainable</p>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <button id="btn-refresh-audit" className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-4">
        <div className="card-body" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            id="audit-search"
            className="form-input"
            style={{ maxWidth: 220 }}
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {DECISION_FILTERS.map(f => (
              <button
                key={f}
                id={`audit-filter-${f.toLowerCase()}`}
                className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
          <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--clr-text-faint)' }}>
            {filtered.length} / {logs.length} records
          </span>
        </div>
      </div>

      {loading ? (
        <div className="empty-state"><div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📭</div>
          <p>No audit records match your filter.</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Timestamp</th>
                  <th>Student ID</th>
                  <th>State Ver.</th>
                  <th>Decision</th>
                  <th>Flags</th>
                  <th>Logic</th>
                </tr>
              </thead>
              <tbody>
                {[...filtered].reverse().map((a, i) => (
                  <React.Fragment key={a.id}>
                    <tr style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                      <td className="td-muted">{a.id}</td>
                      <td className="td-mono">{new Date(a.timestamp).toLocaleString()}</td>
                      <td><span style={{ color: 'var(--clr-primary-glow)', fontFamily: 'JetBrains Mono' }}>{a.user_id}</span></td>
                      <td><span className="badge badge-neutral">v{a.state_version}</span></td>
                      <td><span className={`badge ${decisionBadge(a.decision)}`}>{a.decision}</span></td>
                      <td>
                        {a.is_replay && <span className="badge badge-info">replay</span>}
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm btn-icon" title="View logic">
                          {expanded === a.id ? '▲' : '▼'}
                        </button>
                      </td>
                    </tr>
                    {expanded === a.id && (
                      <tr>
                        <td colSpan={7} style={{ background: 'var(--clr-surface-2)', padding: '0.75rem 1rem' }}>
                          <div className="mb-2">
                            <div className="text-xs text-faint mb-1">RESOLUTION LOGIC</div>
                            <div className="logic-text">{a.resolution_logic}</div>
                          </div>
                          {a.input_events?.length > 0 && (
                            <div>
                              <div className="text-xs text-faint mb-1">INPUT EVENTS</div>
                              <pre className="logic-text">{JSON.stringify(a.input_events, null, 2)}</pre>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
