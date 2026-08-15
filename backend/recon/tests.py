"""
Automated Test Suite for Vidhya Rakshak Reconciliation Engine.

Tests cover all 5 required interacting edge cases:
  EC-1: Duplicate login event from LMS
  EC-2: Out-of-order logout from IoT (timestamp before login)
  EC-3: Conflicting quiz attempt timestamps from LMS and IoT
  EC-4: Missing userId in IoT event
  EC-5: Conflicting device presence events with same timestamp

Also tests:
  - State versioning consistency
  - Replay idempotency
  - Audit log generation
  - AI risk score determinism
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_proj.settings')
django.setup()

import pytest
from django.test import TestCase
from recon.engine import ReconciliationEngine, ReplayEngine
from recon.ai_model import compute_risk_score
from recon.models import RawEvent, StudentState, AuditLog


def clear_db():
    RawEvent.objects.all().delete()
    StudentState.objects.all().delete()
    AuditLog.objects.all().delete()


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_login(user_id='S001', source='LMS', ts='2026-08-15T08:00:00+00:00'):
    return {'source': source, 'userId': user_id, 'eventType': 'login', 'timestamp': ts, 'details': {}}

def make_logout(user_id='S001', source='LMS', ts='2026-08-15T09:00:00+00:00'):
    return {'source': source, 'userId': user_id, 'eventType': 'logout', 'timestamp': ts, 'details': {}}

def make_quiz(user_id='S001', source='LMS', ts='2026-08-15T08:30:00+00:00'):
    return {'source': source, 'userId': user_id, 'eventType': 'quiz_attempt', 'timestamp': ts, 'details': {}}

def make_device_present(user_id='S001', source='IOT', ts='2026-08-15T08:00:00+00:00'):
    return {'source': source, 'userId': user_id, 'eventType': 'device_present', 'timestamp': ts, 'details': {}}

def make_device_absent(user_id='S001', source='IOT', ts='2026-08-15T09:00:00+00:00'):
    return {'source': source, 'userId': user_id, 'eventType': 'device_absent', 'timestamp': ts, 'details': {}}


# ═══════════════════════════════════════════════════════════════════════════
# EC-1: Duplicate Login Event from LMS
# ═══════════════════════════════════════════════════════════════════════════

class TestEC1DuplicateLogin(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_duplicate_login_rejected(self):
        """Sending the exact same login event twice must be idempotent."""
        payload = make_login('S001', 'LMS', '2026-08-15T08:00:00+00:00')

        r1 = self.engine.ingest(payload)
        r2 = self.engine.ingest(payload)  # duplicate

        assert r1['status'] == 'accepted', f"First ingest should be accepted, got: {r1}"
        assert r2['status'] == 'duplicate', f"Second ingest must be duplicate, got: {r2}"

    def test_duplicate_does_not_create_new_state_version(self):
        """Duplicate must not bump the state version."""
        payload = make_login('S001', 'LMS', '2026-08-15T08:00:00+00:00')
        self.engine.ingest(payload)
        self.engine.ingest(payload)

        versions = StudentState.objects.filter(user_id='S001').count()
        assert versions == 1, f"Expected 1 version, got {versions}"

    def test_duplicate_creates_audit_record(self):
        """Even a duplicate event should create an audit record explaining it was dropped."""
        payload = make_login('S001', 'LMS', '2026-08-15T08:00:00+00:00')
        self.engine.ingest(payload)
        self.engine.ingest(payload)

        audit = AuditLog.objects.filter(user_id='S001', decision__icontains='duplicate').first()
        assert audit is not None, "Audit record for duplicate not found"

    def test_three_duplicates_still_idempotent(self):
        """Three duplicates should result in exactly 1 raw event and 1 state version."""
        payload = make_login('S002', 'LMS', '2026-08-15T08:00:00+00:00')
        for _ in range(3):
            self.engine.ingest(payload)
        assert RawEvent.objects.filter(user_id='S002').count() == 1
        assert StudentState.objects.filter(user_id='S002').count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# EC-2: Out-of-Order Logout from IoT
# ═══════════════════════════════════════════════════════════════════════════

class TestEC2OutOfOrderLogout(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_oot_logout_before_login_flagged(self):
        """Logout with timestamp before login should be flagged as out-of-order."""
        # Login at 09:00
        self.engine.ingest(make_login('S003', 'LMS', '2026-08-15T09:00:00+00:00'))
        # Logout at 08:00 (before login — out of order)
        result = self.engine.ingest(make_logout('S003', 'IOT', '2026-08-15T08:00:00+00:00'))

        assert result['status'] == 'accepted'
        assert 'out-of-order' in result['decision'].lower(), f"Expected OOO in decision: {result['decision']}"

    def test_oot_logout_does_not_change_login_state(self):
        """State should remain 'logged in' after an out-of-order logout."""
        self.engine.ingest(make_login('S003', 'LMS', '2026-08-15T09:00:00+00:00'))
        self.engine.ingest(make_logout('S003', 'IOT', '2026-08-15T08:00:00+00:00'))

        state = StudentState.objects.filter(user_id='S003').order_by('-version').first()
        assert state.is_logged_in is True, "is_logged_in should remain True after OOO logout"

    def test_valid_logout_after_login_accepted(self):
        """A logout after login should be accepted normally."""
        self.engine.ingest(make_login('S004', 'LMS', '2026-08-15T08:00:00+00:00'))
        result = self.engine.ingest(make_logout('S004', 'LMS', '2026-08-15T10:00:00+00:00'))

        assert result['decision'] == 'LOGOUT_ACCEPTED'
        state = StudentState.objects.filter(user_id='S004').order_by('-version').first()
        assert state.is_logged_in is False


# ═══════════════════════════════════════════════════════════════════════════
# EC-3: Conflicting Quiz Attempt Timestamps from LMS and IoT
# ═══════════════════════════════════════════════════════════════════════════

class TestEC3ConflictingQuizTimestamps(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_lms_quiz_accepted_first(self):
        """LMS quiz attempt is accepted."""
        result = self.engine.ingest(make_quiz('S005', 'LMS', '2026-08-15T08:30:00+00:00'))
        assert result['decision'] == 'QUIZ_ACCEPTED'

    def test_iot_quiz_same_timestamp_rejected(self):
        """IoT quiz attempt at same timestamp as LMS should be ignored (LMS wins)."""
        self.engine.ingest(make_quiz('S005', 'LMS', '2026-08-15T08:30:00+00:00'))
        # Note: different fingerprint since source differs, so not a duplicate
        result = self.engine.ingest(make_quiz('S005', 'IOT', '2026-08-15T08:30:00+00:00'))

        assert 'ignored' in result['decision'].lower() or 'conflict' in result['decision'].lower(), \
            f"IoT quiz at same TS should be ignored. Got: {result['decision']}"

    def test_quiz_count_not_doubled_on_conflict(self):
        """Quiz count should remain 1 when IoT duplicate (same TS) is ignored."""
        self.engine.ingest(make_quiz('S005', 'LMS', '2026-08-15T08:30:00+00:00'))
        self.engine.ingest(make_quiz('S005', 'IOT', '2026-08-15T08:30:00+00:00'))

        state = StudentState.objects.filter(user_id='S005').order_by('-version').first()
        assert state.quiz_attempts == 1, f"Expected 1 quiz attempt, got {state.quiz_attempts}"

    def test_different_timestamps_both_accepted(self):
        """Quiz attempts from LMS and IoT at DIFFERENT timestamps should both be accepted."""
        self.engine.ingest(make_quiz('S006', 'LMS', '2026-08-15T08:30:00+00:00'))
        result = self.engine.ingest(make_quiz('S006', 'IOT', '2026-08-15T09:30:00+00:00'))
        assert result['decision'] == 'QUIZ_ACCEPTED'


# ═══════════════════════════════════════════════════════════════════════════
# EC-4: Missing userId in IoT Event
# ═══════════════════════════════════════════════════════════════════════════

class TestEC4MissingUserId(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_null_userid_rejected(self):
        payload = {'source': 'IOT', 'userId': None, 'eventType': 'device_present',
                   'timestamp': '2026-08-15T08:00:00+00:00', 'details': {}}
        result = self.engine.ingest(payload)
        assert result['status'] == 'rejected'
        assert 'userId' in result['reason']

    def test_empty_string_userid_rejected(self):
        payload = {'source': 'IOT', 'userId': '', 'eventType': 'device_present',
                   'timestamp': '2026-08-15T08:00:00+00:00', 'details': {}}
        result = self.engine.ingest(payload)
        assert result['status'] == 'rejected'

    def test_missing_userid_key_rejected(self):
        payload = {'source': 'IOT', 'eventType': 'device_present',
                   'timestamp': '2026-08-15T08:00:00+00:00', 'details': {}}
        result = self.engine.ingest(payload)
        assert result['status'] == 'rejected'

    def test_missing_userid_does_not_corrupt_state(self):
        """Rejected event must not create any StudentState rows."""
        payload = {'source': 'IOT', 'userId': None, 'eventType': 'device_present',
                   'timestamp': '2026-08-15T08:00:00+00:00', 'details': {}}
        self.engine.ingest(payload)
        assert StudentState.objects.count() == 0

    def test_missing_userid_audit_created(self):
        """Missing userId must create an audit record for traceability."""
        payload = {'source': 'IOT', 'userId': None, 'eventType': 'device_present',
                   'timestamp': '2026-08-15T08:00:00+00:00', 'details': {}}
        self.engine.ingest(payload)
        audit = AuditLog.objects.filter(decision__icontains='missing userId').first()
        assert audit is not None, "Audit for missing userId not found"


# ═══════════════════════════════════════════════════════════════════════════
# EC-5: Conflicting Device Presence at Same Timestamp
# ═══════════════════════════════════════════════════════════════════════════

class TestEC5ConflictingDevicePresence(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_device_present_wins_over_absent_same_ts(self):
        """device_present should win over device_absent at the same timestamp."""
        ts = '2026-08-15T08:00:00+00:00'

        # Send absent first
        self.engine.ingest(make_device_absent('S007', 'LMS', ts))
        # Then present at same ts
        result = self.engine.ingest(make_device_present('S007', 'IOT', ts))

        assert 'wins' in result['decision'].lower() or 'accepted' in result['decision'].lower(), \
            f"device_present should win. Got: {result['decision']}"

        state = StudentState.objects.filter(user_id='S007').order_by('-version').first()
        assert state.is_device_present is True, "is_device_present should be True"

    def test_conflict_audit_explains_tiebreak(self):
        """Audit must explain why device_present won."""
        ts = '2026-08-15T08:00:00+00:00'
        self.engine.ingest(make_device_absent('S007', 'LMS', ts))
        self.engine.ingest(make_device_present('S007', 'IOT', ts))

        audit = AuditLog.objects.filter(user_id='S007', decision__icontains='wins').first()
        assert audit is not None, "Tie-break audit record not found"
        assert 'safer' in audit.resolution_logic.lower() or 'present' in audit.resolution_logic.lower()


# ═══════════════════════════════════════════════════════════════════════════
# State Versioning Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestStateVersioning(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()

    def test_each_accepted_event_increments_version(self):
        """Every accepted event should create a new state version."""
        events = [
            make_login('S008', 'LMS', '2026-08-15T08:00:00+00:00'),
            make_quiz('S008', 'LMS', '2026-08-15T08:30:00+00:00'),
            make_logout('S008', 'LMS', '2026-08-15T09:00:00+00:00'),
        ]
        for e in events:
            self.engine.ingest(e)

        versions = StudentState.objects.filter(user_id='S008').count()
        assert versions == 3, f"Expected 3 versions, got {versions}"

    def test_versions_are_sequential(self):
        """Versions must be sequential starting from 1."""
        events = [
            make_login('S009', 'LMS', '2026-08-15T08:00:00+00:00'),
            make_device_present('S009', 'IOT', '2026-08-15T08:05:00+00:00'),
        ]
        for e in events:
            self.engine.ingest(e)

        versions = list(StudentState.objects.filter(user_id='S009').values_list('version', flat=True).order_by('version'))
        assert versions == [1, 2], f"Expected [1, 2], got {versions}"


# ═══════════════════════════════════════════════════════════════════════════
# Replay Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestReplay(TestCase):
    def setUp(self):
        clear_db()
        self.engine = ReconciliationEngine()
        self.replay = ReplayEngine()

    def test_replay_produces_same_state(self):
        """Replaying events must produce the same final state."""
        events = [
            make_login('S010', 'LMS', '2026-08-15T08:00:00+00:00'),
            make_quiz('S010', 'LMS', '2026-08-15T08:30:00+00:00'),
            make_device_present('S010', 'IOT', '2026-08-15T08:05:00+00:00'),
            make_logout('S010', 'LMS', '2026-08-15T09:00:00+00:00'),
        ]
        for e in events:
            self.engine.ingest(e)

        state_before = StudentState.objects.filter(user_id='S010').order_by('-version').first()
        is_logged_in_before = state_before.is_logged_in
        quiz_before = state_before.quiz_attempts

        # Replay
        self.replay.replay(user_id='S010')

        state_after = StudentState.objects.filter(user_id='S010').order_by('-version').first()
        assert state_after.is_logged_in == is_logged_in_before
        assert state_after.quiz_attempts == quiz_before

    def test_replay_audit_marked_as_replay(self):
        """Audit logs during replay must be marked is_replay=True."""
        self.engine.ingest(make_login('S011', 'LMS', '2026-08-15T08:00:00+00:00'))
        self.replay.replay(user_id='S011')

        replay_audits = AuditLog.objects.filter(user_id='S011', is_replay=True)
        assert replay_audits.exists(), "No replay audit records found"

    def test_replay_is_idempotent(self):
        """Replaying twice should produce identical final states."""
        self.engine.ingest(make_login('S012', 'LMS', '2026-08-15T08:00:00+00:00'))
        self.replay.replay(user_id='S012')
        state1 = StudentState.objects.filter(user_id='S012').order_by('-version').first()

        self.replay.replay(user_id='S012')
        state2 = StudentState.objects.filter(user_id='S012').order_by('-version').first()

        assert state1.is_logged_in == state2.is_logged_in
        assert state1.quiz_attempts == state2.quiz_attempts


# ═══════════════════════════════════════════════════════════════════════════
# AI Model Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAIModel(TestCase):
    def test_no_data_student_high_risk(self):
        """A student with no events should have a high risk score."""
        state = {
            'is_logged_in': False, 'last_login': None, 'last_logout': None,
            'is_device_present': False, 'last_device_present': None,
            'last_device_absent': None, 'quiz_attempts': 0, 'last_quiz_attempt': None,
        }
        result = compute_risk_score(state)
        assert result['score'] >= 70, f"Expected HIGH risk, got {result['score']}"
        assert result['risk_level'] == 'HIGH'

    def test_active_student_low_risk(self):
        """An engaged student should have a low risk score."""
        from datetime import datetime, timezone as tz
        now = datetime.now(tz=tz.utc)
        state = {
            'is_logged_in': True,
            'last_login': now.isoformat(),
            'last_logout': None,
            'is_device_present': True,
            'last_device_present': now.isoformat(),
            'last_device_absent': None,
            'quiz_attempts': 7,
            'last_quiz_attempt': now.isoformat(),
        }
        result = compute_risk_score(state)
        assert result['score'] < 40, f"Expected LOW risk, got {result['score']}"
        assert result['risk_level'] == 'LOW'

    def test_score_deterministic(self):
        """Same state must always yield the same score."""
        state = {
            'is_logged_in': False, 'last_login': '2026-08-10T08:00:00+00:00',
            'last_logout': '2026-08-10T09:00:00+00:00',
            'is_device_present': False, 'last_device_present': '2026-08-10T08:00:00+00:00',
            'last_device_absent': '2026-08-10T09:00:00+00:00',
            'quiz_attempts': 1, 'last_quiz_attempt': '2026-08-10T08:30:00+00:00',
        }
        r1 = compute_risk_score(state)
        r2 = compute_risk_score(state)
        assert r1['score'] == r2['score']
        assert r1['risk_level'] == r2['risk_level']

    def test_score_in_valid_range(self):
        """Score must always be in [0, 100]."""
        states = [
            {'is_logged_in': True, 'last_login': '2026-08-15T08:00:00+00:00',
             'quiz_attempts': 99, 'is_device_present': True,
             'last_device_present': '2026-08-15T08:00:00+00:00'},
            {'is_logged_in': False, 'last_login': None, 'quiz_attempts': 0,
             'is_device_present': False, 'last_device_present': None},
        ]
        for s in states:
            r = compute_risk_score(s)
            assert 0 <= r['score'] <= 100, f"Score out of range: {r['score']}"
