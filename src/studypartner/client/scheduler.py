"""Spaced repetition scheduler using SM-2 algorithm."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from studypartner.client.database import get_db

logger = logging.getLogger(__name__)


def schedule_review(topic_id: int) -> None:
    """Schedule the first review for a topic (1 day from now)."""
    with get_db() as conn:
        # Check if already scheduled
        existing = conn.execute(
            "SELECT id FROM review_queue WHERE topic_id=?", (topic_id,)
        ).fetchone()

        if not existing:
            conn.execute(
                "INSERT INTO review_queue (topic_id, next_review, interval_days) VALUES (?, ?, ?)",
                (topic_id, (date.today() + timedelta(days=1)).isoformat(), 1),
            )


def update_review(topic_id: int, quality: int) -> None:
    """Update the review schedule after a retrieval attempt.

    Uses the SM-2 algorithm:
    - quality: 0-5 rating (0=complete blank, 5=perfect recall)
    - If quality >= 3: increase interval
    - If quality < 3: reset to 1 day
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM review_queue WHERE topic_id=?", (topic_id,)
        ).fetchone()

        if not row:
            schedule_review(topic_id)
            return

        r = dict(row)
        interval = r["interval_days"]
        ease = r["ease_factor"]
        count = r["review_count"]

        if quality >= 3:
            # Successful recall — increase interval
            if count == 0:
                interval = 1
            elif count == 1:
                interval = 6
            else:
                interval = int(interval * ease)

            # Update ease factor
            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        else:
            # Failed recall — reset
            interval = 1
            # ease stays the same

        next_review = (date.today() + timedelta(days=interval)).isoformat()

        conn.execute(
            """UPDATE review_queue
               SET next_review=?, interval_days=?, ease_factor=?, review_count=review_count+1
               WHERE topic_id=?""",
            (next_review, interval, ease, topic_id),
        )


def get_due_reviews() -> list[dict]:
    """Get all topics due for review today or overdue."""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT t.name, rq.next_review, rq.interval_days, rq.review_count,
                       julianday('now') - julianday(rq.next_review) as overdue_days
                FROM review_queue rq
                JOIN topics t ON rq.topic_id = t.id
                WHERE rq.next_review <= date('now', '+1 day')
                ORDER BY overdue_days DESC
            """).fetchall()

        return [
            {
                "topic": row["name"],
                "next_review": row["next_review"],
                "overdue_days": max(0, int(row["overdue_days"])),
                "review_count": row["review_count"],
            }
            for row in rows
        ]
    except Exception:
        return []
