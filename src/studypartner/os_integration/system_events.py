"""OS Integration: macOS system event hooks (wake/sleep, app launch)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SystemEventWatcher:
    """Watch for macOS system events that affect study sessions.

    Events:
    - Wake from sleep → offer to start/resume session
    - Going to sleep → auto-end session
    - App launch/activate → context clue for topic detection
    """

    def __init__(
        self,
        on_wake: Optional[Callable] = None,
        on_sleep: Optional[Callable] = None,
        on_app_activate: Optional[Callable[[str], None]] = None,
    ):
        self._on_wake = on_wake
        self._on_sleep = on_sleep
        self._on_app_activate = on_app_activate

    def start(self):
        """Start listening for system events."""
        try:
            import AppKit

            workspace = AppKit.NSWorkspace.sharedWorkspace()
            center = workspace.notificationCenter()

            # Wake/sleep notifications
            center.addObserver_selector_name_object_(
                self,
                "handleWake:",
                AppKit.NSWorkspaceDidWakeNotification,
                None,
            )
            center.addObserver_selector_name_object_(
                self,
                "handleSleep:",
                AppKit.NSWorkspaceWillSleepNotification,
                None,
            )

            # App activation
            center.addObserver_selector_name_object_(
                self,
                "handleAppActivate:",
                AppKit.NSWorkspaceDidActivateApplicationNotification,
                None,
            )

            logger.info("System event watcher started")
        except ImportError:
            logger.warning("pyobjc not available — system event watcher disabled")
        except Exception as e:
            logger.error(f"Failed to start system event watcher: {e}")

    def handleWake_(self, notification):
        """Handle wake from sleep."""
        logger.info("System woke from sleep")
        if self._on_wake:
            self._on_wake()

    def handleSleep_(self, notification):
        """Handle going to sleep — auto-end session."""
        logger.info("System going to sleep — ending session")
        if self._on_sleep:
            self._on_sleep()

    def handleAppActivate_(self, notification):
        """Handle app activation — use as context clue."""
        try:
            import AppKit

            app_info = notification.userInfo()
            app_name = app_info.get("NSWorkspaceApplicationKey").localizedName()

            if app_name and self._on_app_activate:
                self._on_app_activate(app_name)
        except Exception:
            pass  # Non-critical


def get_frontmost_app() -> Optional[str]:
    """Get the name of the currently frontmost application."""
    try:
        import AppKit

        workspace = AppKit.NSWorkspace.sharedWorkspace()
        active_app = workspace.frontmostApplication()
        return active_app.localizedName() if active_app else None
    except ImportError:
        # Fallback to osascript
        import subprocess
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process '
                 'whose frontmost is true'],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip() or None
        except Exception:
            return None


def get_active_window_title() -> Optional[str]:
    """Get the title of the currently active window."""
    try:
        import subprocess
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get title of front window of '
             '(first application process whose frontmost is true)'],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() or None
    except Exception:
        return None
