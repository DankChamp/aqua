from typing import Optional

import httpx

from .base import AIProvider, CompletionResult


class LocalGenericProvider(AIProvider):
    name = "local_generic"

    def __init__(self, base_url: Optional[str], default_model: Optional[str], api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.default_model = default_model
        self.api_key = api_key

    async def is_available(self) -> bool:
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models", headers=self._headers())
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        if not self.base_url:
            return []
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except httpx.HTTPError:
            return []

    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        if not self.base_url:
            raise RuntimeError("Local provider called with no base URL configured")

        model = kwargs.get("model", self.default_model)
        if not model:
            raise RuntimeError("No model set for the local provider. Set LOCAL_DEFAULT_MODEL in .env")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/v1/chat/completions", json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        return CompletionResult(text=text, provider=self.name, model=model, raw=data)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key or 'not-needed'}"}
