from fastapi import APIRouter

from core.search.vector import hybrid_search
from core.documents.manager import search_documents
from core.documents.manager import search_notes
from core.study.flashcards import list_flashcards

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str, limit: int = 10):
    return hybrid_search(q, limit=limit)


@router.get("/all")
def search_all(q: str, limit: int = 10):
    like = f"%{q}%"
    docs = search_documents(q, limit=limit)
    notes = search_notes(q, limit=limit)
    cards = list_flashcards(limit=limit)
    cards = [c for c in cards if q.lower() in c.question.lower() or q.lower() in c.answer.lower() or q.lower() in c.topic.lower()][:limit]
    return {"documents": docs, "notes": notes, "flashcards": cards}
