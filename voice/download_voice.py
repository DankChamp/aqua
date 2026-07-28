#!/usr/bin/env python3
"""
Fetch a natural, feminine neural voice for Emma (Piper).

This is the one step that touches the network - it downloads a small
voice model (~30-75MB) once. After that, Emma speaks entirely offline;
nothing you say and nothing she says ever leaves the machine.

Usage:
    python voice/download_voice.py                 # default feminine voice (Amy)
    python voice/download_voice.py --voice jenny   # a warm British-English voice
    python voice/download_voice.py --list          # show the curated voices
    python voice/download_voice.py --all           # grab every curated voice

Models land in voice/models/ and are auto-discovered at runtime, so once a
voice is here you don't have to configure anything - just run the assistant.
Browse the full catalogue at https://huggingface.co/rhasspy/piper-voices
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# A small, opinionated set of pleasant feminine English voices. The `path`
# is the voice's location within the piper-voices repo; both the .onnx model
# and its .onnx.json config live there.
CURATED = {
    "amy": {
        "path": "en/en_US/amy/medium/en_US-amy-medium",
        "desc": "US English, warm and clear (default). ~63MB.",
    },
    "hfc_female": {
        "path": "en/en_US/hfc_female/medium/en_US-hfc_female-medium",
        "desc": "US English, bright and articulate. ~63MB.",
    },
    "libritts": {
        "path": "en/en_US/libritts/high/en_US-libritts-high",
        "desc": "US English, high quality, expressive (multi-speaker). ~120MB.",
    },
    "jenny": {
        "path": "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium",
        "desc": "British English, soft and natural. ~63MB.",
    },
    "kathleen": {
        "path": "en/en_US/kathleen/low/en_US-kathleen-low",
        "desc": "US English, gentle, very small/fast. ~28MB.",
    },
}
DEFAULT_VOICE = "amy"


def _download(url: str, dest: Path) -> None:
    print(f"  -> {dest.name}")

    def _progress(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = min(block_num * block_size, total_size)
        pct = done * 100 // total_size
        bar = "#" * (pct // 4)
        sys.stdout.write(f"\r     [{bar:<25}] {pct:3d}%  ({done // 1_000_000}/{total_size // 1_000_000} MB)")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, _progress)  # noqa: S310 - fixed, trusted HTTPS host
    sys.stdout.write("\n")


def fetch_voice(key: str) -> bool:
    voice = CURATED.get(key)
    if not voice:
        print(f"Unknown voice {key!r}. Use --list to see the options.", file=sys.stderr)
        return False

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    name = voice["path"].rsplit("/", 1)[-1]  # e.g. en_US-amy-medium
    onnx = MODELS_DIR / f"{name}.onnx"
    cfg = MODELS_DIR / f"{name}.onnx.json"

    if onnx.exists() and cfg.exists():
        print(f"'{key}' ({name}) is already installed - skipping.")
        return True

    print(f"Downloading '{key}' ({name})...")
    try:
        _download(f"{HF_BASE}/{voice['path']}.onnx", onnx)
        _download(f"{HF_BASE}/{voice['path']}.onnx.json", cfg)
    except Exception as exc:  # noqa: BLE001 - report cleanly, don't leave half a file
        print(f"\nDownload failed: {exc}", file=sys.stderr)
        for partial in (onnx, cfg):
            if partial.exists() and partial.stat().st_size == 0:
                partial.unlink()
        return False

    print(f"Done. '{name}' is ready in {MODELS_DIR.relative_to(Path.cwd()) if MODELS_DIR.is_relative_to(Path.cwd()) else MODELS_DIR}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a feminine neural voice for Emma (Piper).")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Which curated voice (default: {DEFAULT_VOICE})")
    parser.add_argument("--list", action="store_true", help="List the curated voices and exit")
    parser.add_argument("--all", action="store_true", help="Download every curated voice")
    args = parser.parse_args()

    if args.list:
        print("Curated feminine voices for Emma:\n")
        for key, v in CURATED.items():
            default = "  (default)" if key == DEFAULT_VOICE else ""
            print(f"  {key:<12} {v['desc']}{default}")
        print("\nInstall one with:  python voice/download_voice.py --voice <name>")
        return 0

    if args.all:
        ok = all(fetch_voice(key) for key in CURATED)
        return 0 if ok else 1

    ok = fetch_voice(args.voice)
    if ok:
        print("\nAqua now has a natural voice. Start with: python aqua_voice.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
