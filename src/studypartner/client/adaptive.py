"""Adaptive Engine — learns from user behavior and optimizes coaching strategy."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from studypartner.client.database import get_db
from studypartner.shared.constants import CONFIDENCE_THRESHOLD, MIN_EVIDENCE_FOR_PREFERENCE
from studypartner.shared.models import AdaptiveWeights

logger = logging.getLogger(__name__)


class AdaptiveEngine:
    """Local feedback loop that learns what coaching works for this user.

    Uses simple statistical tracking (counts + averages), NOT machine learning.
    Runs entirely on-device after every session and on every nudge response.
    """

    def __init__(self):
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Set default adaptive profile values if not present."""
        defaults = {
            "optimal_session_length_min": ("45", 0.0, 0),
            "nudge_delay_start_min": ("0", 0.0, 0),
            "preferred_delivery": ("notification", 0.0, 0),
            "tone_preference": ("casual", 0.0, 0),
            "fatigue_onset_min": ("45", 0.0, 0),
            "technique_affinity_feynman": ("0.5", 0.0, 0),
            "technique_affinity_brain_dump": ("0.5", 0.0, 0),
            "technique_affinity_interleaving": ("0.5", 0.0, 0),
            "technique_affinity_worked_example": ("0.5", 0.0, 0),
        }

        with get_db() as conn:
            for key, (value, confidence, count) in defaults.items():
                existing = conn.execute(
                    "SELECT key FROM adaptive_profile WHERE key=?", (key,)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO adaptive_profile (key, value, confidence, last_updated, evidence_count) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (key, value, confidence, datetime.now().isoformat(), count),
                    )

    def record_outcome(
        self,
        nudge_type: str,
        technique: Optional[str],
        delivery: str,
        user_response: str,
        context_phase: Optional[str] = None,
        session_minute: int = 0,
    ):
        """Record a coaching outcome and update adaptive weights.

        Called every time the user responds to a nudge.
        """
        is_positive = user_response in ("acted_on",)

        # Update technique affinity
        if technique:
            self._update_technique_affinity(technique, is_positive)

        # Update delivery preference
        self._update_delivery_preference(delivery, is_positive)

        # Update session timing patterns
        if user_response == "dismissed" and session_minute < 10:
            self._update_nudge_delay(session_minute)

    def _update_technique_affinity(self, technique: str, success: bool):
        """Update how effective a technique is for this user."""
        key = f"technique_affinity_{technique}"

        with get_db() as conn:
            row = conn.execute(
                "SELECT value, confidence, evidence_count FROM adaptive_profile WHERE key=?",
                (key,)
            ).fetchone()

            if row:
                current_score = float(row["value"])
                count = row["evidence_count"] + 1

                # Simple exponential moving average
                alpha = min(0.3, 1.0 / count)  # Decreasing learning rate
                new_score = current_score * (1 - alpha) + (1.0 if success else 0.0) * alpha

                # Confidence grows with evidence
                confidence = min(1.0, count / (MIN_EVIDENCE_FOR_PREFERENCE * 2))

                conn.execute(
                    "UPDATE adaptive_profile SET value=?, confidence=?, "
                    "last_updated=?, evidence_count=? WHERE key=?",
                    (str(round(new_score, 3)), confidence,
                     datetime.now().isoformat(), count, key),
                )
            else:
                # First observation
                score = 0.7 if success else 0.3
                conn.execute(
                    "INSERT INTO adaptive_profile (key, value, confidence, last_updated, evidence_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, str(score), 0.1, datetime.now().isoformat(), 1),
                )

    def _update_delivery_preference(self, delivery: str, success: bool):
        """Track which delivery method the user responds to best."""
        if not success:
            return  # Only learn from positive responses

        key = "preferred_delivery"
        with get_db() as conn:
            row = conn.execute(
                "SELECT value, evidence_count FROM adaptive_profile WHERE key=?", (key,)
            ).fetchone()

            if row:
                count = row["evidence_count"] + 1
                # Simple majority vote — track the most commonly acted-on delivery
                # For a more sophisticated approach, track per-delivery success rates
                if count >= MIN_EVIDENCE_FOR_PREFERENCE:
                    confidence = min(1.0, count / (MIN_EVIDENCE_FOR_PREFERENCE * 3))
                else:
                    confidence = count / MIN_EVIDENCE_FOR_PREFERENCE * 0.5

                conn.execute(
                    "UPDATE adaptive_profile SET value=?, confidence=?, "
                    "last_updated=?, evidence_count=? WHERE key=?",
                    (delivery, confidence, datetime.now().isoformat(), count, key),
                )

    def _update_nudge_delay(self, dismissed_at_minute: int):
        """If user dismisses nudges early in session, learn warm-up period."""
        key = "nudge_delay_start_min"
        with get_db() as conn:
            row = conn.execute(
                "SELECT value, evidence_count FROM adaptive_profile WHERE key=?", (key,)
            ).fetchone()

            if row:
                current_delay = int(row["value"])
                count = row["evidence_count"] + 1

                # If they keep dismissing before minute X, move the delay up
                new_delay = max(current_delay, dismissed_at_minute + 2)
                new_delay = min(new_delay, 15)  # Cap at 15 minutes

                confidence = min(1.0, count / MIN_EVIDENCE_FOR_PREFERENCE)

                conn.execute(
                    "UPDATE adaptive_profile SET value=?, confidence=?, "
                    "last_updated=?, evidence_count=? WHERE key=?",
                    (str(new_delay), confidence, datetime.now().isoformat(), count, key),
                )

    def compute_session_stats(self, session_id: int) -> dict:
        """Compute stats from a completed session to update adaptive model."""
        with get_db() as conn:
            outcomes = conn.execute(
                "SELECT * FROM coaching_outcomes WHERE session_id=?",
                (session_id,)
            ).fetchall()

        if not outcomes:
            return {}

        stats = {
            "total_nudges": len(outcomes),
            "acted_on": sum(1 for o in outcomes if o["user_response"] == "acted_on"),
            "dismissed": sum(1 for o in outcomes if o["user_response"] == "dismissed"),
            "techniques_used": list(set(o["technique"] for o in outcomes if o["technique"])),
        }

        if stats["total_nudges"] > 0:
            stats["response_rate"] = stats["acted_on"] / stats["total_nudges"]

        return stats
