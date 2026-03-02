"""Privacy Gate — filter sensitive content from screenshots before sending to cloud."""

from __future__ import annotations

import logging
import re
from typing import Optional

from studypartner.shared.constants import EXCLUDED_APPS

logger = logging.getLogger(__name__)


def get_active_windows() -> list[dict]:
    """Get list of active windows with their app names and bounds.

    Returns a list of dicts with keys: app_name, window_title, bounds.
    """
    try:
        import Quartz

        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )

        windows = []
        for w in window_list:
            app_name = w.get("kCGWindowOwnerName", "")
            window_title = w.get("kCGWindowName", "")
            bounds = w.get("kCGWindowBounds", {})
            windows.append({
                "app_name": app_name,
                "window_title": window_title,
                "bounds": bounds,
            })
        return windows
    except ImportError:
        logger.warning("pyobjc not available — cannot get window list")
        return []


def has_sensitive_window(windows: list[dict]) -> bool:
    """Check if any currently visible window is in the exclusion list."""
    for w in windows:
        app_name = w.get("app_name", "").lower()
        for excluded in EXCLUDED_APPS:
            if excluded.lower() in app_name:
                return True
    return False


def detect_pii(text: str) -> list[dict]:
    """Detect potential PII in OCR text.

    Returns list of dicts with type and matched text.
    """
    pii_patterns = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    findings = []
    for pii_type, pattern in pii_patterns.items():
        for match in re.finditer(pattern, text):
            findings.append({"type": pii_type, "text": match.group()})

    return findings


def is_study_relevant(detected_activity: str) -> bool:
    """Check if the detected activity is study-relevant.

    Non-study activities (social media, entertainment) should NOT be
    sent to the cloud — only logged locally as off-task.
    """
    non_study_activities = {"idle", "entertainment", "social_media"}
    return detected_activity not in non_study_activities


def preprocess_screenshot(
    jpeg_bytes: bytes,
    windows: Optional[list[dict]] = None,
) -> Optional[bytes]:
    """Run the Privacy Gate on a screenshot.

    1. Check for sensitive windows → skip if found
    2. Return the screenshot (blurring/redaction can be added later)

    Returns JPEG bytes if safe to send, None if should skip.
    """
    if windows is None:
        windows = get_active_windows()

    # Check for sensitive apps
    if has_sensitive_window(windows):
        logger.info("Sensitive window detected — skipping this screenshot")
        return None

    # For MVP: return as-is. Post-hackathon: add PII blur regions.
    return jpeg_bytes
