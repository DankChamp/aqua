from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from core.router import AIRouter
from core.documents.manager import (
    add_note, get_note, list_notes, search_notes, edit_note, delete_note,
    list_subjects, list_chapters, generate_note,
)
from core.documents.models import NOTE_TYPES

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    content: str
    title: str = ""
    document_id: Optional[int] = None
    class_std: str = ""
    subject: str = ""
    chapter: str = ""
    note_type: str = ""


class NoteEdit(BaseModel):
    content: str
    title: Optional[str] = None
    class_std: Optional[str] = None
    subject: Optional[str] = None
    chapter: Optional[str] = None
    note_type: Optional[str] = None


class GenerateRequest(BaseModel):
    class_std: str
    subject: str
    chapter: str
    document_ids: list[int] = []
    note_type: str = "detailed"


@router.post("/generate")
async def generate(payload: GenerateRequest, ai_router: AIRouter = Depends(get_ai_router)):
    try:
        note = await generate_note(
            class_std=payload.class_std,
            subject=payload.subject,
            chapter=payload.chapter,
            document_ids=payload.document_ids or None,
            note_type=payload.note_type,
        )
        return note
    except Exception as exc:
        raise HTTPException(503, f"Note generation failed: {exc}")


@router.post("")
async def create_note(payload: NoteCreate):
    note = add_note(
        content=payload.content, title=payload.title,
        document_id=payload.document_id,
        class_std=payload.class_std, subject=payload.subject, chapter=payload.chapter,
        note_type=payload.note_type,
    )
    try:
        title = payload.title or "untitled"
        from core.emma_bridge import push_summary_to_emma
        await push_summary_to_emma("note", title, payload.content[:200])
    except Exception:
        pass
    return note


@router.get("")
def list_note(document_id: Optional[int] = None, limit: int = 50,
              class_std: Optional[str] = None, subject: Optional[str] = None,
              chapter: Optional[str] = None, note_type: Optional[str] = None):
    return list_notes(document_id=document_id, limit=limit,
                      class_std=class_std, subject=subject, chapter=chapter,
                      note_type=note_type)


@router.get("/subjects")
def subjects(class_std: Optional[str] = None):
    return list_subjects(class_std=class_std)


@router.get("/chapters")
def chapters(class_std: str, subject: str):
    return list_chapters(class_std, subject)


@router.get("/note-types")
def note_types():
    return NOTE_TYPES


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
    note = edit_note(note_id, payload.content, title=payload.title,
                     class_std=payload.class_std, subject=payload.subject,
                     chapter=payload.chapter, note_type=payload.note_type)
    if not note:
        raise HTTPException(404, "Note not found")
    return note


@router.delete("/{note_id}")
def delete_note_route(note_id: int):
    if not delete_note(note_id):
        raise HTTPException(404, "Note not found")
    return {"ok": True}
