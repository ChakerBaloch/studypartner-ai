"""Audio capture and playback for voice coaching via Gemini Live API."""

from __future__ import annotations

import io
import logging
import queue
import threading
import wave
from typing import Optional

logger = logging.getLogger(__name__)

# Audio format constants (matching Gemini Live API requirements)
SAMPLE_RATE = 16000      # 16kHz for input
OUTPUT_SAMPLE_RATE = 24000  # 24kHz for Gemini output
CHANNELS = 1             # Mono
SAMPLE_WIDTH = 2         # 16-bit PCM
CHUNK_SIZE = 1024        # Frames per buffer


class AudioCapture:
    """Capture microphone audio for voice input to Gemini Live API.

    Uses pyobjc AVFoundation for native macOS audio capture.
    Falls back to pyaudio if available.
    """

    def __init__(self):
        self._running = False
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start capturing audio from the microphone."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Audio capture started")

    def stop(self):
        """Stop capturing audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Audio capture stopped")

    def get_audio_chunk(self, timeout: float = 0.1) -> Optional[bytes]:
        """Get the next audio chunk from the queue."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        """Background thread: capture audio using pyaudio or subprocess."""
        try:
            self._capture_with_pyaudio()
        except ImportError:
            logger.info("pyaudio not available, using subprocess fallback")
            self._capture_with_subprocess()
        except Exception as e:
            logger.error(f"Audio capture failed: {e}")

    def _capture_with_pyaudio(self):
        """Capture audio using pyaudio."""
        import pyaudio

        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        try:
            while self._running:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._audio_queue.put(data)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _capture_with_subprocess(self):
        """Fallback: capture audio using macOS sox/rec command."""
        import subprocess

        # Use macOS `rec` (from sox) or `ffmpeg` to capture mic
        try:
            proc = subprocess.Popen(
                [
                    "ffmpeg", "-f", "avfoundation", "-i", ":default",
                    "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
                    "-f", "s16le", "-",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            while self._running and proc.poll() is None:
                data = proc.stdout.read(CHUNK_SIZE * SAMPLE_WIDTH)
                if data:
                    self._audio_queue.put(data)

            proc.terminate()
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install with: brew install ffmpeg")


class AudioPlayer:
    """Play audio output from Gemini Live API coaching responses."""

    def __init__(self):
        self._play_queue: queue.Queue[bytes] = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the audio playback thread."""
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()
        logger.info("Audio player started")

    def stop(self):
        """Stop audio playback."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Audio player stopped")

    def play(self, audio_data: bytes):
        """Queue audio data for playback."""
        self._play_queue.put(audio_data)

    def _playback_loop(self):
        """Background thread: play queued audio chunks."""
        try:
            self._play_with_pyaudio()
        except ImportError:
            logger.info("pyaudio not available, using afplay fallback")
            self._play_with_afplay()
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")

    def _play_with_pyaudio(self):
        """Play audio using pyaudio."""
        import pyaudio

        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=OUTPUT_SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        try:
            while self._running:
                try:
                    data = self._play_queue.get(timeout=0.1)
                    stream.write(data)
                except queue.Empty:
                    continue
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _play_with_afplay(self):
        """Fallback: write to temp WAV file and play with macOS afplay."""
        import subprocess
        import tempfile

        while self._running:
            try:
                data = self._play_queue.get(timeout=0.5)

                # Accumulate data for a reasonable chunk
                all_data = data
                while not self._play_queue.empty():
                    try:
                        more = self._play_queue.get_nowait()
                        all_data += more
                    except queue.Empty:
                        break

                # Write WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    with wave.open(tmp.name, "wb") as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(SAMPLE_WIDTH)
                        wf.setframerate(OUTPUT_SAMPLE_RATE)
                        wf.writeframes(all_data)

                    # Play with afplay (macOS built-in)
                    subprocess.run(
                        ["afplay", tmp.name],
                        capture_output=True,
                        timeout=30,
                    )

                    import os
                    os.unlink(tmp.name)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"afplay playback failed: {e}")


def pcm_to_wav(pcm_data: bytes, sample_rate: int = OUTPUT_SAMPLE_RATE) -> bytes:
    """Convert raw PCM data to WAV format."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buffer.getvalue()
