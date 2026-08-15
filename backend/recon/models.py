"""
Database models for the Reconciliation Engine.

RawEvent      — immutable log of every event as received
StudentState  — versioned reconciled state per student
AuditLog      — one record per reconciliation decision
"""
from django.db import models
from django.utils import timezone


class RawEvent(models.Model):
    """Immutable, append-only store of every received event."""

    SOURCE_CHOICES = [
        ('LMS', 'Learning Management System'),
        ('IOT', 'Classroom IoT Device'),
        ('ATTENDANCE', 'Attendance System'),
    ]

    EVENT_TYPE_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('quiz_attempt', 'Quiz Attempt'),
        ('device_present', 'Device Present'),
        ('device_absent', 'Device Absent'),
        ('attendance_marked', 'Attendance Marked'),
    ]

    id = models.AutoField(primary_key=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    user_id = models.CharField(max_length=100, null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    event_timestamp = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField()
    # SHA256(source + user_id + event_type + event_timestamp) for dedup
    fingerprint = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ['event_timestamp', 'received_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['event_timestamp']),
            models.Index(fields=['fingerprint']),
        ]

    def __str__(self):
        return f"[{self.source}] {self.user_id} / {self.event_type} @ {self.event_timestamp}"


class StudentState(models.Model):
    """
    Versioned reconciled state for a single student.
    Each reconciliation decision creates a new version row.
    """
    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=100, db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    is_logged_in = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    last_logout = models.DateTimeField(null=True, blank=True)
    is_device_present = models.BooleanField(default=False)
    last_device_present = models.DateTimeField(null=True, blank=True)
    last_device_absent = models.DateTimeField(null=True, blank=True)
    quiz_attempts = models.PositiveIntegerField(default=0)
    last_quiz_attempt = models.DateTimeField(null=True, blank=True)

    # Ordered list of reconciled event summaries
    timeline = models.JSONField(default=list)
    # Fingerprints of triggering events
    triggered_by_events = models.JSONField(default=list)

    class Meta:
        ordering = ['user_id', 'version']
        unique_together = [('user_id', 'version')]

    def __str__(self):
        return f"StudentState[{self.user_id}] v{self.version}"


class AuditLog(models.Model):
    """One audit record per reconciliation decision."""
    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=100, db_index=True)
    state_version = models.PositiveIntegerField()
    decision = models.CharField(max_length=200)
    resolution_logic = models.TextField()
    input_events = models.JSONField(default=list)
    timestamp = models.DateTimeField(default=timezone.now)
    is_replay = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit[{self.user_id}] v{self.state_version}: {self.decision}"
