from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aqua"
    debug: bool = True

    db_path: Path = DATA_DIR / "aqua.db"

    groq_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    openai_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"))
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    ollama_base_url: str = "http://localhost:11434"
    local_base_url: Optional[str] = None
    local_api_key: Optional[str] = None
    local_default_model: Optional[str] = None

    ollama_default_model: str = "llama3.2:3b"
    groq_default_model: str = "llama-3.3-70b-versatile"
    nvidia_default_model: str = "meta/llama-3.1-8b-instruct"
    openai_default_model: str = "gpt-4o-mini"
    anthropic_default_model: str = "claude-3-haiku-20240307"
    google_default_model: str = "gemini-2.0-flash-exp"

    prefer_local_when_available: bool = True

    web_password: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("WEB_PASSWORD", "AQUA_WEB_PASSWORD"),
    )
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    emma_api_url: str = ""
    emma_api_key: str = ""

    voice_wake_word: str = "hey aqua"
    voice_backend_url: str = "http://127.0.0.1:8000"
    voice_vosk_model_path: Optional[str] = None
    voice_input_device: Optional[str] = None
    voice_command_timeout_seconds: float = 8.0
    voice_silence_seconds: float = 1.2
    voice_barge_in: bool = True
    voice_tts_engine: str = "auto"
    voice_piper_model_path: Optional[str] = None
    voice_piper_length_scale: float = 1.02
    voice_piper_noise_scale: float = 0.667
    voice_piper_noise_w_scale: float = 0.8
    voice_piper_volume: float = 1.0
    voice_piper_speaker_id: Optional[int] = None
    voice_tts_rate: int = 175
    voice_tts_voice: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


ENV_PATH = BASE_DIR / ".env"


def update_env_file(updates: dict[str, str]) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key in remaining:
            new_lines.append(f"{existing_key}={remaining.pop(existing_key)}")
        else:
            new_lines.append(line)
    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")
    get_settings.cache_clear()
