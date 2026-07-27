import os
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "data_dir": str(Path.home() / ".aqua" / "data"),
    "db_path": str(Path.home() / ".aqua" / "aqua.db"),
    "chroma_path": str(Path.home() / ".aqua" / "chroma"),
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": None,
    },
    "embeddings": {
        "provider": "sentence-transformers",
        "model": "all-MiniLM-L6-v2",
    },
}


def load_config(config_path: str | None = None) -> dict:
    if config_path is None:
        config_path = str(Path.home() / ".aqua" / "config.yaml")

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    config = DEFAULT_CONFIG.copy()
    config.update(user_config)

    if config["llm"]["api_key"] is None:
        config["llm"]["api_key"] = os.environ.get("OPENAI_API_KEY")

    return config
