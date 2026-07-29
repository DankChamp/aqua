from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from config import get_settings, update_env_file
from core.router import AIRouter

router = APIRouter(prefix="/settings", tags=["settings"])


class EnvUpdate(BaseModel):
    updates: dict[str, str]


@router.get("")
def get_settings_route():
    s = get_settings()
    safe = {k: v for k, v in s.model_dump().items() if "key" not in k.lower() and "password" not in k.lower()}
    safe["has_password"] = bool(s.web_password)
    safe["has_groq_key"] = bool(s.groq_api_key)
    safe["has_nvidia_key"] = bool(s.nvidia_api_key)
    safe["has_openai_key"] = bool(s.openai_api_key)
    safe["has_anthropic_key"] = bool(s.anthropic_api_key)
    safe["has_google_key"] = bool(s.google_api_key)
    return safe


@router.post("/env")
def update_env(payload: EnvUpdate):
    update_env_file(payload.updates)
    from core.deps import get_router
    get_router.cache_clear()
    return {"ok": True}


@router.get("/providers")
async def get_providers(ai_router: AIRouter = Depends(get_ai_router)):
    return await ai_router.provider_status()


class TaskTypeInfo(BaseModel):
    name: str
    description: str


@router.get("/task-types")
def get_task_types():
    return [
        {"name": "conversation", "description": "General conversation"},
        {"name": "reasoning", "description": "Complex multi-step reasoning"},
        {"name": "creative", "description": "Creative writing and brainstorming"},
        {"name": "general", "description": "General assistant tasks"},
        {"name": "research", "description": "Research and analysis"},
        {"name": "study", "description": "Study and learning assistance"},
    ]
