from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
