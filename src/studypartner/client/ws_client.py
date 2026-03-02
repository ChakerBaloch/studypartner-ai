"""WebSocket client for communicating with the Cloud Run backend."""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional

import httpx

from studypartner.client.config import Config
from studypartner.shared.models import ContextPacket, ScreenshotAnalysis

logger = logging.getLogger(__name__)


async def analyze_screenshot(
    jpeg_bytes: bytes,
    context: ContextPacket,
    config: Config,
) -> Optional[ScreenshotAnalysis]:
    """Send a screenshot to the Cloud Run backend for Gemini analysis.

    Uses the REST endpoint for one-shot analysis.
    """
    if not config.backend_url:
        logger.error("No backend URL configured. Run 'studypartner setup' first.")
        return None

    url = f"{config.backend_url}/api/analyze-screenshot"

    # Encode screenshot as base64 for JSON transport
    screenshot_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")

    payload = {
        "screenshot_b64": screenshot_b64,
        "context": context.model_dump(mode="json"),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return ScreenshotAnalysis(**data)

    except httpx.ConnectError:
        logger.error(f"Cannot connect to backend at {config.backend_url}")
        return None
    except httpx.TimeoutException:
        logger.error("Backend request timed out")
        return None
    except Exception as e:
        logger.error(f"Backend request failed: {e}")
        return None


async def health_check(config: Config) -> bool:
    """Check if the backend is reachable."""
    if not config.backend_url:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.backend_url}/api/health")
            return response.status_code == 200
    except Exception:
        return False
