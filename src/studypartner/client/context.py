"""Context Composer — builds the context packet from local data for Gemini."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from studypartner.client.database import get_active_session, get_db
from studypartner.shared.constants import (
    ADAPTIVE_PROFILE_PATH,
    LEARNING_PROFILE_PATH,
)
from studypartner.shared.models import (
    AdaptiveWeights,
    ContextPacket,
    LearningHistory,
    SessionContext,
    SpacedReviewItem,
    StudyGuideRules,
    StudyPhase,
)

logger = logging.getLogger(__name__)


def _get_time_of_day() -> str:
    """Get time of day category."""
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    elif hour < 21:
        return "evening"
    return "night"


def _load_adaptive_weights() -> AdaptiveWeights:
    """Load adaptive weights from the adaptive profile database."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT key, value, confidence FROM adaptive_profile WHERE confidence >= 0.3"
            ).fetchall()

        if not rows:
            return AdaptiveWeights()

        weights = AdaptiveWeights()
        for row in rows:
            key, value, confidence = row["key"], row["value"], row["confidence"]
            if key == "optimal_session_length_min":
                weights.optimal_session_length_min = int(value)
            elif key == "nudge_delay_start_min":
                weights.nudge_delay_start_min = int(value)
            elif key == "preferred_delivery":
                weights.preferred_delivery = value
            elif key == "tone_preference":
                weights.tone_preference = value
            elif key == "fatigue_onset_min":
                weights.fatigue_onset_min = int(value)
            elif key.startswith("technique_affinity_"):
                technique = key.replace("technique_affinity_", "")
                weights.preferred_techniques[technique] = float(value)

        return weights
    except Exception as e:
        logger.warning(f"Failed to load adaptive weights: {e}")
        return AdaptiveWeights()


def _get_learning_history(topic: str) -> Optional[LearningHistory]:
    """Get learning history for a specific topic."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE name=?", (topic,)
            ).fetchone()

        if not row:
            return None

        r = dict(row)
        gaps = json.loads(r["gaps"]) if r["gaps"] else []

        return LearningHistory(
            topic=r["name"],
            total_sessions=r["session_count"],
            total_hours=r["total_hours"],
            last_session=r["last_seen"],
            last_retrieval_check=r["last_retrieval"] is not None,
            knowledge_gaps=gaps,
            mastery_score=r["mastery_score"],
        )
    except Exception as e:
        logger.warning(f"Failed to get learning history for {topic}: {e}")
        return None


def _get_spaced_reviews() -> list[SpacedReviewItem]:
    """Get topics due for spaced review."""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT t.name, rq.next_review,
                       julianday('now') - julianday(rq.next_review) as overdue_days
                FROM review_queue rq
                JOIN topics t ON rq.topic_id = t.id
                WHERE rq.next_review <= date('now', '+1 day')
                ORDER BY overdue_days DESC
            """).fetchall()

        return [
            SpacedReviewItem(topic=row["name"], overdue_days=max(0, int(row["overdue_days"])))
            for row in rows
        ]
    except Exception:
        return []


def build_context_packet(
    current_topic: Optional[str] = None,
    session_duration_min: float = 0,
    study_phase: StudyPhase = StudyPhase.UNKNOWN,
    pomodoro_count: int = 0,
) -> ContextPacket:
    """Build the full context packet for Gemini.

    This is the 'warm start' — how the AI remembers you
    without the cloud storing anything.
    """
    # Load adaptive weights from local DB
    adaptive_weights = _load_adaptive_weights()

    # Calculate break timing
    break_due_in = max(
        0, adaptive_weights.optimal_session_length_min - session_duration_min
    )

    # Build session context
    session_ctx = SessionContext(
        current_topic=current_topic,
        session_duration_minutes=session_duration_min,
        study_phase=study_phase,
        pomodoro_count=pomodoro_count,
        break_due_in_minutes=break_due_in,
        time_of_day=_get_time_of_day(),
        is_peak_focus_window=False,  # TODO: detect from adaptive profile
    )

    # Get learning history for current topic
    learning_history = _get_learning_history(current_topic) if current_topic else None

    # Get spaced review items
    spaced_reviews = _get_spaced_reviews()

    # Build study guide rules (use adaptive overrides where confident)
    rules = StudyGuideRules()
    if adaptive_weights.optimal_session_length_min != 45:
        rules.max_session_without_break_min = adaptive_weights.optimal_session_length_min

    return ContextPacket(
        session_context=session_ctx,
        learning_history=learning_history,
        spaced_review_due=spaced_reviews,
        adaptive_weights=adaptive_weights,
        study_guide_rules=rules,
    )
