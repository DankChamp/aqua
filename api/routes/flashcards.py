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
def create_flashcard(payload: FlashcardCreate):
    return add_flashcard(**payload.model_dump())


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
