from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.study.flashcards import add_flashcard, get_flashcard, list_flashcards, review_flashcard, delete_flashcard

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


class FlashcardCreate(BaseModel):
    question: str
    answer: str
    topic: str = ""
    difficulty: int = 1


class ReviewRequest(BaseModel):
    correct: bool


@router.post("")
async def create_flashcard(payload: FlashcardCreate):
    card = add_flashcard(**payload.model_dump())
    try:
        from core.emma_bridge import push_summary_to_emma
        await push_summary_to_emma("flashcard", payload.question, payload.answer[:200], tags=[payload.topic] if payload.topic else None)
    except Exception:
        pass
    return card


@router.get("")
def list_flashcard(topic: Optional[str] = None, limit: int = 100):
    return list_flashcards(topic=topic, limit=limit)


@router.get("/{card_id}")
def get_flashcard_route(card_id: int):
    card = get_flashcard(card_id)
    if not card:
        raise HTTPException(404, "Flashcard not found")
    return card


@router.post("/{card_id}/review")
def review_flashcard_route(card_id: int, payload: ReviewRequest):
    card = review_flashcard(card_id, payload.correct)
    if not card:
        raise HTTPException(404, "Flashcard not found")
    return card


@router.delete("/{card_id}")
def delete_flashcard_route(card_id: int):
    if not delete_flashcard(card_id):
        raise HTTPException(404, "Flashcard not found")
    return {"ok": True}
