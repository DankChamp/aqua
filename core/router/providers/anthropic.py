from typing import Optional

import httpx

from .base import AIProvider, CompletionResult

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str], default_model: str):
        self.api_key = api_key
        self.default_model = default_model

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        if not self.api_key:
            raise RuntimeError("Anthropic provider called with no API key configured")

        model = kwargs.get("model", self.default_model)
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": model, "messages": messages, "max_tokens": 4096}
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data["content"][0]["text"]
        return CompletionResult(text=text, provider=self.name, model=model, raw=data)
