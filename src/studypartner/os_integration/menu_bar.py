"""OS Integration: Menu bar agent for macOS using pyobjc."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MenuBarAgent:
    """macOS menu bar status item — always-on, zero-chrome.

    Provides:
    - Status icon in the menu bar
    - Dropdown menu with session info + controls
    - No Dock icon, no window
    """

    def __init__(self):
        self._status_item = None
        self._app = None
        self._running = False
        self._session_label = None
        self._callbacks: dict[str, Callable] = {}

    def register_callback(self, action: str, callback: Callable):
        """Register a callback for menu actions."""
        self._callbacks[action] = callback

    def start(self):
        """Start the menu bar agent in a background thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        logger.info("Menu bar agent started")

    def _run(self):
        """Run the macOS event loop for the menu bar."""
        try:
            import AppKit
            import objc

            # Create the application (don't show in Dock)
            self._app = AppKit.NSApplication.sharedApplication()
            self._app.setActivationPolicy_(
                AppKit.NSApplicationActivationPolicyAccessory  # No Dock icon
            )

            # Create status bar item
            status_bar = AppKit.NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(
                AppKit.NSVariableStatusItemLength
            )

            # Set the icon (brain emoji as text for now)
            button = self._status_item.button()
            button.setTitle_("🧠")
            button.setToolTip_("StudyPartner AI")

            # Build the menu
            menu = AppKit.NSMenu.alloc().init()

            # Session status (will be updated dynamically)
            self._session_label = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No active session", None, ""
            )
            self._session_label.setEnabled_(False)
            menu.addItem_(self._session_label)

            menu.addItem_(AppKit.NSMenuItem.separatorItem())

            # Start session
            start_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Start Session", "startSession:", "s"
            )
            start_item.setTarget_(self)
            menu.addItem_(start_item)

            # Stop session
            stop_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Stop Session", "stopSession:", "x"
            )
            stop_item.setTarget_(self)
            menu.addItem_(stop_item)

            menu.addItem_(AppKit.NSMenuItem.separatorItem())

            # Quit
            quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit StudyPartner", "quitApp:", "q"
            )
            quit_item.setTarget_(self)
            menu.addItem_(quit_item)

            self._status_item.setMenu_(menu)
            self._running = True

            # Run the event loop
            self._app.run()

        except ImportError:
            logger.warning("pyobjc AppKit not available — menu bar disabled")
        except Exception as e:
            logger.error(f"Menu bar agent failed: {e}")

    def update_status(self, text: str, icon: str = "🧠"):
        """Update the menu bar status display."""
        if self._status_item and self._session_label:
            try:
                import AppKit

                # Update on main thread
                def update():
                    self._status_item.button().setTitle_(icon)
                    self._session_label.setTitle_(text)

                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(update)
            except Exception as e:
                logger.error(f"Failed to update menu bar: {e}")

    def startSession_(self, sender):
        """Handle Start Session menu click."""
        if "start" in self._callbacks:
            threading.Thread(target=self._callbacks["start"], daemon=True).start()

    def stopSession_(self, sender):
        """Handle Stop Session menu click."""
        if "stop" in self._callbacks:
            self._callbacks["stop"]()

    def quitApp_(self, sender):
        """Handle Quit menu click."""
        if "quit" in self._callbacks:
            self._callbacks["quit"]()
        if self._app:
            self._app.terminate_(sender)
