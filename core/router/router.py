import logging
from enum import Enum
from typing import Optional

import httpx

from config import Settings
from .providers import (
    AIProvider, CompletionResult,
    OllamaProvider, LocalGenericProvider,
    GroqProvider, NvidiaProvider,
    OpenAIProvider, AnthropicProvider,
)

logger = logging.getLogger("aqua.router")


class TaskType(str, Enum):
    CONVERSATION = "conversation"
    REASONING = "reasoning"
    CREATIVE = "creative"
    GENERAL = "general"
    RESEARCH = "research"
    STUDY = "study"


class AIRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

        self._ollama = OllamaProvider(settings.ollama_base_url, settings.ollama_default_model)
        self._local = LocalGenericProvider(
            settings.local_base_url, settings.local_default_model, settings.local_api_key
        )
        self._groq = GroqProvider(settings.groq_api_key, settings.groq_default_model)
        self._nvidia = NvidiaProvider(settings.nvidia_api_key, settings.nvidia_default_model)
        self._openai = OpenAIProvider(settings.openai_api_key, settings.openai_default_model)
        self._anthropic = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_default_model)

        self._local_providers = [self._ollama, self._local]

        self._routing_table: dict[TaskType, list[AIProvider]] = {
            TaskType.CONVERSATION: [self._ollama, self._local, self._groq, self._openai],
            TaskType.GENERAL: [self._groq, self._ollama, self._local, self._openai],
            TaskType.REASONING: [self._nvidia, self._groq, self._anthropic, self._openai, self._ollama, self._local],
            TaskType.CREATIVE: [self._groq, self._openai, self._ollama, self._local],
            TaskType.RESEARCH: [self._groq, self._nvidia, self._openai, self._ollama, self._local],
            TaskType.STUDY: [self._groq, self._ollama, self._local, self._openai],
        }

        if settings.prefer_local_when_available:
            for task, providers in self._routing_table.items():
                locals_present = [p for p in self._local_providers if p in providers]
                others = [p for p in providers if p not in self._local_providers]
                providers[:] = locals_present + others

        global_fallback = [self._ollama, self._local, self._groq, self._nvidia, self._openai, self._anthropic]
        for task, providers in self._routing_table.items():
            for provider in global_fallback:
                if provider not in providers:
                    providers.append(provider)

        self.providers_by_name: dict[str, AIProvider] = {
            self._ollama.name: self._ollama,
            self._local.name: self._local,
            self._groq.name: self._groq,
            self._nvidia.name: self._nvidia,
            self._openai.name: self._openai,
            self._anthropic.name: self._anthropic,
        }

    async def provider_status(self) -> list[dict]:
        status = []
        for name, provider in self.providers_by_name.items():
            if provider is self._local:
                configured = bool(getattr(provider, "base_url", None))
            else:
                configured = bool(getattr(provider, "api_key", True))
            available = await provider.is_available()
            status.append({
                "name": name,
                "configured": configured,
                "default_model": getattr(provider, "default_model", None),
                "available": available,
            })
        return status

    def _candidates(self, task: TaskType) -> list[AIProvider]:
        return self._routing_table.get(task, list(self.providers_by_name.values()))

    async def run(
        self,
        task: TaskType,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> CompletionResult:
        if provider_name:
            provider = self.providers_by_name.get(provider_name)
            if provider is None:
                raise RuntimeError(f"Unknown provider '{provider_name}'.")
            kwargs = {"model": model} if model else {}
            try:
                return await provider.complete(prompt, system=system, **kwargs)
            except Exception as exc:
                raise RuntimeError(f"Provider '{provider_name}' couldn't answer: {self._describe_error(exc)}") from exc

        candidates = self._candidates(task)
        errors: list[str] = []
        tried_any = False

        for provider in candidates:
            try:
                if not await provider.is_available():
                    continue
            except Exception as exc:
                errors.append(f"{provider.name}: {self._describe_error(exc)}")
                continue

            tried_any = True
            kwargs = {"model": model} if model else {}
            try:
                result = await provider.complete(prompt, system=system, **kwargs)
                if not (result.text and result.text.strip()):
                    raise RuntimeError("provider returned an empty response")
                if errors:
                    logger.info("Aqua fell back to %s after: %s", provider.name, "; ".join(errors))
                return result
            except Exception as exc:
                msg = self._describe_error(exc)
                logger.warning("Provider %s failed (%s); trying next.", provider.name, msg)
                errors.append(f"{provider.name}: {msg}")
                continue

        if not tried_any and not errors:
            raise RuntimeError(
                f"No AI provider is available for '{task.value}'. Start Ollama, "
                "point Aqua at a local server, or add a working cloud API key."
            )

        detail = "; ".join(errors) if errors else "all providers unavailable"
        raise RuntimeError(
            f"Aqua tried every provider for '{task.value}' but none could answer "
            f"({detail}). Check your API keys and models."
        )

    @staticmethod
    def _describe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            reasons = {
                401: "invalid or missing API key",
                403: "API key rejected (403 - check the key is valid)",
                404: "model not found (check the default model name)",
                429: "rate limited - too many requests",
            }
            if code in reasons:
                return reasons[code]
            if code >= 500:
                return f"provider server error ({code})"
            return f"HTTP {code}"
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return "could not connect (is the server running / online?)"
        if isinstance(exc, httpx.TimeoutException):
            return "timed out"
        return str(exc) or exc.__class__.__name__
