"""FastAPI backend for StudyPartner Cloud Run deployment."""

from __future__ import annotations

import asyncio
import base64
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from studypartner.server.agent import analyze_with_gemini

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StudyPartner AI Backend",
    description="Stateless Cloud Run backend for StudyPartner AI coaching.",
    version="0.1.0",
)

# CORS — allow the macOS client to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    """Request body for screenshot analysis."""
    screenshot_b64: str
    context: dict


class AnalyzeResponse(BaseModel):
    """Response body from screenshot analysis."""
    detected_activity: str = "other"
    detected_topic: str | None = None
    study_phase: str = "unknown"
    coaching_nudge: dict | None = None
    raw_response: str = ""


@app.get("/api/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "service": "studypartner-backend"}


@app.post("/api/analyze-screenshot", response_model=AnalyzeResponse)
async def analyze_screenshot(request: AnalyzeRequest):
    """Analyze a screenshot with Gemini and return coaching advice.

    This endpoint is STATELESS — the screenshot is processed and immediately
    discarded. Nothing is written to disk. Nothing is stored.
    """
    try:
        # Decode the screenshot
        screenshot_bytes = base64.b64decode(request.screenshot_b64)

        # Call Gemini via the ADK agent
        result = await analyze_with_gemini(
            screenshot_bytes=screenshot_bytes,
            context=request.context,
        )

        return AnalyzeResponse(**result)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return AnalyzeResponse(
            raw_response=f"Error: {str(e)}",
        )

    # ❌ No disk writes. No database inserts. No cloud storage.
    # ✅ Request processed, response returned, memory freed.


@app.websocket("/ws/live-session")
async def live_session_ws(websocket: WebSocket):
    """Bidirectional WebSocket for Gemini Live API streaming.

    Relays audio and screenshots between the macOS client and Gemini Live API.
    The server acts as a transparent proxy — no data is stored.
    """
    await websocket.accept()
    logger.info("Live session WebSocket connected")

    from studypartner.server.live_session import LiveSession
    session = LiveSession()

    async def relay_gemini_to_client():
        """Forward Gemini's responses (audio + text) to the client."""
        try:
            async for response in session.receive_responses():
                if response["type"] == "audio":
                    # Send audio as base64-encoded binary
                    import base64 as b64
                    await websocket.send_json({
                        "type": "audio",
                        "data": b64.b64encode(response["data"]).decode(),
                        "mime_type": response.get("mime_type", "audio/pcm"),
                    })
                elif response["type"] == "text":
                    await websocket.send_json({
                        "type": "text",
                        "data": response["data"],
                    })
                elif response["type"] == "turn_complete":
                    await websocket.send_json({"type": "turn_complete"})
                elif response["type"] == "tool_call":
                    await websocket.send_json({
                        "type": "tool_call",
                        "name": response["name"],
                        "args": response["args"],
                        "id": response["id"],
                    })
        except Exception as e:
            logger.error(f"Gemini relay error: {e}")

    relay_task = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "unknown")

            if msg_type == "start_live":
                # Start the Gemini Live API session
                context = data.get("context", {})
                await session.start(context=context)
                relay_task = asyncio.create_task(relay_gemini_to_client())
                await websocket.send_json({"type": "live_started"})

            elif msg_type == "audio":
                # Relay user audio to Gemini
                audio_bytes = base64.b64decode(data["data"])
                await session.send_audio(audio_bytes)

            elif msg_type == "screenshot":
                if session._session:
                    # Live mode: send to Gemini Live
                    screenshot_bytes = base64.b64decode(data["screenshot_b64"])
                    context = data.get("context", {})
                    await session.send_screenshot(screenshot_bytes, context)
                else:
                    # Non-live mode: use REST-style analysis
                    screenshot_bytes = base64.b64decode(data["screenshot_b64"])
                    context = data.get("context", {})
                    result = await analyze_with_gemini(
                        screenshot_bytes=screenshot_bytes,
                        context=context,
                    )
                    await websocket.send_json({
                        "type": "analysis",
                        "data": result,
                    })

            elif msg_type == "tool_response":
                await session.send_tool_response(
                    call_id=data["id"],
                    result=data["result"],
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Live session WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        if relay_task:
            relay_task.cancel()
        await session.close()
        # ❌ No disk writes, no database inserts, no cloud storage.
        logger.info("Live session cleaned up — all data discarded")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
