from typing import Optional

import httpx

from .base import AIProvider, CompletionResult

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str], default_model: str):
        self.api_key = api_key
        self.default_model = default_model

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        if not self.api_key:
            raise RuntimeError("OpenAI provider called with no API key configured")

        model = kwargs.get("model", self.default_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": model, "messages": messages}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OPENAI_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        return CompletionResult(text=text, provider=self.name, model=model, raw=data)
