import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from core.router import AIRouter, TaskType
from core.study.plans import (
    create_plan, get_plan, list_plans, delete_plan,
    add_task, list_tasks, complete_task,
    get_plan_with_tasks, start_session, end_session,
    generate_plan,
)
from core.study.progress import get_progress
from core.study.flashcards import add_flashcard, create_quiz
from core.documents.manager import get_document, add_note
from core import voice_service
from core.activity import get_streak
from core.study.analytics import (
    get_study_stats, get_quiz_history, get_daily_activity,
    get_flashcard_reviews, get_quiz_score_trend, get_study_time_trend,
)

logger = logging.getLogger("aqua.study")

router = APIRouter(prefix="/study", tags=["study"])


class PlanGenerate(BaseModel):
    topic: str
    document_ids: list[int] = []
    duration_days: int = 7


class PlanCreate(BaseModel):
    title: str
    topic: str = ""
    description: str = ""
    duration_days: int = 7
    document_ids: list[int] = []


class TaskCreate(BaseModel):
    day: int = 1
    title: str
    description: str = ""
    duration_minutes: int = 30


class SessionStart(BaseModel):
    plan_id: int
    task_id: Optional[int] = None


class SessionEnd(BaseModel):
    notes: str = ""
    rating: Optional[int] = None


@router.post("/plans/generate")
async def generate(payload: PlanGenerate, ai_router: AIRouter = Depends(get_ai_router)):
    try:
        plan = await generate_plan(payload.topic, payload.document_ids, payload.duration_days)
        return get_plan_with_tasks(plan.id)
    except Exception as exc:
        raise HTTPException(503, f"Plan generation failed: {exc}")


@router.post("/plans")
def create(payload: PlanCreate):
    return create_plan(
        title=payload.title,
        topic=payload.topic,
        description=payload.description,
        duration_days=payload.duration_days,
        document_ids=payload.document_ids,
    )


@router.get("/plans")
def list_all():
    return list_plans()


@router.get("/plans/{plan_id}")
def get(plan_id: int):
    result = get_plan_with_tasks(plan_id)
    if not result:
        raise HTTPException(404, "Study plan not found")
    return result


@router.delete("/plans/{plan_id}")
def delete(plan_id: int):
    if not delete_plan(plan_id):
        raise HTTPException(404, "Study plan not found")
    return {"ok": True}


@router.get("/plans/{plan_id}/tasks")
def plan_tasks(plan_id: int):
    if not get_plan(plan_id):
        raise HTTPException(404, "Study plan not found")
    return list_tasks(plan_id)


@router.post("/plans/{plan_id}/tasks")
def add_plan_task(plan_id: int, payload: TaskCreate):
    if not get_plan(plan_id):
        raise HTTPException(404, "Study plan not found")
    return add_task(
        plan_id=plan_id,
        day=payload.day,
        title=payload.title,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
    )


@router.post("/tasks/{task_id}/complete")
def do_complete(task_id: int):
    task = complete_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found or already completed")
    return task


@router.post("/sessions/start")
def do_start_session(payload: SessionStart):
    return start_session(payload.plan_id, payload.task_id)


@router.post("/sessions/{session_id}/end")
def do_end_session(session_id: int, payload: SessionEnd):
    session = end_session(session_id, notes=payload.notes, rating=payload.rating)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("/stats")
def study_stats():
    return {
        "summary": get_study_stats(),
        "quiz_history": get_quiz_history(10),
        "quiz_score_trend": get_quiz_score_trend(10),
        "daily_activity": get_daily_activity(30),
        "flashcard_reviews": get_flashcard_reviews(30),
        "study_time": get_study_time_trend(30),
    }


class PackGenerate(BaseModel):
    document_id: int


class GuideGenerate(BaseModel):
    document_ids: list[int]
    title: str = ""


class PlanFromDoc(BaseModel):
    document_id: int
    duration_days: int = 7


@router.get("/streak")
def streak():
    return get_streak()


@router.post("/plans/generate-from-doc")
async def generate_plan_from_doc(payload: PlanFromDoc, ai_router: AIRouter = Depends(get_ai_router)):
    doc = get_document(payload.document_id)
    if not doc:
        raise HTTPException(400, "Document not found")
    from core.study.plans import generate_plan as gp
    try:
        plan = await gp(doc.title, [doc.id], payload.duration_days)
        return get_plan_with_tasks(plan.id)
    except Exception as exc:
        raise HTTPException(503, f"Plan generation failed: {exc}")


@router.post("/generate-pack")
async def generate_study_pack(payload: PackGenerate, ai_router: AIRouter = Depends(get_ai_router)):
    doc = get_document(payload.document_id)
    if not doc:
        raise HTTPException(400, "Document not found")
    content = (doc.title + "\n\n" + doc.content)[:6000]

    async def gen_notes():
        prompt = (
            f"Generate comprehensive, detailed study notes from the following document. "
            f"Cover every concept in depth with examples, explanations, and key takeaways. "
            f"Return in clean markdown format.\n\nDocument:\n{content}"
        )
        r = await ai_router.run(TaskType.STUDY, prompt, system="You are a study note generator.")
        return add_note(content=r.text, title=f"Notes: {doc.title}", document_id=doc.id, note_type="detailed")

    async def gen_flashcards():
        prompt = (
            f"Generate 10 flashcards (Q&A pairs) from this document. "
            f"Return ONLY a JSON array of objects with 'question' and 'answer' keys.\n\n{content}"
        )
        r = await ai_router.run(TaskType.STUDY, prompt, system="You are a flashcard generator. Return ONLY valid JSON.")
        raw = r.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        cards = json.loads(raw)
        if not isinstance(cards, list):
            raise ValueError("Not a list")
        count = 0
        for cd in cards[:10]:
            add_flashcard(question=cd["question"], answer=cd["answer"], topic=doc.title)
            count += 1
        return count

    async def gen_quiz():
        prompt = (
            f"Generate 5 quiz questions from this document. "
            f"Return ONLY a JSON array of objects with keys: question, correct_answer, options (array of 4 choices).\n\n{content}"
        )
        r = await ai_router.run(TaskType.STUDY, prompt, system="You are a quiz generator. Return ONLY valid JSON.")
        raw = r.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError("Not a list")
        return create_quiz(f"Quiz: {doc.title}", doc.title, questions)

    import asyncio
    notes_task = gen_notes()
    fc_task = gen_flashcards()
    quiz_task = gen_quiz()

    results = await asyncio.gather(notes_task, fc_task, quiz_task, return_exceptions=True)

    notes_result, fc_result, quiz_result = results

    resp = {}
    if isinstance(notes_result, Exception):
        logger.warning("Note generation failed: %s", notes_result)
        resp["notes"] = {"error": str(notes_result)}
    else:
        resp["notes"] = {"id": notes_result.id, "title": notes_result.title}
        voice_service.say(
            voice_service.summarize_note_for_speech(notes_result.title, notes_result.content),
            interrupt=True,
            max_chars=3200,
        )

    if isinstance(fc_result, Exception):
        logger.warning("Flashcard generation failed: %s", fc_result)
        resp["flashcards"] = {"error": str(fc_result)}
    else:
        resp["flashcards"] = {"count": fc_result}

    if isinstance(quiz_result, Exception):
        logger.warning("Quiz generation failed: %s", quiz_result)
        resp["quiz"] = {"error": str(quiz_result)}
    else:
        resp["quiz"] = {"id": quiz_result.id, "title": quiz_result.title}

    return resp


@router.post("/guide")
async def study_guide(payload: GuideGenerate, ai_router: AIRouter = Depends(get_ai_router)):
    docs_text = ""
    for did in payload.document_ids:
        doc = get_document(did)
        if doc:
            docs_text += f"\n\n--- {doc.title} ---\n{doc.content[:3000]}"
    if not docs_text:
        raise HTTPException(400, "No valid documents found")

    prompt = (
        f"Create a comprehensive study guide combining the source materials below. "
        f"Organize by topics, identify key concepts and their relationships, "
        f"and create a coherent learning path with summaries and review questions. "
        f"Return in clean markdown format.\n\n{docs_text[:12000]}"
    )
    result = await ai_router.run(
        TaskType.STUDY, prompt,
        system="You are a study guide creator. Synthesize multiple sources into a well-structured study guide in markdown.",
    )

    title = payload.title or f"Study Guide ({len(payload.document_ids)} sources)"
    note = add_note(content=result.text, title=title, note_type="study_guide")
    voice_service.say(
        voice_service.summarize_note_for_speech(note.title, note.content),
        interrupt=True,
        max_chars=3200,
    )
    return {"id": note.id, "title": note.title, "content": result.text}
