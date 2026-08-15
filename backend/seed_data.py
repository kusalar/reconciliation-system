"""
Sample Event Dataset for Vidhya Rakshak Reconciliation System.

This script ingests a realistic set of events demonstrating all 5 edge cases.
Run with:
    python seed_data.py

Must be run from the backend/ directory with the venv active.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_proj.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from recon.engine import ReconciliationEngine
from recon.models import RawEvent, StudentState, AuditLog

engine = ReconciliationEngine()


def seed():
    print("=" * 60)
    print("Vidhya Rakshak — Seeding sample event dataset")
    print("=" * 60)

    # ── Student S001: Normal flow ─────────────────────────────────────
    print("\n[S001] Normal engagement flow")
    events = [
        {"source": "LMS",  "userId": "S001", "eventType": "login",
         "timestamp": "2026-08-15T08:00:00+00:00", "details": {}},
        {"source": "IOT",  "userId": "S001", "eventType": "device_present",
         "timestamp": "2026-08-15T08:02:00+00:00", "details": {"room": "Lab-3"}},
        {"source": "LMS",  "userId": "S001", "eventType": "quiz_attempt",
         "timestamp": "2026-08-15T08:30:00+00:00", "details": {"quiz_id": "Q42", "score": 85}},
        {"source": "LMS",  "userId": "S001", "eventType": "logout",
         "timestamp": "2026-08-15T09:30:00+00:00", "details": {}},
    ]
    for e in events:
        r = engine.ingest(e)
        print(f"  [{e['source']}] {e['eventType']} -> {r['status']} / {r.get('decision', '')}")

    # ── EC-1: Duplicate login from LMS ───────────────────────────────
    print("\n[EC-1] Duplicate login from LMS for S001")
    dup = {"source": "LMS", "userId": "S001", "eventType": "login",
           "timestamp": "2026-08-15T08:00:00+00:00", "details": {}}
    r = engine.ingest(dup)
    print(f"  DUPLICATE login -> {r['status']}")

    # ── EC-2: Out-of-order logout from IoT ───────────────────────────
    print("\n[EC-2] Out-of-order IoT logout for S002")
    engine.ingest({"source": "LMS", "userId": "S002", "eventType": "login",
                   "timestamp": "2026-08-15T09:00:00+00:00", "details": {}})
    r = engine.ingest({"source": "IOT", "userId": "S002", "eventType": "logout",
                       "timestamp": "2026-08-15T08:00:00+00:00", "details": {}})
    print(f"  OOO logout -> {r['status']} / {r.get('decision', '')}")

    # ── EC-3: Conflicting quiz timestamps (LMS vs IoT) ────────────────
    print("\n[EC-3] Conflicting quiz timestamps for S003")
    r1 = engine.ingest({"source": "LMS", "userId": "S003", "eventType": "quiz_attempt",
                         "timestamp": "2026-08-15T10:30:00+00:00", "details": {"quiz_id": "Q10"}})
    r2 = engine.ingest({"source": "IOT", "userId": "S003", "eventType": "quiz_attempt",
                         "timestamp": "2026-08-15T10:30:00+00:00", "details": {"quiz_id": "Q10"}})
    print(f"  LMS quiz -> {r1.get('decision', '')}")
    print(f"  IoT quiz (conflict) -> {r2.get('decision', '')}")

    # ── EC-4: Missing userId ──────────────────────────────────────────
    print("\n[EC-4] Missing userId in IoT event")
    r = engine.ingest({"source": "IOT", "userId": None, "eventType": "device_present",
                       "timestamp": "2026-08-15T08:00:00+00:00", "details": {}})
    print(f"  Missing userId -> {r['status']} / {r.get('reason', '')}")

    # ── EC-5: Conflicting device presence at same timestamp ───────────
    print("\n[EC-5] Conflicting device_present and device_absent at same TS for S004")
    ts = "2026-08-15T08:00:00+00:00"
    r1 = engine.ingest({"source": "LMS", "userId": "S004", "eventType": "device_absent",
                         "timestamp": ts, "details": {}})
    r2 = engine.ingest({"source": "IOT", "userId": "S004", "eventType": "device_present",
                         "timestamp": ts, "details": {}})
    print(f"  device_absent -> {r1.get('decision', '')}")
    print(f"  device_present (conflict) -> {r2.get('decision', '')}")

    # ── High-risk student S005 ────────────────────────────────────────
    print("\n[S005] At-risk student — no engagement for 10 days, no quizzes")
    engine.ingest({"source": "LMS", "userId": "S005", "eventType": "login",
                   "timestamp": "2026-08-05T08:00:00+00:00", "details": {}})
    engine.ingest({"source": "LMS", "userId": "S005", "eventType": "logout",
                   "timestamp": "2026-08-05T08:10:00+00:00", "details": {}})

    print("\n" + "=" * 60)
    print("Dataset seeded successfully!")
    print(f"  Raw Events:    {RawEvent.objects.count()}")
    print(f"  Student States: {StudentState.objects.count()}")
    print(f"  Audit Logs:    {AuditLog.objects.count()}")
    print("=" * 60)


if __name__ == '__main__':
    seed()

