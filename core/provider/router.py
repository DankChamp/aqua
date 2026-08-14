"""
Aqua Provider Routing

Independent provider routing with Emma hierarchical control.
Aqua maintains its own provider configuration but can be influenced by Emma.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any

from core.router import AIRouter, TaskType
from config import get_settings as get_aqua_settings
from core.providers.base import AIProvider, TextChunk, ToolCallBatch


@dataclass
class ProviderOverride:
    """Emma-provided provider override for Aqua."""
    provider_name: str
    model: str
    task_types: list[TaskType] = field(default_factory=list)
    expires_at: Optional[float] = None  # Unix timestamp


class AquaProviderRouter:
    """
    Aqua's independent provider router with Emma hierarchical control.
    
    Aqua maintains its own provider configuration and routing logic,
    but Emma can push temporary overrides for specific tasks.
    """
    
    def __init__(self, settings=None):
        self.settings = settings or get_aqua_settings()
        self._router = AIRouter(self.settings)
        self._emma_overrides: list[ProviderOverride] = []
        self._lock = asyncio.Lock()
    
    async def route(
        self,
        task_type: TaskType,
        message: str,
        system: str = "",
        model: Optional[str] = None,
        provider_name: Optional[str] = None,
        local_only: bool = False,
    ) -> Any:
        """Route a request to the appropriate provider with Emma override support."""
        
        # Check for Emma override
        override = await self._get_active_override(task_type)
        
        effective_provider = provider_name
        effective_model = model
        
        if override:
            if not provider_name:
                effective_provider = override.provider_name
            if not model:
                effective_model = override.model
        
        if local_only:
            # Filter to local providers only
            pass  # Router handles this
        
        return await self._router.run(
            task_type,
            message,
            system=system,
            model=effective_model,
            provider_name=effective_provider,
        )
    
    async def stream(
        self,
        task_type: TaskType,
        message: str,
        system: str = "",
        model: Optional[str] = None,
        provider_name: Optional[str] = None,
        local_only: bool = False,
    ):
        """Stream a response with Emma override support."""
        
        override = await self._get_active_override(task_type)
        
        effective_provider = provider_name
        effective_model = model
        
        if override:
            if not provider_name:
                provider_name = override.provider_name
            if not model:
                model = override.model
        
        async for chunk in self._router.stream(
            task_type,
            message,
            system=system,
            model=model,
            provider_name=provider_name,
        ):
            yield chunk
    
    async def _get_active_override(self, task_type: TaskType) -> Optional[ProviderOverride]:
        """Get active Emma override for task type."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            active = [
                o for o in self._emma_overrides
                if (not o.expires_at or o.expires_at > asyncio.get_event_loop().time()) and
                (not o.task_types or task_type in o.task_types)
            ]
            return active[0] if active else None
    
    async def apply_emma_override(self, override: ProviderOverride):
        """Apply an Emma-provided provider override."""
        async with self._lock:
            # Remove any existing override for same provider/task_types
            self._emma_overrides = [
                o for o in self._emma_overrides
                if not (o.provider_name == override.provider_name and
                       set(o.task_types) & set(override.task_types))
            ]
            self._emma_overrides.append(override)
    
    async def clear_emma_overrides(self, provider_name: Optional[str] = None):
        """Clear Emma overrides, optionally for specific provider."""
        async with self._lock:
            if provider_name:
                self._emma_overrides = [
                    o for o in self._emma_overrides
                    if o.provider_name != provider_name
                ]
            else:
                self._emma_overrides.clear()
    
    def get_active_overrides(self) -> list[ProviderOverride]:
        """Get all active overrides."""
        return list(self._emma_overrides)
    
    async def provider_status(self) -> dict:
        """Get provider status including active overrides."""
        status = await self._router.provider_status()
        
        overrides = await self.get_active_overrides()
        for provider in status.get("providers", []):
            provider_name = provider.get("name", "")
            for override in overrides:
                if override.provider_name == provider_name:
                    provider["emma_override"] = {
                        "model": override.model,
                        "task_types": [t.value for t in override.task_types],
                        "expires_at": override.expires_at,
                    }
        
        return status
    
    def get_available_models(self, provider: str) -> list[str]:
        """Get available models for a provider."""
        return self._router.get_available_models(provider)
    
    async def set_active_provider(self, name: str, model: Optional[str] = None):
        """Set active provider (Aqua's own config)."""
        await self._router.set_active(name, model)
    
    async def get_provider(self, name: Optional[str] = None):
        """Get provider instance."""
        return await self._router.get_provider(name)


# Global instance
_aqua_router: Optional[AquaProviderRouter] = None


def get_aqua_router() -> AquaProviderRouter:
    """Get or create the global Aqua provider router."""
    global _aqua_router
    if _aqua_router is None:
        _aqua_router = AquaProviderRouter()
    return _aqua_router