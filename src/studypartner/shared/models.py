"""Shared Pydantic models for StudyPartner context packets and data types."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class StudyPhase(str, Enum):
    ACQUIRE = "acquire"
    PROCESS = "process"
    CONSOLIDATE = "consolidate"
    UNKNOWN = "unknown"


class DetectedActivity(str, Enum):
    CODING = "coding"
    READING = "reading"
    BROWSING = "browsing"
    AI_CHAT = "ai_chat"
    IDLE = "idle"
    OTHER = "other"


class NudgeType(str, Enum):
    TIME_BASED = "time_based"
    PHASE_TRANSITION = "phase_transition"
    ANTI_PATTERN = "anti_pattern"
    RECALL_PROMPT = "recall_prompt"
    PROGRESS = "progress"
    SCHEDULED_REVIEW = "scheduled_review"


class NudgeDelivery(str, Enum):
    NOTIFICATION = "notification"
    VOICE = "voice"
    OVERLAY = "overlay"
    AMBIENT = "ambient"


class UserResponse(str, Enum):
    ACTED_ON = "acted_on"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    IGNORED = "ignored"


# --- Context Packet Models ---

class SessionContext(BaseModel):
    """Current session state sent to Gemini."""
    current_topic: Optional[str] = None
    session_duration_minutes: float = 0
    study_phase: StudyPhase = StudyPhase.UNKNOWN
    pomodoro_count: int = 0
    break_due_in_minutes: Optional[float] = None
    time_of_day: str = "unknown"
    is_peak_focus_window: bool = False


class LearningHistory(BaseModel):
    """Per-topic learning history."""
    topic: str
    total_sessions: int = 0
    total_hours: float = 0
    last_session: Optional[datetime] = None
    last_retrieval_check: bool = False
    knowledge_gaps: list[str] = Field(default_factory=list)
    mastery_score: float = 0.0


class SpacedReviewItem(BaseModel):
    """A topic due for spaced review."""
    topic: str
    overdue_days: int = 0


class AdaptiveWeights(BaseModel):
    """Per-user learned coaching parameters from the Adaptive Engine."""
    preferred_techniques: dict[str, float] = Field(
        default_factory=lambda: {
            "feynman": 0.5,
            "brain_dump": 0.5,
            "interleaving": 0.5,
            "worked_example": 0.5,
        }
    )
    optimal_session_length_min: int = 45
    nudge_delay_start_min: int = 0
    preferred_delivery: NudgeDelivery = NudgeDelivery.NOTIFICATION
    tone_preference: str = "casual"
    fatigue_onset_min: int = 45
    current_motivation_level: str = "medium"
    coaching_density: str = "moderate"


class StudyGuideRules(BaseModel):
    """Guardrail rules from the study guide (defaults, overridable by adaptive)."""
    max_input_without_output_min: int = 30
    max_same_problem_type_min: int = 20
    max_session_without_break_min: int = 45
    detect_ai_copy_paste: bool = True
    detect_passive_rereading: bool = True


class ContextPacket(BaseModel):
    """Complete context packet sent to Gemini with each request."""
    session_context: SessionContext = Field(default_factory=SessionContext)
    learning_history: Optional[LearningHistory] = None
    spaced_review_due: list[SpacedReviewItem] = Field(default_factory=list)
    adaptive_weights: AdaptiveWeights = Field(default_factory=AdaptiveWeights)
    study_guide_rules: StudyGuideRules = Field(default_factory=StudyGuideRules)


# --- Coaching Response Models ---

class CoachingNudge(BaseModel):
    """A coaching nudge from Gemini to be delivered to the user."""
    nudge_type: NudgeType
    technique: Optional[str] = None
    delivery: NudgeDelivery = NudgeDelivery.NOTIFICATION
    message: str
    audio_data: Optional[bytes] = None
    transcript: Optional[str] = None


class ScreenshotAnalysis(BaseModel):
    """Result of Gemini analyzing a screenshot."""
    detected_activity: DetectedActivity = DetectedActivity.OTHER
    detected_topic: Optional[str] = None
    study_phase: StudyPhase = StudyPhase.UNKNOWN
    coaching_nudge: Optional[CoachingNudge] = None
    raw_response: str = ""
