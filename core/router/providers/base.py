from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Optional


@dataclass
class CompletionResult:
    text: str
    provider: str
    model: str
    raw: Optional[dict] = None


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> CompletionResult:
        raise NotImplementedError

    async def stream(self, prompt: str, system: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        result = await self.complete(prompt, system=system, **kwargs)
        yield result.text
