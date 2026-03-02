"""macOS native notification delivery for coaching nudges."""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Emoji map for nudge types
NUDGE_ICONS = {
    "recall_prompt": "🧠",
    "phase_transition": "🔄",
    "anti_pattern": "⚠️",
    "time_based": "⏰",
    "encouragement": "🌟",
    "technique_tip": "📚",
}


def send_notification(
    title: str,
    body: str,
    subtitle: Optional[str] = None,
    sound: str = "Glass",
) -> bool:
    """Send a native macOS notification using osascript.

    Uses the display notification AppleScript command for reliable delivery
    with beautiful native notifications.
    """
    # Build the AppleScript
    script_parts = [f'display notification "{_escape(body)}"']
    script_parts.append(f'with title "{_escape(title)}"')
    if subtitle:
        script_parts.append(f'subtitle "{_escape(subtitle)}"')
    script_parts.append(f'sound name "{sound}"')

    script = " ".join(script_parts)

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        logger.info("🔔 Notification sent: %s — %s", title, body[:50])
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Notification timed out")
        return False
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
        return False


def send_coaching_nudge(
    nudge_type: str,
    message: str,
    technique: Optional[str] = None,
) -> bool:
    """Send a coaching nudge as a styled macOS notification.

    Uses rich formatting with appropriate emoji and sound based on
    the nudge type.
    """
    icon = NUDGE_ICONS.get(nudge_type, "💡")

    # Choose sound based on nudge type
    if nudge_type == "time_based":
        sound = "Purr"       # Gentle for break reminders
    elif nudge_type == "anti_pattern":
        sound = "Basso"      # Attention-getting for warnings
    elif nudge_type == "encouragement":
        sound = "Hero"       # Celebratory
    else:
        sound = "Glass"      # Default pleasant sound

    # Format the title
    title = f"{icon} StudyPartner"

    # Format subtitle with technique name if available
    subtitle = None
    if technique:
        technique_labels = {
            "feynman": "Feynman Technique",
            "brain_dump": "Brain Dump",
            "retrieval_practice": "Retrieval Practice",
            "interleaving": "Interleaving",
            "dual_coding": "Dual Coding",
            "worked_example": "Worked Example",
            "break": "Take a Break",
            "ai_as_tutor": "AI as Tutor",
        }
        subtitle = technique_labels.get(technique, technique.replace("_", " ").title())

    logger.info("💡 Coaching nudge [%s]: %s", nudge_type, message[:60])
    return send_notification(title, message, subtitle=subtitle, sound=sound)


def _escape(text: str) -> str:
    """Escape text for AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
