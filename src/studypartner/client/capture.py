"""Screenshot capture engine for macOS using pyobjc."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from studypartner.shared.constants import (
    SCREENSHOTS_DIR,
    SCREENSHOT_HEIGHT,
    SCREENSHOT_JPEG_QUALITY,
    SCREENSHOT_WIDTH,
)

logger = logging.getLogger(__name__)


def capture_screenshot() -> Optional[bytes]:
    """Capture the main display screenshot and return as JPEG bytes.

    Uses macOS Quartz (CoreGraphics) via pyobjc to capture the screen.
    Falls back to subprocess screencapture if pyobjc is unavailable.

    Returns:
        JPEG bytes of the downscaled screenshot, or None on failure.
    """
    try:
        return _capture_with_quartz()
    except ImportError:
        logger.warning("pyobjc not available, falling back to screencapture CLI")
        return _capture_with_subprocess()
    except Exception as e:
        logger.error(f"Quartz capture failed: {e}, falling back to subprocess")
        return _capture_with_subprocess()


def _capture_with_quartz() -> Optional[bytes]:
    """Capture using CoreGraphics (Quartz) via pyobjc."""
    import Quartz

    # Capture the main display
    image_ref = Quartz.CGWindowListCreateImage(
        Quartz.CGRectInfinite,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )

    if image_ref is None:
        logger.error("CGWindowListCreateImage returned None — check Screen Recording permission")
        return None

    # Get dimensions
    width = Quartz.CGImageGetWidth(image_ref)
    height = Quartz.CGImageGetHeight(image_ref)

    # Convert CGImage to raw bitmap data
    color_space = Quartz.CGColorSpaceCreateDeviceRGB()
    bytes_per_row = 4 * width
    bitmap_data = bytearray(bytes_per_row * height)

    context = Quartz.CGBitmapContextCreate(
        bitmap_data,
        width,
        height,
        8,  # bits per component
        bytes_per_row,
        color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )

    if context is None:
        logger.error("Failed to create bitmap context")
        return None

    Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, width, height), image_ref)

    # Convert to PIL Image
    img = Image.frombytes("RGBA", (width, height), bytes(bitmap_data))

    # Downscale
    img = img.resize((SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT), Image.LANCZOS)

    # Convert to RGB (drop alpha) and encode as JPEG
    img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=SCREENSHOT_JPEG_QUALITY)
    return buffer.getvalue()


def _capture_with_subprocess() -> Optional[bytes]:
    """Fallback: capture using macOS screencapture CLI."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["screencapture", "-x", "-C", tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.error(f"screencapture failed: {result.stderr.decode()}")
            return None

        img = Image.open(tmp_path)
        img = img.resize((SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT), Image.LANCZOS)
        img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=SCREENSHOT_JPEG_QUALITY)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Subprocess capture failed: {e}")
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def save_screenshot(jpeg_bytes: bytes) -> Path:
    """Save a screenshot to the local rolling buffer."""
    today_dir = SCREENSHOTS_DIR / datetime.now().strftime("%Y-%m-%d")
    today_dir.mkdir(parents=True, exist_ok=True)

    filename = datetime.now().strftime("%H%M%S") + "_screenshot.jpg"
    filepath = today_dir / filename
    filepath.write_bytes(jpeg_bytes)
    return filepath


def cleanup_old_screenshots(max_age_days: int = 7):
    """Delete screenshots older than max_age_days."""
    if not SCREENSHOTS_DIR.exists():
        return

    cutoff = datetime.now() - __import__("datetime").timedelta(days=max_age_days)
    for day_dir in SCREENSHOTS_DIR.iterdir():
        if day_dir.is_dir():
            try:
                dir_date = datetime.strptime(day_dir.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    import shutil
                    shutil.rmtree(day_dir)
                    logger.info(f"Cleaned up old screenshots: {day_dir}")
            except ValueError:
                pass  # Skip non-date directories
