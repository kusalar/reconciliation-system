import React, { useState } from 'react'
import { ingestEvent } from '../api.js'

const SOURCES = ['LMS', 'IOT', 'ATTENDANCE']
const EVENT_TYPES = ['login', 'logout', 'quiz_attempt', 'device_present', 'device_absent', 'attendance_marked']

const PRESETS = [
  {
    label: 'EC-1: Duplicate Login',
    description: 'Send this twice to test deduplication.',
    payload: { source: 'LMS', userId: 'S001', eventType: 'login', timestamp: '2026-08-15T08:00:00+00:00', details: {} },
  },
  {
    label: 'EC-2: Out-of-Order Logout',
    description: 'Logout before login (IoT late arrival).',
    payload: { source: 'IOT', userId: 'S002', eventType: 'logout', timestamp: '2026-08-15T07:00:00+00:00', details: {} },
  },
  {
    label: 'EC-3: IoT Quiz (Conflict)',
    description: 'Same timestamp as LMS quiz — IoT should lose.',
    payload: { source: 'IOT', userId: 'S003', eventType: 'quiz_attempt', timestamp: '2026-08-15T10:30:00+00:00', details: { quiz_id: 'Q10' } },
  },
  {
    label: 'EC-4: Missing User ID',
    description: 'Event with no userId — should be rejected.',
    payload: { source: 'IOT', userId: null, eventType: 'device_present', timestamp: '2026-08-15T08:00:00+00:00', details: {} },
  },
  {
    label: 'EC-5: Conflicting Device Presence',
    description: 'device_present and device_absent at same timestamp.',
    payload: { source: 'IOT', userId: 'S004', eventType: 'device_present', timestamp: '2026-08-15T08:00:00+00:00', details: {} },
  },
  {
    label: 'Normal Login',
    description: 'Standard LMS login event.',
    payload: { source: 'LMS', userId: 'S001', eventType: 'login', timestamp: new Date().toISOString(), details: {} },
  },
]

export default function IngestEvent() {
  const [form, setForm] = useState({
    source: 'LMS',
    userId: '',
    eventType: 'login',
    timestamp: new Date().toISOString(),
    details: '{}',
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [detailsError, setDetailsError] = useState(false)

  function handleChange(k, v) {
    setForm(f => ({ ...f, [k]: v }))
    if (k === 'details') setDetailsError(false)
  }

  function applyPreset(preset) {
    setForm({
      source: preset.payload.source,
      userId: preset.payload.userId ?? '',
      eventType: preset.payload.eventType,
      timestamp: preset.payload.timestamp,
      details: JSON.stringify(preset.payload.details, null, 2),
    })
    setResult(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    let details = {}
    try { details = JSON.parse(form.details || '{}') } catch {
      setDetailsError(true)
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const r = await ingestEvent({
        source: form.source,
        userId: form.userId || null,
        eventType: form.eventType,
        timestamp: form.timestamp,
        details,
      })
      setResult({ ok: true, data: r.data })
    } catch (err) {
      setResult({ ok: false, data: err.response?.data || { error: 'Network error' } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-title">
        <div className="page-title-icon">↗</div>
        <div>
          <h1>Ingest Event</h1>
          <p style={{ marginTop: '0.2rem' }}>Submit a behavioral event to the reconciliation engine</p>
        </div>
      </div>

      {/* Presets */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="card-title">⚡ Quick Presets — Edge Cases</div>
        </div>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.75rem' }}>
            {PRESETS.map((p, i) => (
              <button
                key={i}
                id={`preset-${i}`}
                className="btn btn-outline"
                style={{ flexDirection: 'column', alignItems: 'flex-start', padding: '0.75rem 1rem', height: 'auto', gap: '0.25rem' }}
                onClick={() => applyPreset(p)}
              >
                <span style={{ fontWeight: 600, fontSize: '0.825rem' }}>{p.label}</span>
                <span style={{ fontSize: '0.72rem', color: 'var(--clr-text-faint)', fontWeight: 400 }}>{p.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Form */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📨 Event Payload</div>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="ingest-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="ingest-source">Source</label>
                  <select id="ingest-source" className="form-select" value={form.source} onChange={e => handleChange('source', e.target.value)}>
                    {SOURCES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="ingest-event-type">Event Type</label>
                  <select id="ingest-event-type" className="form-select" value={form.eventType} onChange={e => handleChange('eventType', e.target.value)}>
                    {EVENT_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ingest-user-id">User ID</label>
                <input id="ingest-user-id" className="form-input" placeholder="e.g. S001 (leave blank to test EC-4)" value={form.userId} onChange={e => handleChange('userId', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ingest-timestamp">Timestamp (ISO 8601)</label>
                <input id="ingest-timestamp" className="form-input" value={form.timestamp} onChange={e => handleChange('timestamp', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ingest-details">Details (JSON)</label>
                <textarea
                  id="ingest-details"
                  className={`form-textarea ${detailsError ? 'border-color: var(--clr-danger)' : ''}`}
                  style={detailsError ? { borderColor: 'var(--clr-danger)' } : {}}
                  value={form.details}
                  onChange={e => handleChange('details', e.target.value)}
                />
                {detailsError && <div style={{ color: 'var(--clr-danger)', fontSize: '0.78rem' }}>⚠ Invalid JSON</div>}
              </div>
              <button id="btn-ingest-submit" type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? <><span className="spinner" /> Processing…</> : '↗ Submit Event'}
              </button>
            </form>
          </div>
        </div>

        {/* Result */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📡 Reconciliation Result</div>
          </div>
          <div className="card-body">
            {!result ? (
              <div className="empty-state" style={{ padding: '2rem 1rem' }}>
                <div className="empty-state-icon">⏳</div>
                <p>Submit an event to see the reconciliation decision.</p>
              </div>
            ) : (
              <div>
                <div className={`alert alert-${result.ok ? (result.data.status === 'rejected' ? 'warning' : result.data.status === 'duplicate' ? 'info' : 'success') : 'danger'}`}>
                  {result.ok
                    ? result.data.status === 'rejected' ? '⚠ Event Rejected'
                    : result.data.status === 'duplicate' ? 'ℹ Duplicate Detected'
                    : '✓ Event Accepted'
                    : '✗ Request Failed'}
                </div>
                <div style={{ marginTop: '1rem' }}>
                  {result.data.decision && (
                    <div className="mb-3">
                      <div className="text-xs text-faint mb-1">DECISION</div>
                      <div style={{ fontWeight: 700, color: 'var(--clr-text)', fontSize: '0.9rem' }}>{result.data.decision}</div>
                    </div>
                  )}
                  {result.data.state_version && (
                    <div className="mb-3">
                      <div className="text-xs text-faint mb-1">STATE VERSION</div>
                      <span className="badge badge-neutral">v{result.data.state_version}</span>
                    </div>
                  )}
                  {result.data.reason && (
                    <div className="mb-3">
                      <div className="text-xs text-faint mb-1">REASON</div>
                      <div style={{ color: 'var(--clr-warning)', fontSize: '0.875rem' }}>{result.data.reason}</div>
                    </div>
                  )}
                  <div>
                    <div className="text-xs text-faint mb-1">RAW RESPONSE</div>
                    <pre className="logic-text">{JSON.stringify(result.data, null, 2)}</pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
