from typing import Optional

import httpx

from .base import AIProvider, CompletionResult


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str, default_model: str):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        model = kwargs.get("model", self.default_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages, "stream": False}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data.get("message", {}).get("content", "")
        return CompletionResult(text=text, provider=self.name, model=model, raw=data)
