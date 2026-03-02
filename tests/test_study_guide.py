"""Tests for the study guide rules engine."""

from studypartner.shared.study_guide import (
    check_anti_patterns,
    check_return_after_absence,
    detect_study_phase,
    suggest_technique,
)
from studypartner.shared.models import (
    AdaptiveWeights,
    DetectedActivity,
    NudgeType,
    StudyPhase,
)


class TestPhaseDetection:
    def test_reading_is_acquire(self):
        result = detect_study_phase(DetectedActivity.READING, session_minutes=15)
        assert result == StudyPhase.ACQUIRE

    def test_coding_first_session_is_acquire(self):
        result = detect_study_phase(DetectedActivity.CODING, session_minutes=10, topic_session_count=0)
        assert result == StudyPhase.ACQUIRE

    def test_coding_later_sessions_is_process(self):
        result = detect_study_phase(DetectedActivity.CODING, session_minutes=30, topic_session_count=3)
        assert result == StudyPhase.PROCESS

    def test_browsing_is_acquire(self):
        result = detect_study_phase(DetectedActivity.BROWSING, session_minutes=5)
        assert result == StudyPhase.ACQUIRE

    def test_idle_is_unknown(self):
        result = detect_study_phase(DetectedActivity.IDLE, session_minutes=5)
        assert result == StudyPhase.UNKNOWN


class TestAntiPatterns:
    def test_no_break_too_long(self):
        result = check_anti_patterns(
            activity=DetectedActivity.CODING,
            study_phase=StudyPhase.PROCESS,
            session_minutes=50,
            minutes_since_last_break=50,
            minutes_in_current_activity=50,
        )
        assert result is not None
        assert result.pattern_name == "no_break"
        assert result.nudge_type == NudgeType.TIME_BASED

    def test_passive_reading(self):
        result = check_anti_patterns(
            activity=DetectedActivity.READING,
            study_phase=StudyPhase.ACQUIRE,
            session_minutes=35,
            minutes_since_last_break=35,
            minutes_in_current_activity=35,
            adaptive_weights=AdaptiveWeights(optimal_session_length_min=60),
        )
        assert result is not None
        assert result.pattern_name == "passive_reading"

    def test_ai_copy_paste(self):
        result = check_anti_patterns(
            activity=DetectedActivity.AI_CHAT,
            study_phase=StudyPhase.PROCESS,
            session_minutes=20,
            minutes_since_last_break=20,
            minutes_in_current_activity=10,
            adaptive_weights=AdaptiveWeights(optimal_session_length_min=60),
        )
        assert result is not None
        assert result.pattern_name == "ai_copy_paste"

    def test_no_pattern_early_session(self):
        """No anti-patterns should fire during warm-up period."""
        result = check_anti_patterns(
            activity=DetectedActivity.READING,
            study_phase=StudyPhase.ACQUIRE,
            session_minutes=2,
            minutes_since_last_break=2,
            minutes_in_current_activity=2,
            adaptive_weights=AdaptiveWeights(nudge_delay_start_min=5),
        )
        assert result is None

    def test_no_pattern_normal_session(self):
        """No patterns in a normal, healthy session."""
        result = check_anti_patterns(
            activity=DetectedActivity.CODING,
            study_phase=StudyPhase.PROCESS,
            session_minutes=15,
            minutes_since_last_break=15,
            minutes_in_current_activity=10,
        )
        assert result is None


class TestReturnAfterAbsence:
    def test_return_after_days(self):
        result = check_return_after_absence(hours_since_last_session=48)
        assert result is not None
        assert result.pattern_name == "return_after_absence"
        assert "2 day" in result.message

    def test_no_return_same_day(self):
        result = check_return_after_absence(hours_since_last_session=4)
        assert result is None


class TestTechniqueSuggestion:
    def test_acquire_phase(self):
        result = suggest_technique(StudyPhase.ACQUIRE)
        assert result is not None
        technique_name, message = result
        assert technique_name in ("worked_example", "dual_coding")

    def test_process_phase(self):
        result = suggest_technique(StudyPhase.PROCESS)
        assert result is not None
        technique_name, message = result
        assert technique_name in ("feynman", "brain_dump", "interleaving")

    def test_consolidate_phase(self):
        result = suggest_technique(StudyPhase.CONSOLIDATE)
        assert result is not None
        assert result[0] == "retrieval_practice"

    def test_adaptive_preference(self):
        """Should select the technique with highest affinity."""
        weights = AdaptiveWeights(
            preferred_techniques={"feynman": 0.9, "brain_dump": 0.2, "interleaving": 0.3}
        )
        result = suggest_technique(StudyPhase.PROCESS, adaptive_weights=weights)
        assert result is not None
        assert result[0] == "feynman"
