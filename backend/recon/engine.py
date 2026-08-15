"""
Reconciliation Engine for Vidhya Rakshak.

This module implements DETERMINISTIC conflict resolution logic for
student behavioral events arriving from multiple asynchronous sources.

Design Principles:
  - Idempotent: replaying the same events never changes the final state.
  - Deterministic: same input → same output, always.
  - Auditable: every decision is logged with its rationale.
  - No ML/LLM: pure rule-based logic.

Edge Cases Handled:
  1. Duplicate events (same source/userId/eventType/timestamp) → ignored.
  2. Out-of-order events (timestamp earlier than current state) → applied
     retroactively but only if they are the authoritative state.
  3. Conflicting quiz attempt timestamps from LMS vs IoT → LMS wins.
  4. Missing userId → event rejected with audit record.
  5. Conflicting device_present/device_absent with same timestamp → 
     device_present wins (assume presence is safer assumption).
"""
import hashlib
import json
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import RawEvent, StudentState, AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fingerprint(source: str, user_id: str, event_type: str, timestamp: str) -> str:
    """SHA-256 fingerprint for deduplication."""
    key = f"{source}|{user_id or ''}|{event_type}|{timestamp}"
    return hashlib.sha256(key.encode()).hexdigest()


def _serialize_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_iso(ts: str) -> datetime:
    """Parse ISO-8601 to timezone-aware datetime."""
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f"Invalid ISO-8601 timestamp: {ts!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt


def _get_or_init_state(user_id: str) -> StudentState:
    """Return the latest StudentState for user_id, or a transient new one."""
    qs = StudentState.objects.filter(user_id=user_id).order_by('-version')
    if qs.exists():
        return qs.first()
    # Return an unsaved sentinel with version=0
    return StudentState(user_id=user_id, version=0, timeline=[], triggered_by_events=[])


def _bump_version(prev: StudentState) -> StudentState:
    """Create and return a new unsaved StudentState as the next version."""
    import copy as _copy
    new = StudentState(
        user_id=prev.user_id,
        version=prev.version + 1,
        is_logged_in=prev.is_logged_in,
        last_login=prev.last_login,
        last_logout=prev.last_logout,
        is_device_present=prev.is_device_present,
        last_device_present=prev.last_device_present,
        last_device_absent=prev.last_device_absent,
        quiz_attempts=prev.quiz_attempts,
        last_quiz_attempt=prev.last_quiz_attempt,
        timeline=list(prev.timeline),
        triggered_by_events=list(prev.triggered_by_events),
    )
    return new


def _write_audit(
    user_id: str,
    version: int,
    decision: str,
    logic: str,
    input_events: list,
    is_replay: bool = False,
):
    AuditLog.objects.create(
        user_id=user_id,
        state_version=version,
        decision=decision,
        resolution_logic=logic,
        input_events=input_events,
        is_replay=is_replay,
    )


# ---------------------------------------------------------------------------
# Core Reconciliation Logic
# ---------------------------------------------------------------------------

class ReconciliationEngine:
    """
    Stateless engine: receives a validated payload dict and updates DB state.
    All DB operations are wrapped in a transaction.
    """

    # Source priority for conflict resolution (higher = more authoritative)
    SOURCE_PRIORITY = {'LMS': 2, 'IOT': 1, 'ATTENDANCE': 1}

    @transaction.atomic
    def ingest(self, payload: dict, is_replay: bool = False) -> dict:
        """
        Main entry point. Returns a dict with status and any audit info.
        """
        # ── Edge Case 4: Missing userId ──────────────────────────────────
        user_id = payload.get('userId') or payload.get('user_id')
        if not user_id or str(user_id).strip() == '':
            _write_audit(
                user_id='UNKNOWN',
                version=0,
                decision='REJECTED: missing userId',
                logic='Rule: Every event must carry a non-empty userId. '
                      'Event discarded to prevent state corruption.',
                input_events=[payload],
                is_replay=is_replay,
            )
            return {'status': 'rejected', 'reason': 'missing userId'}

        user_id = str(user_id).strip()
        source = str(payload.get('source', '')).upper()
        event_type = str(payload.get('eventType', payload.get('event_type', ''))).lower()
        timestamp_raw = payload.get('timestamp', '')
        details = payload.get('details', {}) or {}

        # Validate source
        if source not in self.SOURCE_PRIORITY:
            return {'status': 'rejected', 'reason': f'unknown source: {source}'}

        # Validate event type
        valid_types = {'login', 'logout', 'quiz_attempt', 'device_present', 'device_absent', 'attendance_marked'}
        if event_type not in valid_types:
            return {'status': 'rejected', 'reason': f'unknown eventType: {event_type}'}

        # Parse timestamp
        try:
            event_ts = _parse_iso(timestamp_raw)
        except ValueError as e:
            return {'status': 'rejected', 'reason': str(e)}

        # ── Edge Case 1: Duplicate Detection ────────────────────────────
        fingerprint = _make_fingerprint(source, user_id, event_type, timestamp_raw)
        if RawEvent.objects.filter(fingerprint=fingerprint).exists():
            _write_audit(
                user_id=user_id,
                version=self._current_version(user_id),
                decision='IGNORED: duplicate event',
                logic=f'Rule: Fingerprint {fingerprint[:12]}… already exists. '
                       'Idempotency enforced — duplicate dropped.',
                input_events=[payload],
                is_replay=is_replay,
            )
            return {'status': 'duplicate', 'fingerprint': fingerprint}

        # Persist raw event
        raw = RawEvent.objects.create(
            source=source,
            user_id=user_id,
            event_type=event_type,
            event_timestamp=event_ts,
            details=details,
            raw_payload=payload,
            fingerprint=fingerprint,
        )

        # Load current state
        prev_state = _get_or_init_state(user_id)
        new_state = _bump_version(prev_state)

        # ── Dispatch to handler ──────────────────────────────────────────
        result = self._dispatch(event_type, source, event_ts, details, new_state, raw, is_replay)

        # Append to timeline
        new_state.timeline.append({
            'source': source,
            'event_type': event_type,
            'timestamp': event_ts.isoformat(),
            'decision': result['decision'],
            'fingerprint': fingerprint,
        })
        new_state.triggered_by_events.append(fingerprint)
        new_state.save()

        _write_audit(
            user_id=user_id,
            version=new_state.version,
            decision=result['decision'],
            logic=result['logic'],
            input_events=[payload],
            is_replay=is_replay,
        )

        return {
            'status': 'accepted',
            'decision': result['decision'],
            'state_version': new_state.version,
            'fingerprint': fingerprint,
        }

    def _current_version(self, user_id: str) -> int:
        qs = StudentState.objects.filter(user_id=user_id).order_by('-version')
        return qs.first().version if qs.exists() else 0

    def _dispatch(self, event_type, source, event_ts, details, state, raw, is_replay):
        handlers = {
            'login': self._handle_login,
            'logout': self._handle_logout,
            'quiz_attempt': self._handle_quiz,
            'device_present': self._handle_device_present,
            'device_absent': self._handle_device_absent,
            'attendance_marked': self._handle_attendance,
        }
        handler = handlers.get(event_type, self._handle_unknown)
        return handler(source, event_ts, details, state, raw, is_replay)

    # ── Login ──────────────────────────────────────────────────────────
    def _handle_login(self, source, event_ts, details, state, raw, is_replay):
        """
        Rule: Accept login. If a previous login exists without a logout,
        still accept — last-write-wins on login (most recent state wins).
        Out-of-order: if event_ts < last_logout, ignore (stale event).
        """
        # ── Edge Case 2: Out-of-order ────────────────────────────────
        if state.last_logout and event_ts < state.last_logout:
            return {
                'decision': 'LOGIN_IGNORED: out-of-order (before last logout)',
                'logic': (
                    f'Rule (OOO): event_ts={event_ts.isoformat()} < '
                    f'last_logout={state.last_logout.isoformat()}. '
                    'Stale login ignored to preserve temporal consistency.'
                ),
            }

        if state.last_login and event_ts <= state.last_login:
            return {
                'decision': 'LOGIN_IGNORED: not newer than existing login',
                'logic': (
                    f'Rule: event_ts={event_ts.isoformat()} ≤ '
                    f'last_login={state.last_login.isoformat()}. Ignored.'
                ),
            }

        state.is_logged_in = True
        state.last_login = event_ts
        return {
            'decision': 'LOGIN_ACCEPTED',
            'logic': (
                f'Rule: Login from {source} at {event_ts.isoformat()} accepted. '
                'Student marked as logged in.'
            ),
        }

    # ── Logout ─────────────────────────────────────────────────────────
    def _handle_logout(self, source, event_ts, details, state, raw, is_replay):
        """
        Rule: Accept logout if it is newer than last login (or if no login
        recorded, accept anyway — last-write-wins). Out-of-order handled.
        """
        # ── Edge Case 2: Out-of-order logout ─────────────────────────
        if state.last_login and event_ts < state.last_login:
            return {
                'decision': 'LOGOUT_FLAGGED: out-of-order (before last login)',
                'logic': (
                    f'Rule (OOO): logout event_ts={event_ts.isoformat()} < '
                    f'last_login={state.last_login.isoformat()}. '
                    'Logout flagged as out-of-order; state unchanged to '
                    'preserve temporal integrity.'
                ),
            }

        state.is_logged_in = False
        state.last_logout = event_ts
        return {
            'decision': 'LOGOUT_ACCEPTED',
            'logic': (
                f'Rule: Logout from {source} at {event_ts.isoformat()} accepted. '
                'Student marked as logged out.'
            ),
        }

    # ── Quiz Attempt ───────────────────────────────────────────────────
    def _handle_quiz(self, source, event_ts, details, state, raw, is_replay):
        """
        Rule: LMS quiz attempts are authoritative over IoT.
        If same timestamp conflict from different sources, LMS wins.
        """
        # ── Edge Case 3: Conflicting timestamps ──────────────────────
        if state.last_quiz_attempt and event_ts == state.last_quiz_attempt:
            winner = 'LMS'
            if source != winner:
                return {
                    'decision': f'QUIZ_IGNORED: timestamp conflict, {winner} wins',
                    'logic': (
                        f'Rule (Conflict): quiz_attempt at {event_ts.isoformat()} '
                        f'already recorded. Source={source} loses to {winner}. '
                        'LMS is the authoritative source for quiz events.'
                    ),
                }

        state.quiz_attempts += 1
        state.last_quiz_attempt = event_ts
        return {
            'decision': 'QUIZ_ACCEPTED',
            'logic': (
                f'Rule: Quiz attempt from {source} at {event_ts.isoformat()} accepted. '
                f'Total attempts: {state.quiz_attempts}.'
            ),
        }

    # ── Device Present ─────────────────────────────────────────────────
    def _handle_device_present(self, source, event_ts, details, state, raw, is_replay):
        """
        Rule: If conflicting device_present and device_absent exist at the
        same timestamp, device_present wins (safer assumption = present).
        """
        # ── Edge Case 5: Same-timestamp conflict ─────────────────────
        if state.last_device_absent and event_ts == state.last_device_absent:
            # device_present wins over device_absent at same timestamp
            state.is_device_present = True
            state.last_device_present = event_ts
            return {
                'decision': 'DEVICE_PRESENT_WINS: tie-break over device_absent',
                'logic': (
                    f'Rule (Conflict): device_present and device_absent share '
                    f'timestamp {event_ts.isoformat()}. '
                    'device_present wins as the safer assumption '
                    '(presence is less risky to assume than absence).'
                ),
            }

        if state.last_device_present and event_ts <= state.last_device_present:
            return {
                'decision': 'DEVICE_PRESENT_IGNORED: not newer',
                'logic': (
                    f'Rule: event_ts={event_ts.isoformat()} ≤ '
                    f'last_device_present={state.last_device_present.isoformat()}.'
                ),
            }

        state.is_device_present = True
        state.last_device_present = event_ts
        return {
            'decision': 'DEVICE_PRESENT_ACCEPTED',
            'logic': (
                f'Rule: Device present from {source} at {event_ts.isoformat()} accepted.'
            ),
        }

    # ── Device Absent ──────────────────────────────────────────────────
    def _handle_device_absent(self, source, event_ts, details, state, raw, is_replay):
        """
        Rule: Accept device_absent if newer than last device_present.
        Same-timestamp: device_present wins (handled in _handle_device_present).
        """
        if state.last_device_present and event_ts <= state.last_device_present:
            return {
                'decision': 'DEVICE_ABSENT_IGNORED: not newer than device_present',
                'logic': (
                    f'Rule: event_ts={event_ts.isoformat()} ≤ '
                    f'last_device_present={state.last_device_present.isoformat()}. '
                    'device_absent ignored; student still considered present.'
                ),
            }

        state.is_device_present = False
        state.last_device_absent = event_ts
        return {
            'decision': 'DEVICE_ABSENT_ACCEPTED',
            'logic': (
                f'Rule: Device absent from {source} at {event_ts.isoformat()} accepted.'
            ),
        }

    # ── Attendance ─────────────────────────────────────────────────────
    def _handle_attendance(self, source, event_ts, details, state, raw, is_replay):
        return {
            'decision': 'ATTENDANCE_RECORDED',
            'logic': f'Rule: Attendance marked from {source} at {event_ts.isoformat()}.',
        }

    def _handle_unknown(self, source, event_ts, details, state, raw, is_replay):
        return {
            'decision': 'EVENT_UNKNOWN',
            'logic': 'No rule matched this event type.',
        }


# ---------------------------------------------------------------------------
# Replay Engine
# ---------------------------------------------------------------------------

class ReplayEngine:
    """
    Replays all RawEvents for a given user_id (or all users) in
    chronological order, rebuilding state from scratch.
    """

    @transaction.atomic
    def replay(self, user_id: Optional[str] = None) -> dict:
        """
        Delete existing state and audit logs for user(s) and replay all
        raw events in chronological order.
        Returns summary of replayed events.
        """
        if user_id:
            StudentState.objects.filter(user_id=user_id).delete()
            AuditLog.objects.filter(user_id=user_id).delete()
            events = RawEvent.objects.filter(user_id=user_id).order_by('event_timestamp', 'received_at')
        else:
            StudentState.objects.all().delete()
            AuditLog.objects.all().delete()
            events = RawEvent.objects.all().order_by('event_timestamp', 'received_at')

        # We need to temporarily allow re-ingestion — temporarily clear fingerprints
        # by deleting raw events and re-ingesting from raw_payload
        raw_payloads = [e.raw_payload for e in events]
        if user_id:
            RawEvent.objects.filter(user_id=user_id).delete()
        else:
            RawEvent.objects.all().delete()

        engine = ReconciliationEngine()
        results = []
        for payload in raw_payloads:
            result = engine.ingest(payload, is_replay=True)
            results.append(result)

        return {'replayed': len(results), 'results': results}
