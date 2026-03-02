"""OS Integration: Native macOS notifications with interactive actions."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages native macOS notifications with interactive action buttons.

    Uses UNUserNotificationCenter for rich notifications with:
    - Action buttons (Let's go! / Later / Not now)
    - Grouped by session
    - Response tracking for adaptive engine
    """

    def __init__(self, on_response: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            on_response: Callback(nudge_id, action) when user responds to a notification.
        """
        self._on_response = on_response
        self._center = None
        self._delegate = None

    def setup(self):
        """Request notification permissions and configure categories."""
        try:
            import UserNotifications as UN

            self._center = UN.UNUserNotificationCenter.currentNotificationCenter()

            # Request permission
            def completion_handler(granted, error):
                if granted:
                    logger.info("Notification permission granted")
                else:
                    logger.warning(f"Notification permission denied: {error}")

            self._center.requestAuthorizationWithOptions_completionHandler_(
                UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound,
                completion_handler,
            )

            # Define notification categories with actions
            act_on = UN.UNNotificationAction.actionWithIdentifier_title_options_(
                "acted_on", "Let's go! ✅", UN.UNNotificationActionOptionNone,
            )
            snooze = UN.UNNotificationAction.actionWithIdentifier_title_options_(
                "snoozed", "Later ⏰", UN.UNNotificationActionOptionNone,
            )
            dismiss = UN.UNNotificationAction.actionWithIdentifier_title_options_(
                "dismissed", "Not now", UN.UNNotificationActionOptionNone,
            )

            coaching_category = UN.UNNotificationCategory.categoryWithIdentifier_actions_intentIdentifiers_options_(
                "coaching",
                [act_on, snooze, dismiss],
                [],
                UN.UNNotificationCategoryOptionNone,
            )

            self._center.setNotificationCategories_({coaching_category})

            logger.info("Notification manager set up with interactive categories")

        except ImportError:
            logger.warning("UserNotifications framework not available")
        except Exception as e:
            logger.error(f"Failed to set up notifications: {e}")

    def send_coaching_notification(
        self,
        nudge_id: str,
        title: str,
        body: str,
        subtitle: Optional[str] = None,
    ):
        """Send an interactive coaching notification."""
        try:
            import UserNotifications as UN
            import Foundation

            content = UN.UNMutableNotificationContent.alloc().init()
            content.setTitle_(title)
            content.setBody_(body)
            if subtitle:
                content.setSubtitle_(subtitle)
            content.setSound_(UN.UNNotificationSound.defaultSound())
            content.setCategoryIdentifier_("coaching")
            content.setUserInfo_({"nudge_id": nudge_id})

            # Create trigger (immediate)
            trigger = UN.UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(
                0.1, False
            )

            request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(
                nudge_id, content, trigger
            )

            def completion(error):
                if error:
                    logger.error(f"Failed to send notification: {error}")
                else:
                    logger.info(f"Coaching notification sent: {nudge_id}")

            self._center.addNotificationRequest_withCompletionHandler_(
                request, completion
            )

        except ImportError:
            # Fallback to simple notification
            from studypartner.client.nudge import send_notification
            send_notification(title, body, subtitle=subtitle)
        except Exception as e:
            logger.error(f"Failed to send coaching notification: {e}")
            from studypartner.client.nudge import send_notification
            send_notification(title, body, subtitle=subtitle)
