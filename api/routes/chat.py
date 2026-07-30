import asyncio
import json
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_ai_router
from core.agent.engine import run_agent, build_system_prompt
from core.chat.memory import add_message, get_history, clear_session, list_session_details, get_session_messages, edit_message, delete_message
from core.profile import manager as profile_mgr
from core.router import AIRouter, TaskType
from core.study.ncert import get_context_block as ncert_block

logger = logging.getLogger("aqua.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    task_type: TaskType = TaskType.CONVERSATION
    system: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    agentic: bool = False
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    agent_used: bool = False
    session_id: str = "default"


async def _build_system_parts(payload: ChatRequest) -> list[str]:
    AQUA_INSTRUCTIONS = (
        "You are Aqua, a sharp and efficient research & study assistant. "
        "Always use Markdown formatting. NEVER output HTML tags like <br>, "
        "<table>, <b>, or any other HTML. For tables use | pipes |, for "
        "line breaks just use a blank line, for bold use **double stars**, "
        "for lists use - dashes, for code use backticks. "
        "Be conversational, not academic. Use short paragraphs, bullet points, "
        "or simple lists to keep responses scannable. Never write a huge wall "
        "of text unless the user explicitly asks for depth. If you use web or "
        "knowledge sources, briefly cite them. Adapt your tone to the user."
        " When discussing academic topics, ALWAYS look up and reference NCERT "
        "book chapters and topics. Align explanations with the NCERT curriculum."
    )

    parts = [AQUA_INSTRUCTIONS]

    custom_prompt = profile_mgr.get_system_prompt()
    if custom_prompt:
        parts.append(custom_prompt)

    profile_block = profile_mgr.to_context_block()
    if profile_block:
        parts.append(profile_block)

    cls = profile_mgr.get("class_std") or ""
    subj = profile_mgr.get("subject") or ""
    ch = profile_mgr.get("chapter") or ""
    if cls and subj:
        ncert = ncert_block(cls, subj, ch)
        if ncert:
            parts.append(ncert)

    history = get_history(payload.session_id)
    if history:
        history_block = "Conversation so far:\n" + "\n".join(
            f"{m['role']}: {m['content']}" for m in history
        )
        parts.append(history_block)

    from core.search.vector import search_chunks
    try:
        chunks = await asyncio.to_thread(search_chunks, payload.message, 3)
        if chunks:
            lines = []
            for c in chunks:
                src = c.get("source", "?")
                title = c.get("title", "")
                text = c.get("text", "")
                lines.append(f"[{src}] {title}: {text[:500]}")
            parts.append("Knowledge base:\n" + "\n".join(lines))
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)

    from core.web.search import search_duckduckgo
    try:
        web_results = await asyncio.to_thread(search_duckduckgo, payload.message, 3)
        if web_results:
            lines = []
            for r in web_results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                url = r.get("url", "")
                lines.append(f"[Web] {title}: {snippet[:300]} ({url})")
            parts.append("Latest web results:\n" + "\n".join(lines))
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)

    if payload.system:
        parts.append(payload.system)

    return parts


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, ai_router: AIRouter = Depends(get_ai_router)):
    add_message(payload.session_id, "user", payload.message)

    parts = await _build_system_parts(payload)

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
        return ChatResponse(reply=reply, provider="agent", model="agent", agent_used=True, session_id=payload.session_id)

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
    return ChatResponse(reply=result.text, provider=result.provider, model=result.model, session_id=payload.session_id)


@router.post("/stream")
async def chat_stream(payload: ChatRequest, ai_router: AIRouter = Depends(get_ai_router)):
    add_message(payload.session_id, "user", payload.message)

    parts = await _build_system_parts(payload)

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
        return ChatResponse(reply=reply, provider="agent", model="agent", agent_used=True, session_id=payload.session_id)

    system = "\n\n".join(parts) if parts else None

    async def event_stream():
        full = ""
        try:
            async for chunk in ai_router.stream(
                payload.task_type,
                payload.message,
                system=system,
                model=payload.model,
                provider_name=payload.provider,
            ):
                full += chunk
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True, 'full': full})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return
        add_message(payload.session_id, "assistant", full)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/models")
async def list_models(ai_router: AIRouter = Depends(get_ai_router)):
    result = {}
    async def fetch_ollama():
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(ai_router.settings.ollama_base_url.rstrip("/") + "/api/tags")
                r.raise_for_status()
                data = r.json()
                result["ollama"] = [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            logger.debug("Ollama model fetch failed: %s", exc)
            result["ollama"] = []

    async def fetch_groq():
        try:
            if not ai_router.settings.groq_api_key:
                result["groq"] = []; return
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.groq.com/openai/v1/models",
                                headers={"Authorization": f"Bearer {ai_router.settings.groq_api_key}"})
                r.raise_for_status()
                data = r.json()
                result["groq"] = sorted(set(m["id"] for m in data.get("data", [])))
        except Exception as exc:
            logger.debug("Groq model fetch failed: %s", exc)
            result["groq"] = []

    async def fetch_openai():
        try:
            if not ai_router.settings.openai_api_key:
                result["openai"] = []; return
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.openai.com/v1/models",
                                headers={"Authorization": f"Bearer {ai_router.settings.openai_api_key}"})
                r.raise_for_status()
                data = r.json()
                result["openai"] = sorted(set(m["id"] for m in data.get("data", [])))
        except Exception as exc:
            logger.debug("OpenAI model fetch failed: %s", exc)
            result["openai"] = []

    async def fetch_nvidia():
        try:
            if not ai_router.settings.nvidia_api_key:
                result["nvidia"] = []; return
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://integrate.api.nvidia.com/v1/models",
                                headers={"Authorization": f"Bearer {ai_router.settings.nvidia_api_key}"})
                r.raise_for_status()
                data = r.json()
                result["nvidia"] = sorted(set(m["id"] for m in data.get("data", [])))
        except Exception as exc:
            logger.debug("NVIDIA model fetch failed: %s", exc)
            result["nvidia"] = []

    await asyncio.gather(fetch_ollama(), fetch_groq(), fetch_openai(), fetch_nvidia())
    return result


@router.get("/sessions")
def sessions():
    return list_session_details()


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return get_session_messages(session_id)


@router.post("/sessions/{session_id}/rename")
def rename_session(session_id: str, body: dict):
    from core.chat.memory import rename_session as do_rename
    name = body.get("name", "").strip()
    if name:
        do_rename(session_id, name)
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    clear_session(session_id)
    return {"ok": True}


class EditMessage(BaseModel):
    content: str


@router.put("/messages/{message_id}")
def edit_chat_message(message_id: int, body: EditMessage):
    if not edit_message(message_id, body.content):
        raise HTTPException(404, "Message not found")
    return {"ok": True}


@router.delete("/messages/{message_id}")
def delete_chat_message(message_id: int):
    if not delete_message(message_id):
        raise HTTPException(404, "Message not found")
    return {"ok": True}
