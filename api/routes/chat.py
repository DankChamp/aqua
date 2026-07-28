from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_ai_router
from core.chat.memory import add_message, get_history, clear_session, list_sessions
from core.profile import manager as profile_mgr
from core.router import AIRouter, TaskType

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
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
    add_message(payload.session_id, "user", payload.message)

    parts = []

    custom_prompt = profile_mgr.get_system_prompt()
    if custom_prompt:
        parts.append(custom_prompt)

    profile_block = profile_mgr.to_context_block()
    if profile_block:
        parts.append(profile_block)

    history = get_history(payload.session_id)
    if history:
        history_block = "Conversation so far:\n" + "\n".join(
            f"{m['role']}: {m['content']}" for m in history
        )
        parts.append(history_block)

    from core.search.vector import search_chunks
    try:
        chunks = search_chunks(payload.message, top_k=3)
        if chunks:
            ctx = "Relevant knowledge:\n" + "\n---\n".join(
                f"[{c.get('source','?')}] {c.get('title','')}: {c.get('text','')}" for c in chunks
            )
            parts.append(ctx)
    except Exception:
        pass

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

    add_message(payload.session_id, "assistant", result.text)
    return ChatResponse(reply=result.text, provider=result.provider, model=result.model)


@router.get("/sessions")
def sessions():
    return list_sessions()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    clear_session(session_id)
    return {"ok": True}
