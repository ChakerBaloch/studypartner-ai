"""Native macOS notification nudges via pyobjc."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_notification(
    title: str,
    message: str,
    subtitle: Optional[str] = None,
    sound: bool = True,
) -> bool:
    """Send a macOS native notification.

    Uses NSUserNotification (legacy) or UNUserNotificationCenter.
    Falls back to osascript if pyobjc is unavailable.
    """
    try:
        return _send_with_pyobjc(title, message, subtitle, sound)
    except ImportError:
        return _send_with_osascript(title, message, subtitle, sound)
    except Exception as e:
        logger.error(f"pyobjc notification failed: {e}")
        return _send_with_osascript(title, message, subtitle, sound)


def _send_with_pyobjc(
    title: str,
    message: str,
    subtitle: Optional[str],
    sound: bool,
) -> bool:
    """Send notification using pyobjc NSUserNotification."""
    from Foundation import NSUserNotification, NSUserNotificationCenter

    notification = NSUserNotification.alloc().init()
    notification.setTitle_(title)
    notification.setInformativeText_(message)
    if subtitle:
        notification.setSubtitle_(subtitle)
    if sound:
        notification.setSoundName_("default")

    center = NSUserNotificationCenter.defaultUserNotificationCenter()
    center.deliverNotification_(notification)

    logger.info(f"Sent notification: {title}")
    return True


def _send_with_osascript(
    title: str,
    message: str,
    subtitle: Optional[str],
    sound: bool,
) -> bool:
    """Fallback: send notification using osascript."""
    import subprocess

    subtitle_part = f'subtitle "{subtitle}"' if subtitle else ""
    sound_part = 'sound name "default"' if sound else ""

    script = (
        f'display notification "{message}" '
        f'with title "{title}" {subtitle_part} {sound_part}'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        logger.info(f"Sent notification via osascript: {title}")
        return True
    except Exception as e:
        logger.error(f"osascript notification failed: {e}")
        return False


def send_coaching_nudge(
    nudge_type: str,
    message: str,
    technique: Optional[str] = None,
):
    """Send a coaching nudge as a native notification.

    Maps nudge types to emoji headers.
    """
    emoji_map = {
        "time_based": "⏰",
        "phase_transition": "🔄",
        "anti_pattern": "⚠️",
        "recall_prompt": "🎯",
        "progress": "📊",
        "scheduled_review": "🗓️",
    }

    emoji = emoji_map.get(nudge_type, "🧠")
    title = f"{emoji} StudyPartner"
    subtitle = technique.replace("_", " ").title() if technique else None

    send_notification(title, message, subtitle=subtitle)
