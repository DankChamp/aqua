from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_ai_router
from core.profile import manager as profile_mgr
from core.router import AIRouter, TaskType

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    task_type: TaskType = TaskType.CONVERSATION
    system: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, ai_router: AIRouter = Depends(get_ai_router)):
    parts = []

    custom_prompt = profile_mgr.get_system_prompt()
    if custom_prompt:
        parts.append(custom_prompt)

    profile_block = profile_mgr.to_context_block()
    if profile_block:
        parts.append(profile_block)

    if payload.system:
        parts.append(payload.system)

    system = "\n\n".join(parts) if parts else None

    try:
        result = await ai_router.run(
            payload.task_type,
            payload.message,
            system=system,
            model=payload.model,
            provider_name=payload.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(reply=result.text, provider=result.provider, model=result.model)
