from fastapi import APIRouter
from pydantic import BaseModel

from core.activity import get_activity, add_activity

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityCreate(BaseModel):
    action: str = ""
    detail: str = ""
    class_std: str = ""
    subject: str = ""
    chapter: str = ""


@router.get("")
def activity(limit: int = 20):
    return get_activity(limit=limit)


@router.post("")
def log_activity(payload: ActivityCreate):
    add_activity(
        action=payload.action,
        detail=payload.detail,
        class_std=payload.class_std,
        subject=payload.subject,
        chapter=payload.chapter,
    )
    return {"ok": True}
