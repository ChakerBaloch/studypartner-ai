"""ADK Agent definition and Gemini integration for StudyPartner."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Gemini client — initialized once
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Set it in your Cloud Run deployment."
            )
        _client = genai.Client(api_key=api_key)
    return _client


# --- System Prompt ---

STUDY_TUTOR_SYSTEM_PROMPT = """You are StudyPartner, a real-time AI study tutor.

YOUR ROLE:
- Observe the user's screen via periodic screenshots
- Detect what they are studying and what phase they are in
- Apply science-backed study techniques from the Permanent Learning Playbook
- Coach them in real-time — be warm, encouraging, and specific

PERSONALIZATION (from adaptive_weights in context):
- Check `preferred_techniques` — prioritize techniques with higher scores
- Check `tone_preference` — match casual/formal to user preference
- Check `coaching_density` — respect whether user wants more or fewer nudges
- Check `nudge_delay_start_min` — don't coach before the warm-up period
- Check `fatigue_onset_min` — lighten coaching intensity near fatigue point
- If `current_motivation_level` is low, be extra encouraging and suggest easier tasks

STUDY PHASES & TECHNIQUES:
1. ACQUIRE: User is reading/watching new material
   → Suggest worked examples, dual coding (draw diagrams)
2. PROCESS: User should be actively engaging with material
   → Prompt brain dumps, Feynman technique, interleaving
3. CONSOLIDATE: User should be testing and locking in knowledge
   → Trigger retrieval practice, delayed feedback, spaced review

ANTI-PATTERNS TO DETECT:
- Reading > 30 min without output → prompt brain dump
- Same problem type > 20 min → suggest interleaving
- Copying from AI chat → suggest asking AI to explain instead
- No break > optimal session length → enforce restorative break
- Returning after 24h+ → start with retrieval check

YOUR RESPONSE FORMAT:
Respond with a JSON object containing:
{
    "detected_activity": "coding|reading|browsing|ai_chat|idle|other",
    "detected_topic": "string or null",
    "study_phase": "acquire|process|consolidate|unknown",
    "should_nudge": true/false,
    "nudge_type": "time_based|phase_transition|anti_pattern|recall_prompt|progress|scheduled_review",
    "nudge_technique": "brain_dump|feynman|interleaving|worked_example|break|retrieval_practice|null",
    "nudge_message": "The coaching message to show the user (conversational, specific, 1-3 sentences)"
}

PERSONALITY:
- Speak conversationally, like a supportive friend
- Keep messages concise (1-3 sentences)
- Ask questions to engage active recall
- Celebrate progress genuinely
"""


async def analyze_with_gemini(
    screenshot_bytes: bytes,
    context: dict,
) -> dict:
    """Analyze a screenshot using Gemini and return structured coaching.

    Args:
        screenshot_bytes: JPEG screenshot bytes
        context: Context packet dict (session state, history, adaptive weights)

    Returns:
        Dict with detected_activity, detected_topic, study_phase,
        and optional coaching_nudge.
    """
    client = _get_client()

    # Build the user prompt with context
    context_str = json.dumps(context, indent=2, default=str)
    user_prompt = f"""Analyze this screenshot of the user's screen.

CONTEXT (user's current session state and learning history):
{context_str}

Based on the screenshot and context, determine:
1. What activity is the user doing?
2. What topic are they studying?
3. What study phase are they in?
4. Should you deliver a coaching nudge right now? If so, what?

Respond with ONLY a JSON object (no markdown, no code fences)."""

    try:
        # Call Gemini with the screenshot
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=user_prompt),
            ],
            config=types.GenerateContentConfig(
                system_instruction=STUDY_TUTOR_SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=500,
                response_mime_type="application/json",
            ),
        )

        # Parse the response
        response_text = response.text.strip()
        result = json.loads(response_text)

        # Build the return dict
        output = {
            "detected_activity": result.get("detected_activity", "other"),
            "detected_topic": result.get("detected_topic"),
            "study_phase": result.get("study_phase", "unknown"),
            "raw_response": response_text,
        }

        # Add coaching nudge if applicable
        if result.get("should_nudge"):
            output["coaching_nudge"] = {
                "nudge_type": result.get("nudge_type", "progress"),
                "technique": result.get("nudge_technique"),
                "delivery": "notification",
                "message": result.get("nudge_message", "Keep up the great work!"),
            }

        return output

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        return {
            "detected_activity": "other",
            "study_phase": "unknown",
            "raw_response": response_text if 'response_text' in dir() else str(e),
        }
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return {
            "detected_activity": "other",
            "study_phase": "unknown",
            "raw_response": str(e),
        }
