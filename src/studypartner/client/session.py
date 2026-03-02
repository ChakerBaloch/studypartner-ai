"""Session manager — orchestrates the capture → analyze → nudge loop."""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from typing import Optional

from rich.console import Console

from studypartner.client.capture import capture_screenshot, save_screenshot, cleanup_old_screenshots
from studypartner.client.config import Config
from studypartner.client.context import build_context_packet
from studypartner.client.database import (
    create_session,
    end_session,
    get_active_session,
    init_db,
    log_activity,
    upsert_topic,
)
from studypartner.client.nudge import send_coaching_nudge, send_notification
from studypartner.client.preprocessor import preprocess_screenshot
from studypartner.client.ws_client import analyze_screenshot
from studypartner.shared.models import StudyPhase

logger = logging.getLogger(__name__)
console = Console()

# Global session state
_running = False
_session_id: Optional[int] = None
_start_time: Optional[float] = None


def start_session(topic: Optional[str] = None):
    """Start a new study session with the capture → analyze → nudge loop."""
    global _running, _session_id, _start_time

    # Initialize database
    init_db()

    config = Config.load()
    if not config.is_configured:
        console.print(
            "[yellow]⚠️  StudyPartner not configured yet.[/yellow]\n"
            "Run [bold]studypartner setup[/bold] first to configure your backend."
        )
        return

    # Check for existing active session
    active = get_active_session()
    if active:
        console.print(
            f"[yellow]Session already active (started {active['started_at']}). "
            f"Run 'studypartner stop' first.[/yellow]"
        )
        return

    # Create new session
    _session_id = create_session(topic=topic)
    _start_time = time.time()
    _running = True

    if topic:
        upsert_topic(topic)

    # Clean up old screenshots
    cleanup_old_screenshots(max_age_days=config.auto_delete_screenshots_days)

    console.print(f"[green]✅ Session started (ID: {_session_id})[/green]")
    send_notification(
        "🧠 StudyPartner",
        f"Study session started! Topic: {topic or 'Auto-detect'}",
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        stop_session()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the main loop
    try:
        asyncio.run(_capture_loop(config, topic))
    except KeyboardInterrupt:
        stop_session()


async def _capture_loop(config: Config, topic: Optional[str] = None):
    """Main capture → analyze → nudge loop."""
    global _running

    pomodoro_count = 0
    current_phase = StudyPhase.UNKNOWN
    detected_topic = topic

    console.print(
        f"[dim]Capturing every {config.capture_interval_seconds}s. Press Ctrl+C to stop.[/dim]"
    )

    while _running:
        try:
            elapsed_min = (time.time() - _start_time) / 60.0

            # 1. Capture screenshot
            jpeg_bytes = capture_screenshot()
            if jpeg_bytes is None:
                logger.warning("Screenshot capture failed, retrying...")
                await asyncio.sleep(config.capture_interval_seconds)
                continue

            # 2. Privacy Gate
            safe_bytes = preprocess_screenshot(jpeg_bytes)
            if safe_bytes is None:
                logger.info("Screenshot filtered by Privacy Gate")
                log_activity(
                    session_id=_session_id,
                    detected_activity="filtered",
                    study_phase=current_phase.value,
                )
                await asyncio.sleep(config.capture_interval_seconds)
                continue

            # 3. Save screenshot locally
            screenshot_path = save_screenshot(jpeg_bytes)

            # 4. Build context packet
            context = build_context_packet(
                current_topic=detected_topic,
                session_duration_min=elapsed_min,
                study_phase=current_phase,
                pomodoro_count=pomodoro_count,
            )

            # 5. Send to backend for analysis
            analysis = await analyze_screenshot(safe_bytes, context, config)

            if analysis:
                # Update detected values
                if analysis.detected_topic:
                    detected_topic = analysis.detected_topic
                if analysis.study_phase != StudyPhase.UNKNOWN:
                    current_phase = analysis.study_phase

                # Log activity
                log_activity(
                    session_id=_session_id,
                    screenshot_path=str(screenshot_path),
                    detected_activity=analysis.detected_activity.value,
                    detected_topic=analysis.detected_topic,
                    study_phase=analysis.study_phase.value,
                    nudge_type=analysis.coaching_nudge.nudge_type.value if analysis.coaching_nudge else None,
                    nudge_text=analysis.coaching_nudge.message if analysis.coaching_nudge else None,
                )

                # 6. Deliver coaching nudge if any
                if analysis.coaching_nudge:
                    nudge = analysis.coaching_nudge
                    send_coaching_nudge(
                        nudge_type=nudge.nudge_type.value,
                        message=nudge.message,
                        technique=nudge.technique,
                    )
                    console.print(
                        f"  [cyan]💡 {nudge.message[:80]}...[/cyan]"
                        if len(nudge.message) > 80
                        else f"  [cyan]💡 {nudge.message}[/cyan]"
                    )

            # Wait for next capture
            await asyncio.sleep(config.capture_interval_seconds)

        except Exception as e:
            logger.error(f"Error in capture loop: {e}")
            await asyncio.sleep(config.capture_interval_seconds)


def stop_session():
    """Stop the current session."""
    global _running, _session_id, _start_time

    _running = False

    if _session_id and _start_time:
        elapsed_min = (time.time() - _start_time) / 60.0
        end_session(_session_id, focus_min=elapsed_min)

        console.print(
            f"\n[green]✅ Session ended.[/green]\n"
            f"   Duration: {elapsed_min:.1f} minutes\n"
        )
        send_notification(
            "🧠 StudyPartner",
            f"Session ended! {elapsed_min:.1f} minutes of studying. Great work! 🎉",
        )

    _session_id = None
    _start_time = None


def get_status() -> Optional[str]:
    """Get current session status string."""
    if not _running or not _start_time:
        return None

    elapsed = (time.time() - _start_time) / 60.0
    return (
        f"🟢 Active session\n"
        f"   Duration: {elapsed:.1f} minutes\n"
        f"   Session ID: {_session_id}"
    )
