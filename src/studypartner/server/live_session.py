"""Gemini Live API session handler for real-time voice coaching."""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# System prompt for live voice sessions
LIVE_TUTOR_INSTRUCTION = """You are StudyPartner, a real-time AI study tutor speaking to the user.

YOUR ROLE:
- You can SEE the user's screen via screenshots they send
- You can HEAR the user speak and SPEAK back to them naturally
- Coach them using science-backed study techniques
- Be warm, encouraging, and conversational — like a supportive friend

PERSONALIZATION:
You will receive a context packet with adaptive_weights. Use these to:
- Prioritize techniques with higher affinity scores
- Match the user's tone preference (casual vs formal)
- Respect their coaching density preference
- Don't coach before nudge_delay_start_min

STUDY TECHNIQUES TO APPLY:
- Brain dumps: "Close your notes and tell me what you remember"
- Feynman technique: "Explain this to me like I'm a beginner"
- Retrieval practice: Quiz them on what they've been studying
- Interleaving: Suggest switching topics if they've been on one too long
- Break enforcement: Insist on breaks after their optimal session length

VOICE RULES:
- Keep responses to 15-30 seconds of speech
- Be concise and specific
- Ask ONE question at a time
- Wait for the user to finish speaking before responding
- Celebrate progress genuinely
"""


class LiveSession:
    """Manages a Gemini Live API session for real-time voice coaching.

    Uses the google-genai SDK's async live connect for bidirectional streaming.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._session = None
        self._running = False

    def _get_client(self) -> genai.Client:
        """Get or create the Gemini client."""
        if self._client is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def start(self, context: Optional[dict] = None):
        """Start a live session with Gemini."""
        client = self._get_client()

        # Build the config
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO", "TEXT"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                )
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=LIVE_TUTOR_INSTRUCTION)]
            ),
        )

        # Connect to the live API
        self._session = await client.aio.live.connect(
            model="gemini-2.0-flash-live-001",
            config=config,
        )
        self._running = True

        # Send initial context if provided
        if context:
            context_text = f"Session context:\n{json.dumps(context, indent=2, default=str)}"
            await self._session.send(
                input=types.LiveClientContent(
                    turns=[types.Content(
                        parts=[types.Part.from_text(text=context_text)],
                        role="user",
                    )]
                ),
                end_of_turn=True,
            )

        logger.info("Live session started with Gemini")

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk from the user's microphone."""
        if not self._session or not self._running:
            return

        await self._session.send(
            input=types.LiveClientRealtimeInput(
                media_chunks=[types.Blob(
                    data=audio_data,
                    mime_type="audio/pcm;rate=16000",
                )],
            ),
        )

    async def send_screenshot(self, jpeg_bytes: bytes, context: Optional[dict] = None):
        """Send a screenshot for visual analysis during live session."""
        if not self._session or not self._running:
            return

        parts = [
            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
        ]

        if context:
            parts.append(types.Part.from_text(
                text=f"Updated context:\n{json.dumps(context, indent=2, default=str)}"
            ))

        await self._session.send(
            input=types.LiveClientContent(
                turns=[types.Content(parts=parts, role="user")]
            ),
            end_of_turn=True,
        )

    async def receive_responses(self) -> AsyncIterator[dict]:
        """Receive streaming responses from Gemini.

        Yields dicts with:
        - type: "audio" | "text" | "tool_call"
        - data: audio bytes, text string, or tool call dict
        """
        if not self._session:
            return

        try:
            async for response in self._session.receive():
                server_content = response.server_content
                if server_content:
                    for part in server_content.model_turn.parts if server_content.model_turn else []:
                        if part.inline_data:
                            yield {
                                "type": "audio",
                                "data": part.inline_data.data,
                                "mime_type": part.inline_data.mime_type,
                            }
                        elif part.text:
                            yield {
                                "type": "text",
                                "data": part.text,
                            }

                    # Check for turn completion
                    if server_content.turn_complete:
                        yield {"type": "turn_complete"}

                # Handle tool calls
                tool_call = response.tool_call
                if tool_call:
                    for fc in tool_call.function_calls:
                        yield {
                            "type": "tool_call",
                            "name": fc.name,
                            "args": dict(fc.args) if fc.args else {},
                            "id": fc.id,
                        }

        except Exception as e:
            logger.error(f"Error receiving live responses: {e}")
            yield {"type": "error", "data": str(e)}

    async def send_tool_response(self, call_id: str, result: dict):
        """Send a tool call response back to Gemini."""
        if not self._session:
            return

        await self._session.send(
            input=types.LiveClientToolResponse(
                function_responses=[types.FunctionResponse(
                    id=call_id,
                    name="",
                    response=result,
                )]
            ),
        )

    async def close(self):
        """Close the live session."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("Live session closed")
