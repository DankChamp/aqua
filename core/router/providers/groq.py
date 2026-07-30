import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from .base import AIProvider, CompletionResult

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

logger = logging.getLogger("aqua.providers.groq")


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, api_key: Optional[str], default_model: str):
        self.api_key = api_key
        self.default_model = default_model

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        if not self.api_key:
            raise RuntimeError("Groq provider called with no API key configured")

        model = kwargs.get("model", self.default_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": model, "messages": messages}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GROQ_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            logger.warning("Groq returned empty content; response keys: %s", list(data.keys()))
            text = ""
        return CompletionResult(text=text, provider=self.name, model=model, raw=data)

    async def stream(self, prompt: str, system: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise RuntimeError("Groq provider called with no API key configured")

        model = kwargs.get("model", self.default_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": model, "messages": messages, "stream": True}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", GROQ_API_URL, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
