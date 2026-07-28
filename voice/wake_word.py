"""
WakeWordListener - the audio front end. Continuously streams microphone
audio through Vosk (fully offline speech recognition) listening for the
wake phrase, then records and transcribes whatever's said right after it.

Nothing here talks to Emma's backend or does any AI - that's client.py and
the router's job respectively. This module's only responsibility is
turning "sound near the microphone" into "a short string of text".
"""
from __future__ import annotations

import json
import queue
import time
from typing import Optional

from .matcher import contains_wake_word

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000  # ~0.25s of int16 mono audio per block at 16kHz


class VoiceDependencyError(RuntimeError):
    """Raised when a required package or model isn't available, with a fix-it message."""


def _require_vosk():
    try:
        import vosk
    except ImportError as exc:
        raise VoiceDependencyError(
            "vosk isn't installed. Run: pip install vosk --break-system-packages"
        ) from exc
    return vosk


def _require_sounddevice():
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise VoiceDependencyError(
            "sounddevice isn't installed. Run: pip install sounddevice --break-system-packages "
            "(Linux also needs PortAudio: sudo apt install libportaudio2)"
        ) from exc
    return sd


def load_model(model_path: Optional[str]):
    """
    Loads a Vosk model once so it can be shared between the wake-word
    listener and command capture, instead of reloading it (a few hundred
    MB) for every single utterance.
    """
    if not model_path:
        raise VoiceDependencyError(
            "No VOICE_VOSK_MODEL_PATH set. Download a model from "
            "https://alphacephei.com/vosk/models (vosk-model-small-en-us-0.15 is a good "
            "~40MB starting point), unzip it somewhere, and set VOICE_VOSK_MODEL_PATH "
            "to that folder's path in .env."
        )
    vosk = _require_vosk()
    vosk.SetLogLevel(-1)  # Vosk is chatty on stderr by default; keep it quiet.
    return vosk.Model(model_path)


class _MicStream:
    """Wraps sounddevice's RawInputStream behind a simple blocking queue."""

    def __init__(self, device: Optional[str] = None):
        self._sd = _require_sounddevice()
        self.device = device or None
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(bytes(indata))

    def __enter__(self):
        self._stream = self._sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=self.device,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    def read(self, timeout: float = 0.3) -> Optional[bytes]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


class WakeWordListener:
    """
    Usage:
        listener = WakeWordListener(model, wake_word="hey emma")
        listener.wait_for_wake_word()      # blocks until "hey emma" is heard
        command = listener.capture_command()  # blocks, returns transcribed text
    """

    def __init__(self, model, wake_word: str = "hey emma", device: Optional[str] = None):
        self.model = model
        self.wake_word = wake_word
        self.device = device or None

    def wait_for_wake_word(self, stop_check=None) -> bool:
        """
        Streams mic audio through Vosk until the wake phrase is detected.
        `stop_check`, if given, is a zero-arg callable polled between reads
        so callers (e.g. the GUI's Stop button, or the barge-in watcher that
        listens *while Emma is speaking*) can cancel listening.

        Returns True if the wake word was actually heard, False if listening
        was cancelled via `stop_check`. The distinction matters for barge-in:
        the watcher thread only cuts Emma off when the phrase was genuinely
        heard, not when the main loop tells it to stand down.
        """
        vosk = _require_vosk()
        recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)

        with _MicStream(self.device) as mic:
            while True:
                if stop_check is not None and stop_check():
                    return False
                data = mic.read(timeout=0.3)
                if data is None:
                    continue

                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                else:
                    text = json.loads(recognizer.PartialResult()).get("partial", "")

                if text and contains_wake_word(text, self.wake_word):
                    return True

    def capture_command(self, max_seconds: float = 8.0, silence_seconds: float = 1.2) -> str:
        """
        Records what's said right after the wake word and transcribes it.
        Recording stops on whichever comes first: `max_seconds` elapsed
        total, or `silence_seconds` of quiet after speech has started
        (a slightly longer grace period is given before speech begins,
        so "hey emma" ... <pause to think> ... "what's on my calendar"
        doesn't get cut off too early).
        """
        vosk = _require_vosk()
        recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)

        start = time.monotonic()
        last_activity = start
        speech_started = False
        leading_grace = max(silence_seconds * 2, 2.5)
        final_chunks: list[str] = []

        with _MicStream(self.device) as mic:
            while True:
                now = time.monotonic()
                if now - start > max_seconds:
                    break

                data = mic.read(timeout=0.2)
                if data is not None:
                    if recognizer.AcceptWaveform(data):
                        piece = json.loads(recognizer.Result()).get("text", "")
                        if piece:
                            final_chunks.append(piece)
                            speech_started = True
                            last_activity = now
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "")
                        if partial:
                            speech_started = True
                            last_activity = now

                quiet_for = now - last_activity
                cutoff = silence_seconds if speech_started else leading_grace
                if quiet_for > cutoff and (speech_started or now - start > leading_grace):
                    break

            tail = json.loads(recognizer.FinalResult()).get("text", "")
            if tail:
                final_chunks.append(tail)

        return " ".join(chunk for chunk in final_chunks if chunk).strip()
