"""SQLite database operations for StudyPartner."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from studypartner.shared.constants import DATA_DIR, DB_PATH


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """Get a database connection with row factory."""
    ensure_data_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript("""
            -- Sessions
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TIMESTAMP NOT NULL,
                ended_at    TIMESTAMP,
                topic       TEXT,
                focus_min   REAL DEFAULT 0,
                break_min   REAL DEFAULT 0,
                phases      TEXT,
                trigger     TEXT DEFAULT 'manual'
            );

            -- Activity Snapshots
            CREATE TABLE IF NOT EXISTS activity_log (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        INTEGER REFERENCES sessions(id),
                timestamp         TIMESTAMP NOT NULL,
                screenshot_path   TEXT,
                detected_activity TEXT,
                detected_topic    TEXT,
                study_phase       TEXT,
                nudge_type        TEXT,
                nudge_text        TEXT,
                user_response     TEXT
            );

            -- Learning Topics
            CREATE TABLE IF NOT EXISTS topics (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT UNIQUE NOT NULL,
                first_seen      TIMESTAMP,
                last_seen       TIMESTAMP,
                total_hours     REAL DEFAULT 0,
                session_count   INTEGER DEFAULT 0,
                mastery_score   REAL DEFAULT 0,
                gaps            TEXT,
                last_retrieval  TIMESTAMP
            );

            -- Spaced Repetition Queue
            CREATE TABLE IF NOT EXISTS review_queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id        INTEGER REFERENCES topics(id),
                next_review     DATE NOT NULL,
                interval_days   INTEGER DEFAULT 1,
                ease_factor     REAL DEFAULT 2.5,
                review_count    INTEGER DEFAULT 0
            );

            -- Coaching Outcomes (feeds Adaptive Engine)
            CREATE TABLE IF NOT EXISTS coaching_outcomes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      INTEGER REFERENCES sessions(id),
                timestamp       TIMESTAMP NOT NULL,
                nudge_type      TEXT,
                technique       TEXT,
                delivery        TEXT,
                context_topic   TEXT,
                context_phase   TEXT,
                session_minute  INTEGER,
                time_of_day     TEXT,
                user_response   TEXT,
                response_time_s REAL,
                behavior_changed BOOLEAN,
                retrieval_score  REAL,
                focus_delta_min  REAL
            );

            -- Adaptive Profile (learned user preferences)
            CREATE TABLE IF NOT EXISTS adaptive_profile (
                key             TEXT PRIMARY KEY,
                value           TEXT,
                confidence      REAL DEFAULT 0.0,
                last_updated    TIMESTAMP,
                evidence_count  INTEGER DEFAULT 0
            );

            -- Detected Behavior Patterns
            CREATE TABLE IF NOT EXISTS behavior_patterns (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type    TEXT,
                pattern_data    TEXT,
                confidence      REAL DEFAULT 0.0,
                first_detected  TIMESTAMP,
                last_confirmed  TIMESTAMP,
                sample_count    INTEGER DEFAULT 0
            );
        """)


# --- Session Operations ---

def create_session(topic: Optional[str] = None, trigger: str = "manual") -> int:
    """Create a new session and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (started_at, topic, trigger) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), topic, trigger),
        )
        return cursor.lastrowid


def end_session(session_id: int, focus_min: float = 0, break_min: float = 0):
    """End a session."""
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at=?, focus_min=?, break_min=? WHERE id=?",
            (datetime.now().isoformat(), focus_min, break_min, session_id),
        )


def get_active_session() -> Optional[dict]:
    """Get the current active session (no ended_at)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_recent_sessions(limit: int = 10) -> list[dict]:
    """Get recent sessions formatted for display."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        started = datetime.fromisoformat(r["started_at"])
        results.append({
            "date": started.strftime("%Y-%m-%d %H:%M"),
            "topic": r["topic"] or "Auto-detected",
            "duration": f"{r['focus_min']:.0f} min",
            "focus": f"{r['focus_min']:.0f} min focus, {r['break_min']:.0f} min break",
        })
    return results


# --- Activity Log ---

def log_activity(
    session_id: int,
    screenshot_path: Optional[str] = None,
    detected_activity: Optional[str] = None,
    detected_topic: Optional[str] = None,
    study_phase: Optional[str] = None,
    nudge_type: Optional[str] = None,
    nudge_text: Optional[str] = None,
    user_response: Optional[str] = None,
):
    """Log an activity snapshot."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO activity_log
               (session_id, timestamp, screenshot_path, detected_activity,
                detected_topic, study_phase, nudge_type, nudge_text, user_response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id, datetime.now().isoformat(), screenshot_path,
                detected_activity, detected_topic, study_phase,
                nudge_type, nudge_text, user_response,
            ),
        )


# --- Coaching Outcomes ---

def log_coaching_outcome(
    session_id: int,
    nudge_type: str,
    technique: Optional[str],
    delivery: str,
    context_topic: Optional[str],
    context_phase: Optional[str],
    session_minute: int,
    user_response: str,
    response_time_s: Optional[float] = None,
    behavior_changed: Optional[bool] = None,
):
    """Log a coaching outcome for the adaptive engine."""
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    elif hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO coaching_outcomes
               (session_id, timestamp, nudge_type, technique, delivery,
                context_topic, context_phase, session_minute, time_of_day,
                user_response, response_time_s, behavior_changed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id, now.isoformat(), nudge_type, technique, delivery,
                context_topic, context_phase, session_minute, time_of_day,
                user_response, response_time_s, behavior_changed,
            ),
        )


# --- Topics ---

def upsert_topic(name: str, hours_delta: float = 0):
    """Create or update a topic."""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM topics WHERE name=?", (name,)).fetchone()
        now = datetime.now().isoformat()
        if existing:
            conn.execute(
                """UPDATE topics SET last_seen=?, total_hours=total_hours+?,
                   session_count=session_count+1 WHERE name=?""",
                (now, hours_delta, name),
            )
        else:
            conn.execute(
                "INSERT INTO topics (name, first_seen, last_seen, total_hours, session_count) "
                "VALUES (?, ?, ?, ?, 1)",
                (name, now, now, hours_delta),
            )


# --- Reset ---

def reset_all_data():
    """Delete all StudyPartner data."""
    import shutil
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
