"""Study guide rules engine — detects study phases and anti-patterns."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from studypartner.shared.constants import (
    AI_CHAT_KEYWORDS,
    CODING_KEYWORDS,
)
from studypartner.shared.models import (
    AdaptiveWeights,
    DetectedActivity,
    NudgeType,
    StudyPhase,
)

logger = logging.getLogger(__name__)


@dataclass
class StudyRule:
    """A single study technique rule."""
    name: str
    nudge_type: NudgeType
    technique: str
    condition_description: str
    message_template: str


# --- Phase Detection ---

def detect_study_phase(
    activity: DetectedActivity,
    session_minutes: float,
    topic_session_count: int = 0,
) -> StudyPhase:
    """Detect the current study phase based on activity and context.

    Phases:
    - ACQUIRE: User is reading/watching new material
    - PROCESS: User is actively engaging (coding, writing, problem-solving)
    - CONSOLIDATE: User is testing/reviewing (quizzing, retrieval practice)
    """
    if activity == DetectedActivity.READING:
        if session_minutes < 30:
            return StudyPhase.ACQUIRE
        else:
            # Been reading too long — should transition to PROCESS
            return StudyPhase.ACQUIRE  # Still acquiring, but nudge for transition

    elif activity in (DetectedActivity.CODING, DetectedActivity.OTHER):
        if topic_session_count <= 1:
            return StudyPhase.ACQUIRE  # First session — still acquiring
        return StudyPhase.PROCESS

    elif activity == DetectedActivity.BROWSING:
        return StudyPhase.ACQUIRE  # Researching

    return StudyPhase.UNKNOWN


# --- Anti-Pattern Detection ---

@dataclass
class AntiPatternResult:
    """Result of anti-pattern detection."""
    detected: bool
    pattern_name: str
    nudge_type: NudgeType
    technique: str
    message: str


def check_anti_patterns(
    activity: DetectedActivity,
    study_phase: StudyPhase,
    session_minutes: float,
    minutes_since_last_break: float,
    minutes_in_current_activity: float,
    adaptive_weights: Optional[AdaptiveWeights] = None,
) -> Optional[AntiPatternResult]:
    """Check for study anti-patterns and return a coaching nudge if detected.

    Checks are ordered by priority (most impactful first).
    """
    weights = adaptive_weights or AdaptiveWeights()

    # Skip if in warm-up period
    if session_minutes < weights.nudge_delay_start_min:
        return None

    # 1. No break too long → enforce restorative break
    break_threshold = weights.optimal_session_length_min
    if minutes_since_last_break >= break_threshold:
        return AntiPatternResult(
            detected=True,
            pattern_name="no_break",
            nudge_type=NudgeType.TIME_BASED,
            technique="break",
            message=(
                f"You've been going for {int(minutes_since_last_break)} minutes — "
                f"great focus! Time for a restorative break. "
                f"Step away from the screen for 10 minutes. "
                f"Walk, stretch, or just sit quietly. No phone!"
            ),
        )

    # 2. Passive reading too long → prompt brain dump
    if (
        activity == DetectedActivity.READING
        and minutes_in_current_activity >= 30
    ):
        return AntiPatternResult(
            detected=True,
            pattern_name="passive_reading",
            nudge_type=NudgeType.PHASE_TRANSITION,
            technique="brain_dump",
            message=(
                f"You've been reading for {int(minutes_in_current_activity)} minutes. "
                f"Time to test what stuck! Close your notes and write down "
                f"everything you remember. Don't peek — the struggle is the learning."
            ),
        )

    # 3. AI copy-paste pattern → warn
    if activity == DetectedActivity.AI_CHAT:
        return AntiPatternResult(
            detected=True,
            pattern_name="ai_copy_paste",
            nudge_type=NudgeType.ANTI_PATTERN,
            technique="ai_as_tutor",
            message=(
                "I see you're using an AI assistant. That's fine — but make sure "
                "you're using it as a tutor, not a crutch. Instead of copying code, "
                "ask the AI to EXPLAIN the concept, then try writing it yourself."
            ),
        )

    # 4. Same activity too long → suggest interleaving
    if minutes_in_current_activity >= 20 and activity == DetectedActivity.CODING:
        # Check if interleaving has high affinity for this user
        interleave_score = weights.preferred_techniques.get("interleaving", 0.5)
        if interleave_score >= 0.4:
            return AntiPatternResult(
                detected=True,
                pattern_name="blocked_practice",
                nudge_type=NudgeType.PHASE_TRANSITION,
                technique="interleaving",
                message=(
                    f"You've been on the same type of problem for "
                    f"{int(minutes_in_current_activity)} minutes. "
                    f"Try switching to a different but related topic for 15 minutes. "
                    f"Interleaving helps your brain build stronger connections."
                ),
            )

    # 5. Fatigue onset → lighten coaching
    if session_minutes >= weights.fatigue_onset_min:
        return AntiPatternResult(
            detected=True,
            pattern_name="fatigue",
            nudge_type=NudgeType.TIME_BASED,
            technique="break",
            message=(
                f"You've been studying for {int(session_minutes)} minutes — "
                f"you're probably hitting diminishing returns. Consider wrapping up "
                f"this session with a quick retrieval check, then take a real break."
            ),
        )

    return None


# --- Return-After-Absence Detection ---

def check_return_after_absence(hours_since_last_session: float) -> Optional[AntiPatternResult]:
    """Check if user is returning after a long absence (24h+)."""
    if hours_since_last_session >= 24:
        days = int(hours_since_last_session / 24)
        return AntiPatternResult(
            detected=True,
            pattern_name="return_after_absence",
            nudge_type=NudgeType.RECALL_PROMPT,
            technique="retrieval_practice",
            message=(
                f"Welcome back! It's been {days} day(s) since your last session. "
                f"Before diving into new material, let's do a quick retrieval check. "
                f"Can you recall the key points from your last session?"
            ),
        )
    return None


# --- Technique Suggestion ---

def suggest_technique(
    study_phase: StudyPhase,
    adaptive_weights: Optional[AdaptiveWeights] = None,
) -> Optional[tuple[str, str]]:
    """Suggest a study technique based on current phase and user preferences.

    Returns (technique_name, suggestion_message) or None.
    """
    weights = adaptive_weights or AdaptiveWeights()
    prefs = weights.preferred_techniques

    if study_phase == StudyPhase.ACQUIRE:
        # Check which acquisition techniques score highest
        candidates = {
            "worked_example": (
                prefs.get("worked_example", 0.5),
                "Try finding a worked example of this problem before solving it yourself. "
                "Study the step-by-step solution, then attempt a similar problem."
            ),
            "dual_coding": (
                prefs.get("dual_coding", 0.5),
                "While you're reading, try drawing a diagram of what you're learning. "
                "Engaging both verbal and visual channels makes memory much stronger."
            ),
        }
        best = max(candidates.items(), key=lambda x: x[1][0])
        return (best[0], best[1][1])

    elif study_phase == StudyPhase.PROCESS:
        candidates = {
            "feynman": (
                prefs.get("feynman", 0.5),
                "Try the Feynman technique: explain what you just learned as if "
                "teaching it to a beginner. Where you stumble is where you need to study more."
            ),
            "brain_dump": (
                prefs.get("brain_dump", 0.5),
                "Time for a brain dump! Close everything and write down all you remember. "
                "The struggle to recall is what builds permanent memory."
            ),
            "interleaving": (
                prefs.get("interleaving", 0.5),
                "Consider switching to a related but different topic for 15 minutes. "
                "Interleaving helps you learn to distinguish between concepts."
            ),
        }
        best = max(candidates.items(), key=lambda x: x[1][0])
        return (best[0], best[1][1])

    elif study_phase == StudyPhase.CONSOLIDATE:
        return (
            "retrieval_practice",
            "Let's lock this in! I'll quiz you on what you've covered. "
            "Don't check answers until the end — delayed feedback strengthens memory."
        )

    return None
