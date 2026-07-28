from fastapi import APIRouter
from pydantic import BaseModel

from core.deps import get_db
from core.profile import manager as profile_mgr

router = APIRouter(prefix="/api/facts", tags=["facts"])


class FactBody(BaseModel):
    fact: str
    tags: list[str] = []


@router.post("")
def ingest_fact(payload: FactBody):
    tags_str = ", ".join(payload.tags) if payload.tags else "general"
    key = f"fact_{payload.tags[0]}" if payload.tags else "fact_general"
    profile_mgr.set(key, payload.fact, category="user_facts")
    return {"ok": True, "fact": payload.fact}


@router.get("")
def list_facts():
    conn = get_db()
    rows = conn.execute(
        "SELECT key, value FROM profile WHERE category = 'user_facts' ORDER BY key"
    ).fetchall()
    return [{"key": r["key"], "value": r["value"]} for r in rows] if rows else []
