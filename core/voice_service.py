import logging
import queue
import re
import threading
from typing import Optional

from config import get_settings
from voice.tts import Speaker

logger = logging.getLogger("aqua.voice.service")

_speaker: Optional[Speaker] = None
_speaker_lock = threading.Lock()
_speech_queue: "queue.Queue[Optional[str]]" = queue.Queue()
_worker: Optional[threading.Thread] = None
_current_stop: Optional[threading.Event] = None


def _get_speaker() -> Speaker:
    global _speaker
    with _speaker_lock:
        if _speaker is None:
            settings = get_settings()
            _speaker = Speaker(
                rate=settings.voice_tts_rate,
                voice_hint=settings.voice_tts_voice,
                engine=settings.voice_tts_engine,
                piper_model_path=settings.voice_piper_model_path,
                length_scale=settings.voice_piper_length_scale,
                noise_scale=settings.voice_piper_noise_scale,
                noise_w_scale=settings.voice_piper_noise_w_scale,
                volume=settings.voice_piper_volume,
                speaker_id=settings.voice_piper_speaker_id,
            )
        return _speaker


def _worker_loop() -> None:
    global _current_stop
    while True:
        text = _speech_queue.get()
        if text is None:
            _speech_queue.task_done()
            return

        stop_event = threading.Event()
        _current_stop = stop_event
        try:
            _get_speaker().say(text, stop_event=stop_event)
        except Exception:
            logger.exception("TTS playback failed")
        finally:
            _current_stop = None
            _speech_queue.task_done()


def _ensure_worker() -> None:
    global _worker
    if _worker and _worker.is_alive():
        return
    _worker = threading.Thread(target=_worker_loop, name="aqua-tts", daemon=True)
    _worker.start()


def clean_for_speech(text: str, max_chars: int = 4200) -> str:
    text = text or ""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~>|#]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].strip() + "."
    return text


def summarize_note_for_speech(title: str, content: str) -> str:
    title = title or "your notes"
    body = clean_for_speech(content, max_chars=2600)
    return f"Your notes for {title} are ready. I'll read the opening and key ideas now. {body}"


def say(text: str, *, interrupt: bool = True, max_chars: int = 4200) -> bool:
    spoken = clean_for_speech(text, max_chars=max_chars)
    if not spoken:
        return False
    if interrupt:
        stop()
    _ensure_worker()
    _speech_queue.put(spoken)
    return True


def stop() -> None:
    if _current_stop is not None:
        _current_stop.set()
    try:
        while True:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
    except queue.Empty:
        pass


def status() -> dict:
    backend = "not_loaded"
    if _speaker is not None:
        backend = _speaker.backend_name
    return {
        "ok": True,
        "backend": backend,
        "speaking": _current_stop is not None,
        "queued": _speech_queue.qsize(),
    }


def start() -> dict:
    speaker = _get_speaker()
    _ensure_worker()
    result = status()
    result["backend"] = speaker.backend_name
    return result
