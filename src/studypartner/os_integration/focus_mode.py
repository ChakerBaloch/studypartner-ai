"""OS Integration: macOS Focus Mode detection and auto-start."""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def is_focus_mode_active() -> bool:
    """Check if macOS Focus Mode (Do Not Disturb) is currently active.

    Uses the `defaults` command to check DND status.
    """
    try:
        # Check the DND state via assertions database
        result = subprocess.run(
            ["defaults", "-currentHost", "read", "com.apple.notificationcenterui",
             "doNotDisturb"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() == "1"
    except Exception:
        # Fallback: try reading the Focus state from ControlCenter
        try:
            result = subprocess.run(
                ["defaults", "read", "com.apple.controlcenter", "NSStatusItem Visible FocusModes"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip() == "1"
        except Exception:
            return False


def get_active_focus_mode() -> Optional[str]:
    """Get the name of the currently active Focus Mode.

    Returns the focus mode name (e.g., 'Study', 'Work') or None.
    """
    # macOS doesn't expose focus mode names easily via command line
    # For now, we just detect if any focus mode is active
    if is_focus_mode_active():
        return "Focus"
    return None


class FocusModeWatcher:
    """Watch for Focus Mode changes and trigger session auto-start/stop.

    Uses NSWorkspace notifications to detect DND state changes.
    """

    def __init__(self, on_focus_start=None, on_focus_end=None):
        self._on_focus_start = on_focus_start
        self._on_focus_end = on_focus_end
        self._was_focused = False

    def start(self):
        """Start watching for Focus Mode changes."""
        try:
            import AppKit
            import Foundation

            workspace = AppKit.NSWorkspace.sharedWorkspace()
            center = workspace.notificationCenter()

            # Watch for DND state changes in DistributedNotificationCenter
            dist_center = Foundation.NSDistributedNotificationCenter.defaultCenter()
            dist_center.addObserver_selector_name_object_(
                self,
                "focusChanged:",
                "com.apple.notificationcenterui.dndActivated",
                None,
            )
            dist_center.addObserver_selector_name_object_(
                self,
                "focusChanged:",
                "com.apple.notificationcenterui.dndDeactivated",
                None,
            )

            logger.info("Focus Mode watcher started")
        except ImportError:
            logger.warning("pyobjc not available — Focus Mode watcher disabled")
        except Exception as e:
            logger.error(f"Failed to start Focus Mode watcher: {e}")

    def focusChanged_(self, notification):
        """Handle Focus Mode state change notification."""
        is_focused = is_focus_mode_active()

        if is_focused and not self._was_focused:
            logger.info("Focus Mode activated — auto-starting session")
            if self._on_focus_start:
                self._on_focus_start()
        elif not is_focused and self._was_focused:
            logger.info("Focus Mode deactivated — pausing session")
            if self._on_focus_end:
                self._on_focus_end()

        self._was_focused = is_focused

    def check_once(self) -> bool:
        """One-shot check of Focus Mode status."""
        is_focused = is_focus_mode_active()
        if is_focused != self._was_focused:
            if is_focused and self._on_focus_start:
                self._on_focus_start()
            elif not is_focused and self._on_focus_end:
                self._on_focus_end()
            self._was_focused = is_focused
        return is_focused
