from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_ai_router
from core.agent.engine import run_agent, build_system_prompt
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
    agentic: bool = False


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    agent_used: bool = False


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, ai_router: AIRouter = Depends(get_ai_router)):
    add_message(payload.session_id, "user", payload.message)

    AQUA_INSTRUCTIONS = (
        "You are Aqua, a sharp and efficient research & study assistant. "
        "Be conversational, not academic. Use short paragraphs, bullet points, "
        "or simple lists to keep responses scannable. Never write a huge wall "
        "of text unless the user explicitly asks for depth. If you use web or "
        "knowledge sources, briefly cite them. Adapt your tone to the user."
    )

    parts = [AQUA_INSTRUCTIONS]

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
            lines = []
            for c in chunks:
                src = c.get("source", "?")
                title = c.get("title", "")
                text = c.get("text", "")
                lines.append(f"[{src}] {title}: {text[:500]}")
            parts.append("Knowledge base:\n" + "\n".join(lines))
    except Exception:
        pass

    from core.web.search import search_duckduckgo
    try:
        web_results = search_duckduckgo(payload.message, max_results=3)
        if web_results:
            lines = []
            for r in web_results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                url = r.get("url", "")
                lines.append(f"[Web] {title}: {snippet[:300]} ({url})")
            parts.append("Latest web results:\n" + "\n".join(lines))
    except Exception:
        pass

    if payload.system:
        parts.append(payload.system)

    if payload.agentic:
        system = build_system_prompt(extra="\n\n".join(parts) if parts else None)
        try:
            reply = await run_agent(
                ai_router,
                payload.message,
                system=system,
                model=payload.model,
                provider_name=payload.provider,
                session_id=payload.session_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        add_message(payload.session_id, "assistant", reply)
        return ChatResponse(reply=reply, provider="agent", model="agent", agent_used=True)

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
