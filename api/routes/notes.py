from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.documents.manager import add_note, get_note, list_notes, search_notes, edit_note, delete_note

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    content: str
    title: str = ""
    document_id: Optional[int] = None


class NoteEdit(BaseModel):
    content: str
    title: Optional[str] = None


@router.post("")
async def create_note(payload: NoteCreate):
    note = add_note(content=payload.content, title=payload.title, document_id=payload.document_id)
    try:
        title = payload.title or "untitled"
        from core.emma_bridge import push_summary_to_emma
        await push_summary_to_emma("note", title, payload.content[:200])
    except Exception:
        pass
    return note


@router.get("")
def list_note(document_id: Optional[int] = None, limit: int = 50):
    return list_notes(document_id=document_id, limit=limit)


@router.get("/{note_id}")
def get_note_route(note_id: int):
    note = get_note(note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    return note


@router.get("/search/{query}")
def search_note(query: str, limit: int = 20):
    return search_notes(query, limit=limit)


@router.put("/{note_id}")
def update_note(note_id: int, payload: NoteEdit):
    note = edit_note(note_id, payload.content, title=payload.title)
    if not note:
        raise HTTPException(404, "Note not found")
    return note


@router.delete("/{note_id}")
def delete_note_route(note_id: int):
    if not delete_note(note_id):
        raise HTTPException(404, "Note not found")
    return {"ok": True}
