"""WebSocket/HTTP client for communicating with the Cloud Run backend."""

from __future__ import annotations

import base64
import json
import logging
import time

from studypartner.client.config import Config
from studypartner.shared.models import (
    CoachingNudge,
    DetectedActivity,
    NudgeType,
    ScreenshotAnalysis,
    StudyPhase,
)

logger = logging.getLogger(__name__)


async def analyze_screenshot(
    jpeg_bytes: bytes,
    context: dict,
    config: Config,
) -> ScreenshotAnalysis | None:
    """Send screenshot to the Cloud Run backend and return analysis.

    Uses REST endpoint POST /api/analyze-screenshot.
    """
    import httpx

    if not config.backend_url:
        logger.error("❌ No backend URL configured. Run 'studypartner setup' first.")
        return None

    url = f"{config.backend_url}/api/analyze-screenshot"

    # Serialize context — it may be a Pydantic model or a dict
    if hasattr(context, "model_dump"):
        context_dict = context.model_dump(mode="json")
    elif hasattr(context, "dict"):
        context_dict = context.dict()
    else:
        context_dict = context

    payload = {
        "screenshot_b64": base64.b64encode(jpeg_bytes).decode(),
        "context": context_dict,
    }

    logger.info("☁️  POST %s", url)
    logger.debug("   Payload size: %.1f KB (screenshot) + context",
                  len(jpeg_bytes) / 1024)

    try:
        start = time.monotonic()

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            elapsed_ms = (time.monotonic() - start) * 1000

            logger.info("☁️  Response: %d in %.0fms", response.status_code, elapsed_ms)

            if response.status_code != 200:
                logger.error("❌ Backend returned %d: %s",
                              response.status_code, response.text[:200])
                return None

            data = response.json()
            logger.debug("   Raw response: %s", json.dumps(data, indent=2)[:500])

            return _parse_analysis(data)

    except httpx.ConnectError as e:
        logger.error("❌ Cannot connect to backend: %s", e)
        logger.error("   Is the backend deployed? Check: curl %s/api/health", config.backend_url)
        return None
    except httpx.TimeoutException:
        logger.error("❌ Backend request timed out (30s)")
        return None
    except Exception as e:
        logger.error("❌ Backend request failed: %s", e, exc_info=True)
        return None


def _parse_analysis(data: dict) -> ScreenshotAnalysis | None:
    """Parse the backend response into a ScreenshotAnalysis."""
    try:
        # Parse detected activity
        activity_str = data.get("detected_activity", "other")
        try:
            activity = DetectedActivity(activity_str)
        except ValueError:
            activity = DetectedActivity.OTHER

        # Parse study phase
        phase_str = data.get("study_phase", "unknown")
        try:
            phase = StudyPhase(phase_str)
        except ValueError:
            phase = StudyPhase.UNKNOWN

        # Parse coaching nudge
        nudge = None
        nudge_data = data.get("coaching_nudge")
        if nudge_data and isinstance(nudge_data, dict):
            try:
                nudge = CoachingNudge(
                    nudge_type=NudgeType(nudge_data.get("nudge_type", "recall_prompt")),
                    message=nudge_data.get("message", ""),
                    technique=nudge_data.get("technique"),
                )
            except (ValueError, KeyError):
                pass

        return ScreenshotAnalysis(
            detected_activity=activity,
            detected_topic=data.get("detected_topic"),
            study_phase=phase,
            coaching_nudge=nudge,
            raw_response=data.get("raw_response", ""),
        )

    except Exception as e:
        logger.error("Failed to parse analysis response: %s", e)
        return None
