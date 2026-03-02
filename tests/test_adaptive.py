"""Tests for the adaptive engine."""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from studypartner.client.database import init_db, get_db
from studypartner.shared.constants import DB_PATH, DATA_DIR


class TestAdaptiveEngine:
    """Tests for the adaptive engine."""

    def setup_method(self):
        """Set up a temporary database for testing."""
        self._tmp_dir = tempfile.mkdtemp()
        self._original_db_path = DB_PATH
        self._original_data_dir = DATA_DIR

        # Patch paths to use temp dir
        import studypartner.shared.constants as constants
        from pathlib import Path
        constants.DATA_DIR = Path(self._tmp_dir)
        constants.DB_PATH = Path(self._tmp_dir) / "test.db"

        init_db()

    def teardown_method(self):
        """Clean up temp database."""
        import shutil
        import studypartner.shared.constants as constants
        constants.DATA_DIR = self._original_data_dir
        constants.DB_PATH = self._original_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_engine_initializes_defaults(self):
        """Adaptive engine should create default profile entries."""
        from studypartner.client.adaptive import AdaptiveEngine
        engine = AdaptiveEngine()

        with get_db() as conn:
            rows = conn.execute("SELECT * FROM adaptive_profile").fetchall()

        keys = [row["key"] for row in rows]
        assert "optimal_session_length_min" in keys
        assert "preferred_delivery" in keys
        assert "technique_affinity_feynman" in keys

    def test_record_positive_outcome(self):
        """Positive outcome should increase technique affinity."""
        from studypartner.client.adaptive import AdaptiveEngine
        engine = AdaptiveEngine()

        # Get initial score
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM adaptive_profile WHERE key='technique_affinity_feynman'"
            ).fetchone()
            initial_score = float(row["value"])

        # Record positive outcome
        engine.record_outcome(
            nudge_type="recall_prompt",
            technique="feynman",
            delivery="notification",
            user_response="acted_on",
        )

        # Score should increase
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM adaptive_profile WHERE key='technique_affinity_feynman'"
            ).fetchone()
            new_score = float(row["value"])

        assert new_score > initial_score

    def test_record_negative_outcome(self):
        """Negative outcome should decrease technique affinity."""
        from studypartner.client.adaptive import AdaptiveEngine
        engine = AdaptiveEngine()

        # Get initial score
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM adaptive_profile WHERE key='technique_affinity_feynman'"
            ).fetchone()
            initial_score = float(row["value"])

        # Record negative outcome
        engine.record_outcome(
            nudge_type="recall_prompt",
            technique="feynman",
            delivery="notification",
            user_response="dismissed",
        )

        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM adaptive_profile WHERE key='technique_affinity_feynman'"
            ).fetchone()
            new_score = float(row["value"])

        assert new_score < initial_score
