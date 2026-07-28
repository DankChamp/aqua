from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.study.flashcards import create_quiz, get_quiz, list_quizzes, submit_answer, grade_quiz
from core.documents.manager import get_document
from api.deps import get_ai_router
from core.router import AIRouter, TaskType

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


class GenerateRequest(BaseModel):
    document_id: int
    num_questions: int = 5
    topic: str = ""


@router.post("/generate")
async def generate_quiz(payload: GenerateRequest, ai_router: AIRouter = Depends(get_ai_router)):
    doc = get_document(payload.document_id)
    if not doc:
        raise HTTPException(400, "Document not found")
    content_preview = (doc.title + "\n\n" + doc.content)[:4000]
    prompt = (
        f"Generate {payload.num_questions} quiz questions based on this document.\n"
        f"Return ONLY a JSON array of objects with keys: question, correct_answer, options (array of 4 choices).\n"
        f"Document:\n{content_preview}"
    )
    try:
        result = await ai_router.run(TaskType.STUDY, prompt, model="", provider_name="")
    except Exception as exc:
        raise HTTPException(503, f"AI generation failed: {exc}")
    import json
    raw = result.text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI returned invalid JSON")
    if not isinstance(questions, list):
        raise HTTPException(500, "AI did not return a list")
    topic = payload.topic or doc.title
    q = create_quiz(f"Quiz: {doc.title}", topic, questions)
    return q


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
