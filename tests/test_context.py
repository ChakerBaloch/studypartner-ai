"""Tests for context composer."""

import os
import sys

# Ensure the source is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from studypartner.shared.models import (
    AdaptiveWeights,
    ContextPacket,
    NudgeDelivery,
    SessionContext,
    StudyPhase,
)


class TestContextPacket:
    def test_default_context_packet(self):
        """Default context packet should have sane defaults."""
        pkt = ContextPacket()
        assert pkt.session_context.session_duration_minutes == 0
        assert pkt.session_context.study_phase == StudyPhase.UNKNOWN
        assert pkt.adaptive_weights.optimal_session_length_min == 45
        assert pkt.adaptive_weights.tone_preference == "casual"

    def test_adaptive_weights_defaults(self):
        """Adaptive weights should have all techniques at 0.5."""
        weights = AdaptiveWeights()
        assert weights.preferred_techniques["feynman"] == 0.5
        assert weights.preferred_techniques["brain_dump"] == 0.5
        assert weights.preferred_delivery == NudgeDelivery.NOTIFICATION

    def test_context_packet_serialization(self):
        """Context packet should serialize to JSON and back."""
        pkt = ContextPacket(
            session_context=SessionContext(
                current_topic="Bash Scripting",
                session_duration_minutes=30,
                study_phase=StudyPhase.PROCESS,
            ),
            adaptive_weights=AdaptiveWeights(
                preferred_techniques={"feynman": 0.8},
                optimal_session_length_min=50,
            ),
        )

        json_str = pkt.model_dump_json()
        restored = ContextPacket.model_validate_json(json_str)

        assert restored.session_context.current_topic == "Bash Scripting"
        assert restored.session_context.session_duration_minutes == 30
        assert restored.adaptive_weights.preferred_techniques["feynman"] == 0.8
        assert restored.adaptive_weights.optimal_session_length_min == 50
