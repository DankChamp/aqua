import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from core.documents.manager import (
    add_document, get_document, list_documents,
    search_documents, delete_document,
)

logger = logging.getLogger("aqua.documents")

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
    except Exception as exc:
        logger.warning("Emma bridge failed: %s", exc)
    return doc


@router.post("/import")
async def import_doc(file: UploadFile = File(...), title: Optional[str] = Form(None)):
    content = await file.read()
    filename = file.filename or "untitled"
    doc_title = title or filename
    text = ""
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            raise HTTPException(400, "Failed to extract PDF text")
    elif filename.endswith(".html") or filename.endswith(".htm"):
        from core.web.scraper import extract_text
        text = extract_text(content.decode("utf-8", errors="replace"))
    else:
        text = content.decode("utf-8", errors="replace")
    doc = add_document(title=doc_title, content=text, source="import", file_path=filename)
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
