from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.study.flashcards import create_quiz, get_quiz, list_quizzes, submit_answer, grade_quiz

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


class QuestionData(BaseModel):
    question: str
    correct_answer: str
    options: list[str] = []


class QuizCreate(BaseModel):
    title: str
    topic: str = ""
    questions: list[QuestionData]


class AnswerSubmit(BaseModel):
    answer: str


@router.post("")
def create_quiz_route(payload: QuizCreate):
    q_data = [qd.model_dump() for qd in payload.questions]
    return create_quiz(payload.title, payload.topic, q_data)


@router.get("")
def list_quiz(limit: int = 20):
    return list_quizzes(limit=limit)


@router.get("/{quiz_id}")
def get_quiz_route(quiz_id: int):
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    return quiz


@router.post("/{quiz_id}/questions/{question_id}/answer")
def answer_question(quiz_id: int, question_id: int, payload: AnswerSubmit):
    if not submit_answer(question_id, payload.answer):
        raise HTTPException(404, "Question not found")
    return {"ok": True}


@router.post("/{quiz_id}/grade")
def grade_quiz_route(quiz_id: int):
    result = grade_quiz(quiz_id)
    if not result:
        raise HTTPException(404, "Quiz not found")
    return result
