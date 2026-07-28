"""
Speaker - offline text-to-speech, "just on my computer".

Emma speaks with a natural, feminine voice through Piper, a small neural
TTS engine that runs entirely on the CPU with no network calls:

  - Piper (preferred)  -> neural voices that actually sound human. Ships a
                          curated feminine default ("Amy"). Fully offline;
                          the voice model is a local .onnx file.
  - pyttsx3 (fallback) -> wraps whatever robotic TTS the OS already has
                          (SAPI5 / NSSpeech / espeak-ng). Used only when no
                          Piper voice is installed, so Emma still talks even
                          on a bare machine.

Nothing here ever goes over the network once the voice model is on disk.

Backend selection (``engine``):
    "auto"     -> Piper if a voice model is available, else pyttsx3
    "piper"    -> Piper only (raises if unavailable)
    "pyttsx3"  -> the legacy system voice only

Design notes:
  - The Piper voice is loaded once and reused. Loading the ~60MB ONNX model
    on every utterance would add seconds of latency; onnxruntime inference
    is stateless per call, so a single cached voice is safe for Emma's
    sequential "speak one reply at a time" loop.
  - pyttsx3's engine, by contrast, is NOT safe to reuse across threads and
    hangs if .stop() races .runAndWait(), so that backend still builds a
    fresh engine per utterance - same as before.
  - Playback prefers sounddevice (in-process, no temp files). If there's no
    usable output device it falls back to the system `aplay`/`paplay`, so
    Emma stays audible across very different machines.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger("aqua.voice.tts")

# Where `download_voice.py` drops voice models, and where "auto" looks first.
MODELS_DIR = Path(__file__).resolve().parent / "models"


def _discover_piper_model(explicit: Optional[str]) -> Optional[Path]:
    """
    Resolve which Piper voice to use.

    Order: an explicit path/name from config, then any *.onnx sitting in
    voice/models (preferring one whose name looks feminine so "auto" lands
    on a nice default even if several voices are installed).
    """
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        # Allow a bare model name like "en_US-amy-medium".
        candidate = MODELS_DIR / (explicit if explicit.endswith(".onnx") else f"{explicit}.onnx")
        if candidate.is_file():
            return candidate
        logger.warning("Configured Piper model %r not found; falling back to auto-discovery.", explicit)

    if not MODELS_DIR.is_dir():
        return None

    onnx_files = sorted(MODELS_DIR.glob("*.onnx"))
    if not onnx_files:
        return None

    # Prefer a voice that advertises itself as female in its filename.
    feminine_hints = ("amy", "female", "jenny", "hfc_female", "libritts", "kathleen", "ljspeech")
    for f in onnx_files:
        if any(h in f.name.lower() for h in feminine_hints):
            return f
    return onnx_files[0]


class _PiperBackend:
    """Neural, natural-sounding TTS via Piper. Loaded lazily and cached."""

    def __init__(
        self,
        model_path: Path,
        length_scale: float = 1.0,
        noise_scale: float = 0.667,
        noise_w_scale: float = 0.8,
        volume: float = 1.0,
        speaker_id: Optional[int] = None,
    ):
        from piper import PiperVoice, SynthesisConfig

        self.model_path = model_path
        self._voice = PiperVoice.load(str(model_path))
        self._syn_config = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w_scale,
            volume=volume,
            speaker_id=speaker_id,
            normalize_audio=True,
        )
        self.sample_rate = self._voice.config.sample_rate
        logger.info(
            "Piper voice ready: %s (%d Hz, length_scale=%.2f)",
            model_path.name,
            self.sample_rate,
            length_scale,
        )

    def say(self, text: str, stop_event: Optional[threading.Event] = None) -> bool:
        """
        Speak `text`. Returns True if it played to the end, False if it was
        cut short by `stop_event` (barge-in).

        Synthesis happens sentence-by-sentence so a barge-in can stop between
        chunks without waiting for the whole reply to be turned into audio
        first - important for long replies, where synthesizing everything up
        front would add a noticeable delay before the interrupt could land.
        """
        chunks: Iterable = self._voice.synthesize(text, syn_config=self._syn_config)
        for chunk in chunks:
            if stop_event is not None and stop_event.is_set():
                return False
            pcm = chunk.audio_int16_bytes
            if not pcm:
                continue
            if not _play_pcm(pcm, self.sample_rate, stop_event=stop_event):
                return False
        return True


class _Pyttsx3Backend:
    """Legacy fallback: whatever robotic TTS engine the OS already ships."""

    def __init__(self, rate: int = 175, voice_hint: Optional[str] = None):
        self.rate = rate
        self.voice_hint = voice_hint

    def say(self, text: str, stop_event: Optional[threading.Event] = None) -> bool:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError(
                "pyttsx3 isn't installed. Run: pip install pyttsx3 --break-system-packages "
                "(Linux also needs espeak-ng: sudo apt install espeak-ng)"
            ) from exc

        # pyttsx3 can't reliably be interrupted mid-utterance across
        # backends, so barge-in here is coarse: speak one sentence at a time
        # and check `stop_event` between sentences. Good enough for the
        # legacy fallback voice; the real neural path (Piper) interrupts
        # promptly, chunk by chunk.
        sentences = _split_sentences(text) if stop_event is not None else [text]
        for sentence in sentences:
            if stop_event is not None and stop_event.is_set():
                return False
            engine = pyttsx3.init()
            try:
                engine.setProperty("rate", self.rate)
                if self.voice_hint:
                    self._select_voice(engine, self.voice_hint)
                engine.say(sentence)
                engine.runAndWait()
            finally:
                del engine
        return not (stop_event is not None and stop_event.is_set())

    def _select_voice(self, engine, hint: str) -> None:
        hint_lower = hint.lower()
        for voice in engine.getProperty("voices"):
            haystack = f"{voice.id} {voice.name}".lower()
            if hint_lower in haystack:
                engine.setProperty("voice", voice.id)
                return
        logger.warning("No installed voice matched hint %r; using the system default voice.", hint)


def _play_pcm(pcm: bytes, sample_rate: int, stop_event: Optional[threading.Event] = None) -> bool:
    """
    Play raw 16-bit mono PCM. Prefer sounddevice (in-process, no temp file);
    fall back to the system audio player if there's no usable output device.

    Returns True if playback finished, False if `stop_event` was set partway
    through (barge-in) so the caller stops feeding it further audio.
    """
    try:
        import numpy as np
        import sounddevice as sd

        samples = np.frombuffer(pcm, dtype=np.int16)
        sd.play(samples, samplerate=sample_rate)
        if stop_event is None:
            sd.wait()
            return True
        # Poll instead of sd.wait() so a barge-in can cut playback promptly.
        while sd.get_stream().active:
            if stop_event.is_set():
                sd.stop()
                return False
            stop_event.wait(0.05)
        return True
    except Exception as exc:  # noqa: BLE001 - any audio-stack failure -> try the CLI player
        logger.debug("sounddevice playback unavailable (%s); trying system player.", exc)

    return _play_pcm_via_cli(pcm, sample_rate, stop_event=stop_event)


def _play_pcm_via_cli(pcm: bytes, sample_rate: int, stop_event: Optional[threading.Event] = None) -> bool:
    player = shutil.which("aplay") or shutil.which("paplay") or shutil.which("ffplay")
    if not player:
        raise RuntimeError(
            "No audio output available: sounddevice failed and none of aplay/paplay/ffplay "
            "were found. On Linux, install ALSA (aplay) or PulseAudio (paplay)."
        )

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)

        if player.endswith("ffplay"):
            cmd = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", path]
        elif player.endswith("aplay"):
            cmd = [player, "-q", path]
        else:  # paplay
            cmd = [player, path]

        if stop_event is None:
            subprocess.run(cmd, check=False)
            return True

        # Run the player detached so a barge-in can terminate it mid-word.
        proc = subprocess.Popen(cmd)
        while proc.poll() is None:
            if stop_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return False
            stop_event.wait(0.05)
        return True
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _split_sentences(text: str) -> list[str]:
    """
    Very small sentence splitter for the pyttsx3 fallback's coarse barge-in.
    Not linguistically clever - just breaks on ., !, ? and newlines so the
    stop check gets a chance to fire between utterances.
    """
    import re

    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p for p in (s.strip() for s in parts) if p]


class Speaker:
    """
    Emma's voice. Picks the best available backend and hides the difference
    from the rest of the voice loop, which just calls ``speaker.say(text)``.
    """

    def __init__(
        self,
        rate: int = 175,
        voice_hint: Optional[str] = None,
        engine: str = "auto",
        piper_model_path: Optional[str] = None,
        length_scale: Optional[float] = None,
        noise_scale: float = 0.667,
        noise_w_scale: float = 0.8,
        volume: float = 1.0,
        speaker_id: Optional[int] = None,
    ):
        self.rate = rate
        self.voice_hint = voice_hint
        self._backend = None
        self._backend_name = "none"

        engine = (engine or "auto").lower()
        want_piper = engine in ("auto", "piper")

        if want_piper:
            model = _discover_piper_model(piper_model_path)
            if model is not None:
                try:
                    self._backend = _PiperBackend(
                        model,
                        length_scale=length_scale if length_scale is not None else _rate_to_length_scale(rate),
                        noise_scale=noise_scale,
                        noise_w_scale=noise_w_scale,
                        volume=volume,
                        speaker_id=speaker_id,
                    )
                    self._backend_name = "piper"
                except Exception as exc:  # noqa: BLE001 - fall back rather than go mute
                    logger.warning("Couldn't start Piper (%s); falling back to system voice.", exc)
            elif engine == "piper":
                raise RuntimeError(
                    "No Piper voice model found. Run `python voice/download_voice.py` to fetch a "
                    "feminine voice, or set VOICE_TTS_ENGINE=pyttsx3 to use the system voice."
                )
            else:
                logger.info(
                    "No Piper voice installed - using the system voice. For a natural feminine "
                    "voice, run: python voice/download_voice.py"
                )

        if self._backend is None:
            self._backend = _Pyttsx3Backend(rate=rate, voice_hint=voice_hint)
            self._backend_name = "pyttsx3"

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def say(self, text: str, stop_event: Optional[threading.Event] = None) -> bool:
        """
        Speak `text` out loud and block until finished.

        If `stop_event` is given, playback can be interrupted (barge-in): the
        method returns False the moment the event is set, True if the whole
        reply was spoken.
        """
        if not text or not text.strip():
            return True
        return self._backend.say(text, stop_event=stop_event)

    @staticmethod
    def list_voices() -> list[dict]:
        """
        List available voices for the GUI's Voice tab: installed Piper models
        first (marked ``engine="piper"``), then system pyttsx3 voices.
        """
        voices: list[dict] = []

        for onnx in sorted(MODELS_DIR.glob("*.onnx")) if MODELS_DIR.is_dir() else []:
            voices.append({"id": str(onnx), "name": onnx.stem, "engine": "piper"})

        try:
            import pyttsx3

            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                voices.append({"id": v.id, "name": v.name, "engine": "pyttsx3"})
            del engine
        except Exception:  # noqa: BLE001 - system voices are optional
            pass

        return voices


def _rate_to_length_scale(rate: int) -> float:
    """
    Map the legacy words-per-minute ``rate`` (pyttsx3's knob, ~175 default)
    onto Piper's ``length_scale`` (1.0 = the voice's natural pace; higher is
    slower). This lets an existing VOICE_TTS_RATE keep roughly working when a
    user switches to Piper without having to relearn a new setting.
    """
    if not rate or rate <= 0:
        return 1.0
    scale = 175.0 / float(rate)
    # Keep it in a sane, natural-sounding band.
    return max(0.7, min(1.6, scale))
