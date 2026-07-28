"""
Aqua Voice - a wake-word + speech front end.

This is just another client of Aqua's HTTP API. It never imports from
core/ directly. Everything runs fully on the local machine:
  - wake-word + command transcription: Vosk (offline speech recognition)
  - reply playback: Piper TTS or pyttsx3 fallback

No audio ever leaves the machine except as text sent to whatever AI
provider Aqua's router picks for the reply (which can be a fully local
model).
"""
