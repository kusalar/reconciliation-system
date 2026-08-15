"""
Mock AI Model: Dropout Risk Scorer

Deterministic scoring based on reconciled student behavioral signals.
No ML/LLM — pure heuristic rule-based logic.

Risk Factors (additive, capped at 100):
  - No login in the last 7 days:             +30
  - Device never present:                    +25
  - Device absent more than present:         +15
  - Quiz attempts < 2:                       +20
  - Currently logged out:                    +10

Risk Reduction:
  - Multiple quiz attempts (≥5):             -10
  - Active login (is_logged_in):             -5
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional


def compute_risk_score(state: dict) -> dict:
    """
    Compute a dropout risk score from a reconciled student state dict.

    Args:
        state: dict representation of StudentState fields.

    Returns:
        dict with 'score' (0–100), 'risk_level', and 'factors' list.
    """
    score = 0
    factors = []

    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt

    now = datetime.now(tz=dt_timezone.utc)
    last_login = _parse_dt(state.get('last_login'))
    is_logged_in = state.get('is_logged_in', False)
    is_device_present = state.get('is_device_present', False)
    last_device_present = _parse_dt(state.get('last_device_present'))
    last_device_absent = _parse_dt(state.get('last_device_absent'))
    quiz_attempts = state.get('quiz_attempts', 0)

    # ── Factor 1: No recent login ──────────────────────────────────────
    if last_login is None:
        score += 35
        factors.append({
            'factor': 'No login recorded',
            'delta': +35,
            'logic': 'Student has never logged in to the LMS.',
        })
    elif (now - last_login) > timedelta(days=7):
        score += 30
        factors.append({
            'factor': 'No login in last 7 days',
            'delta': +30,
            'logic': f'Last login was {last_login.isoformat()}, over 7 days ago.',
        })

    # ── Factor 2: Device never present ────────────────────────────────
    if last_device_present is None:
        score += 25
        factors.append({
            'factor': 'Device never detected in classroom',
            'delta': +25,
            'logic': 'No device_present event recorded; student may not attend physically.',
        })
    elif not is_device_present:
        score += 10
        factors.append({
            'factor': 'Device currently absent from classroom',
            'delta': +10,
            'logic': 'Most recent device signal indicates absence.',
        })

    # ── Factor 3: Low quiz engagement ─────────────────────────────────
    if quiz_attempts == 0:
        score += 20
        factors.append({
            'factor': 'No quiz attempts',
            'delta': +20,
            'logic': 'Student has not attempted any quizzes.',
        })
    elif quiz_attempts < 2:
        score += 10
        factors.append({
            'factor': 'Low quiz engagement (< 2 attempts)',
            'delta': +10,
            'logic': f'Only {quiz_attempts} quiz attempt(s) recorded.',
        })

    # ── Factor 4: Currently logged out ────────────────────────────────
    if not is_logged_in and last_login is not None:
        score += 5
        factors.append({
            'factor': 'Currently logged out',
            'delta': +5,
            'logic': 'Student is not currently active on the LMS.',
        })

    # ── Reduction: High quiz engagement ───────────────────────────────
    if quiz_attempts >= 5:
        score -= 10
        factors.append({
            'factor': 'High quiz engagement (≥ 5 attempts)',
            'delta': -10,
            'logic': f'{quiz_attempts} quiz attempts indicate strong engagement.',
        })

    # ── Reduction: Active login ────────────────────────────────────────
    if is_logged_in:
        score -= 5
        factors.append({
            'factor': 'Currently logged in',
            'delta': -5,
            'logic': 'Student is actively using the LMS right now.',
        })

    # Cap score to [0, 100]
    score = max(0, min(100, score))

    if score >= 70:
        risk_level = 'HIGH'
    elif score >= 40:
        risk_level = 'MEDIUM'
    else:
        risk_level = 'LOW'

    return {
        'score': score,
        'risk_level': risk_level,
        'factors': factors,
        'model': 'VidhyaRakshak-Heuristic-v1',
    }
