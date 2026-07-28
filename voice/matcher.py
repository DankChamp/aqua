"""
Wake-word matching - pulled out into its own pure-function module so it
can be unit tested without a microphone or a Vosk model on hand.

Offline speech recognition on a two-word wake phrase is noisy: "hey emma"
comes back from Vosk as things like "hey emma", "a emma", "hey emmer", or
"heyemma" depending on the speaker and the model. Rather than requiring an
exact match, we score a sliding window of the transcript against the wake
phrase and accept anything close enough.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def contains_wake_word(transcript: str, wake_word: str, threshold: float = 0.70) -> bool:
    """
    True if `transcript` plausibly contains `wake_word` somewhere in it.

    Strategy: normalize both strings, then slide a window of the wake
    word's word-count (plus a little slack for STT insertions/omissions)
    across the transcript and take the best fuzzy-match score. This
    tolerates single mis-transcribed words ("hey emmer") and small
    word-count drift ("ok hey emma") without accepting unrelated speech.
    """
    wake_norm = normalize(wake_word)
    transcript_norm = normalize(transcript)
    if not wake_norm or not transcript_norm:
        return False

    # Fast path: literal substring match (the common case when Vosk gets
    # it right, which is most of the time for a short, distinct phrase).
    if wake_norm in transcript_norm:
        return True

    words = transcript_norm.split()
    wake_len = len(wake_norm.split())

    best = 0.0
    # Slide windows from wake_len-1 to wake_len+1 words to absorb a
    # dropped or inserted filler word ("a", "hey", "um").
    for span in range(max(1, wake_len - 1), wake_len + 2):
        for start in range(0, max(1, len(words) - span + 1)):
            window = " ".join(words[start : start + span])
            best = max(best, _similarity(window, wake_norm))

    return best >= threshold
