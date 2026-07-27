from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.documents.manager import (
    add_document, get_document, list_documents,
    search_documents, delete_document,
)
from core.documents.models import Document

router = APIRouter(prefix="/documents", tags=["documents"])


class DocCreate(BaseModel):
    title: str
    content: str = ""
    authors: str = ""
    source: str = "manual"
    source_url: str = ""
    file_path: str = ""
    summary: str = ""
    tags: list[str] = []
    metadata: dict = {}


@router.post("")
async def create_doc(payload: DocCreate):
    doc = add_document(**payload.model_dump())
    try:
        summary = payload.summary or payload.content[:200]
        from core.emma_bridge import push_summary_to_emma
        await push_summary_to_emma("document", payload.title, summary, tags=payload.tags)
    except Exception:
        pass
    return doc


@router.get("")
def list_docs(tag: Optional[str] = None, source: Optional[str] = None, limit: int = 50):
    return list_documents(tag=tag, source=source, limit=limit)


@router.get("/{doc_id}")
def get_doc(doc_id: int):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/search/{query}")
def search_docs(query: str, limit: int = 20):
    return search_documents(query, limit=limit)


@router.delete("/{doc_id}")
def delete_doc(doc_id: int):
    if not delete_document(doc_id):
        raise HTTPException(404, "Document not found")
    return {"ok": True}
