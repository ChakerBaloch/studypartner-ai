"""Session manager — orchestrates the capture → analyze → nudge loop."""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from typing import Optional

from rich.console import Console
from rich.table import Table

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
from studypartner.client.logging_config import setup_logging
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


def _print_banner(config: Config, topic: Optional[str]):
    """Print a startup banner showing configuration."""
    console.print()
    table = Table(title="🧠 StudyPartner AI — Session Starting", border_style="green")
    table.add_column("Setting", style="dim")
    table.add_column("Value", style="bold")
    table.add_row("Backend", config.backend_url or "[red]Not set[/red]")
    table.add_row("Topic", topic or "Auto-detect")
    table.add_row("Capture interval", f"{config.capture_interval_seconds}s")
    table.add_row("Pomodoro length", f"{config.default_pomodoro_minutes} min")
    table.add_row("Voice coaching", "✅ Enabled" if config.enable_voice_coaching else "❌ Disabled")
    table.add_row("Screenshots", str(config.auto_delete_screenshots_days) + " day retention")
    table.add_row("Log file", str(logging.getLogger("studypartner").handlers[0].baseFilename)
                   if logging.getLogger("studypartner").handlers else "Console only")
    console.print(table)
    console.print()


def start_session(topic: Optional[str] = None, verbose: bool = False):
    """Start a new study session with the capture → analyze → nudge loop."""
    global _running, _session_id, _start_time

    # Set up logging
    setup_logging(verbose=verbose)

    # Initialize database
    init_db()
    logger.info("Database initialized")

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

    _print_banner(config, topic)

    logger.info("━━━ Session #%d started ━━━", _session_id)
    logger.info("Topic: %s", topic or "Auto-detect")
    logger.info("Backend: %s", config.backend_url)

    send_notification(
        "🧠 StudyPartner Active",
        f"Study session started! Topic: {topic or 'Auto-detect'}",
        subtitle="Watching your screen now...",
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

    cycle_count = 0
    current_phase = StudyPhase.UNKNOWN
    detected_topic = topic

    console.print(
        "[dim]Pipeline: Screenshot → Privacy Gate → Cloud Run → Gemini → Coaching[/dim]"
    )
    console.print(
        f"[dim]Capturing every {config.capture_interval_seconds}s. Press Ctrl+C to stop.[/dim]\n"
    )

    while _running:
        try:
            cycle_count += 1
            elapsed_min = (time.time() - _start_time) / 60.0

            # 1. Capture screenshot
            logger.info("🔄 Cycle %d │ Elapsed: %.1f min", cycle_count, elapsed_min)
            logger.info("📸 Capturing screenshot...")

            jpeg_bytes = capture_screenshot()
            if jpeg_bytes is None:
                logger.warning("❌ Screenshot capture failed, retrying in %ds", config.capture_interval_seconds)
                await asyncio.sleep(config.capture_interval_seconds)
                continue

            size_kb = len(jpeg_bytes) / 1024
            logger.info("📸 Screenshot captured: %.1f KB", size_kb)

            # 2. Privacy Gate
            logger.info("🔒 Running Privacy Gate...")
            safe_bytes = preprocess_screenshot(jpeg_bytes)
            if safe_bytes is None:
                logger.info("🔒 Screenshot filtered (sensitive content detected)")
                log_activity(
                    session_id=_session_id,
                    detected_activity="filtered",
                    study_phase=current_phase.value,
                )
                await asyncio.sleep(config.capture_interval_seconds)
                continue
            logger.info("🔒 Privacy Gate: ✅ passed")

            # 3. Save screenshot locally
            screenshot_path = save_screenshot(jpeg_bytes)
            logger.debug("💾 Screenshot saved: %s", screenshot_path)

            # 4. Build context packet
            context = build_context_packet(
                current_topic=detected_topic,
                session_duration_min=elapsed_min,
                study_phase=current_phase,
                pomodoro_count=0,
            )
            logger.info("📋 Context built │ Topic: %s │ Phase: %s",
                         detected_topic or "unknown", current_phase.value)

            # 5. Send to backend for analysis
            logger.info("☁️  Sending to Cloud Run (%s)...", config.backend_url)
            analysis = await analyze_screenshot(safe_bytes, context, config)

            if analysis:
                logger.info("✅ Gemini response received")
                logger.info("   Activity: %s │ Topic: %s │ Phase: %s",
                             analysis.detected_activity.value,
                             analysis.detected_topic or "—",
                             analysis.study_phase.value)

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
                logger.debug("💾 Activity logged to database")

                # 6. Deliver coaching nudge if any
                if analysis.coaching_nudge:
                    nudge = analysis.coaching_nudge
                    logger.info("💡 Coaching nudge: [%s] %s",
                                 nudge.nudge_type.value, nudge.message[:60])
                    send_coaching_nudge(
                        nudge_type=nudge.nudge_type.value,
                        message=nudge.message,
                        technique=nudge.technique,
                    )
                    console.print(
                        f"  [cyan]💡 {nudge.message}[/cyan]"
                    )
                else:
                    logger.info("💡 No coaching nudge this cycle (you're doing great!)")
            else:
                logger.warning("⚠️  No response from backend")

            logger.info("⏳ Next capture in %ds...\n", config.capture_interval_seconds)

            # Wait for next capture
            await asyncio.sleep(config.capture_interval_seconds)

        except Exception as e:
            logger.error("❌ Error in capture loop: %s", e, exc_info=True)
            await asyncio.sleep(config.capture_interval_seconds)


def stop_session():
    """Stop the current session."""
    global _running, _session_id, _start_time

    _running = False

    if _session_id and _start_time:
        elapsed_min = (time.time() - _start_time) / 60.0
        end_session(_session_id, focus_min=elapsed_min)

        logger.info("━━━ Session #%d ended ━━━", _session_id)
        logger.info("Duration: %.1f minutes", elapsed_min)

        console.print(
            f"\n[green]✅ Session ended.[/green]\n"
            f"   Duration: {elapsed_min:.1f} minutes\n"
        )
        send_notification(
            "🧠 Session Complete",
            f"Great work! {elapsed_min:.1f} minutes of studying. 🎉",
            subtitle="Take a well-deserved break!",
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
