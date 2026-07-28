#!/usr/bin/env python3
import argparse
import logging
import sys

from config import get_settings


def _list_input_devices():
    from voice.wake_word import _require_sounddevice
    sd = _require_sounddevice()
    print("Available input devices (use the name or index with --device):\n")
    for idx, device in enumerate(sd.query_devices()):
        if device.get("max_input_channels", 0) > 0:
            print(f"  [{idx}] {device['name']}")


def _list_voices():
    from voice.tts import Speaker
    voices = Speaker.list_voices()
    if not voices:
        print("No TTS voices found yet.")
        print("Get a natural voice with:  python voice/download_voice.py")
        return
    piper = [v for v in voices if v.get("engine") == "piper"]
    system = [v for v in voices if v.get("engine") != "piper"]
    if piper:
        print("Piper neural voices:\n")
        for voice in piper:
            print(f"  {voice['name']}")
        print()
    else:
        print("No Piper voice installed yet.")
        print("Get a natural voice with:  python voice/download_voice.py\n")
    if system:
        print("System voices:\n")
        for voice in system:
            print(f"  {voice['name']}  ({voice['id']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aqua wake-word voice front end.")
    parser.add_argument("--wake-word", help='Override the wake phrase (default: from .env)')
    parser.add_argument("--backend-url", help="Override Aqua's backend URL")
    parser.add_argument("--device", help="Microphone device name or index")
    parser.add_argument("--engine", choices=["auto", "piper", "pyttsx3"], help="TTS engine")
    parser.add_argument("--piper-model", help="Piper voice model path or name")
    parser.add_argument("--length-scale", type=float, help="Piper pacing: 1.0 natural")
    parser.add_argument("--voice", help="Fallback system-voice name substring")
    parser.add_argument("--no-ack", action="store_true", help="Skip spoken acknowledgement")
    parser.add_argument("--no-barge-in", action="store_true", help="Disable barge-in")
    parser.add_argument("--list-devices", action="store_true", help="List microphones and exit")
    parser.add_argument("--list-voices", action="store_true", help="List installed voices and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_devices:
        _list_input_devices()
        return 0
    if args.list_voices:
        _list_voices()
        return 0

    settings = get_settings()

    from voice.assistant import VoiceAssistant
    from voice.wake_word import VoiceDependencyError

    wake_word = args.wake_word or settings.voice_wake_word
    print(f'Listening for "{wake_word}"... (Ctrl+C to stop)')

    try:
        assistant = VoiceAssistant(
            backend_url=args.backend_url or settings.voice_backend_url,
            wake_word=wake_word,
            vosk_model_path=settings.voice_vosk_model_path,
            input_device=args.device or settings.voice_input_device,
            tts_rate=settings.voice_tts_rate,
            tts_voice=args.voice or settings.voice_tts_voice,
            tts_engine=args.engine or settings.voice_tts_engine,
            piper_model_path=args.piper_model or settings.voice_piper_model_path,
            piper_length_scale=args.length_scale if args.length_scale is not None else settings.voice_piper_length_scale,
            piper_noise_scale=settings.voice_piper_noise_scale,
            piper_noise_w_scale=settings.voice_piper_noise_w_scale,
            piper_volume=settings.voice_piper_volume,
            piper_speaker_id=settings.voice_piper_speaker_id,
            command_timeout=settings.voice_command_timeout_seconds,
            silence_seconds=settings.voice_silence_seconds,
            speak_acknowledgement=not args.no_ack,
            barge_in=settings.voice_barge_in and not args.no_barge_in,
            on_state_change=lambda state: print(f"[{state}]"),
        )
    except VoiceDependencyError as exc:
        print(f"\nCan't start voice mode yet: {exc}", file=sys.stderr)
        return 1

    try:
        assistant.run_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
