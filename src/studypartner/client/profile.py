"""Learning profile manager — persistent profile that tracks learning journey."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from studypartner.shared.constants import LEARNING_PROFILE_PATH, DATA_DIR

logger = logging.getLogger(__name__)


class TopicProfile(BaseModel):
    """Profile for a single topic."""
    name: str
    total_hours: float = 0
    session_count: int = 0
    mastery_score: float = 0.0
    knowledge_gaps: list[str] = Field(default_factory=list)
    last_session: Optional[str] = None
    last_retrieval: Optional[str] = None
    first_seen: Optional[str] = None


class LearningProfile(BaseModel):
    """Persistent learning profile that builds over time."""
    user_name: Optional[str] = None
    topics: dict[str, TopicProfile] = Field(default_factory=dict)
    total_study_hours: float = 0
    total_sessions: int = 0
    study_streak_days: int = 0
    last_study_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def load(cls) -> LearningProfile:
        """Load profile from disk, or return defaults."""
        if LEARNING_PROFILE_PATH.exists():
            try:
                data = json.loads(LEARNING_PROFILE_PATH.read_text())
                return cls(**data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load learning profile: {e}")
                return cls()
        return cls()

    def save(self) -> None:
        """Save profile to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LEARNING_PROFILE_PATH.write_text(self.model_dump_json(indent=2))

    def update_topic(
        self,
        topic_name: str,
        hours_delta: float = 0,
        mastery_delta: float = 0,
        gaps: Optional[list[str]] = None,
    ):
        """Update a topic's profile data."""
        if topic_name not in self.topics:
            self.topics[topic_name] = TopicProfile(
                name=topic_name,
                first_seen=datetime.now().isoformat(),
            )

        tp = self.topics[topic_name]
        tp.total_hours += hours_delta
        tp.session_count += 1
        tp.mastery_score = min(1.0, max(0.0, tp.mastery_score + mastery_delta))
        tp.last_session = datetime.now().isoformat()

        if gaps:
            # Merge gaps, removing duplicates
            existing = set(tp.knowledge_gaps)
            tp.knowledge_gaps = list(existing | set(gaps))

    def record_session(self, topic: Optional[str], duration_hours: float):
        """Record a completed session."""
        self.total_sessions += 1
        self.total_study_hours += duration_hours

        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_study_date == today:
            pass  # Same day
        elif self.last_study_date:
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if self.last_study_date == yesterday:
                self.study_streak_days += 1
            else:
                self.study_streak_days = 1
        else:
            self.study_streak_days = 1

        self.last_study_date = today

        if topic:
            self.update_topic(topic, hours_delta=duration_hours)

        self.save()

    def get_welcome_back_message(self) -> Optional[str]:
        """Generate a welcome-back message based on profile state."""
        if not self.last_study_date:
            return None

        last_date = datetime.strptime(self.last_study_date, "%Y-%m-%d")
        days_away = (datetime.now() - last_date).days

        if days_away == 0:
            return None  # Same day, no welcome back

        # Find the most recently studied topic
        recent_topic = None
        recent_time = None
        for tp in self.topics.values():
            if tp.last_session:
                t = datetime.fromisoformat(tp.last_session)
                if recent_time is None or t > recent_time:
                    recent_time = t
                    recent_topic = tp

        if not recent_topic:
            return None

        msg = f"👋 Welcome back! It's been {days_away} day(s).\n"
        msg += f"Last session: {recent_topic.name}\n"

        if days_away >= 2:
            msg += "⚠️ Perfect time for spaced review! Let's start with a retrieval check.\n"

        if recent_topic.knowledge_gaps:
            gaps = ", ".join(recent_topic.knowledge_gaps[:3])
            msg += f"Known gaps: {gaps}\n"

        if self.study_streak_days > 1:
            msg += f"🔥 Study streak: {self.study_streak_days} days!"

        return msg
