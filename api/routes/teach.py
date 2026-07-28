from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from core.router import AIRouter
from core.teach.engine import start_session, end_session, get_session, list_sessions, teach

router = APIRouter(prefix="/teach", tags=["teach"])


class StartRequest(BaseModel):
    class_std: str
    subject: str
    chapter: str


class MessageRequest(BaseModel):
    message: str


@router.post("/start")
def teach_start(payload: StartRequest):
    session_id = start_session(payload.class_std, payload.subject, payload.chapter)
    return {"session_id": session_id, "class_std": payload.class_std, "subject": payload.subject, "chapter": payload.chapter}


@router.post("/{session_id}/message")
async def teach_message(session_id: str, payload: MessageRequest, ai_router: AIRouter = Depends(get_ai_router)):
    try:
        response = await teach(ai_router, session_id, payload.message)
        return {"response": response}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{session_id}/end")
def teach_end(session_id: str):
    end_session(session_id)
    return {"ok": True}


@router.get("/{session_id}")
def teach_get(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("")
def teach_list(limit: int = 20):
    return list_sessions(limit=limit)
