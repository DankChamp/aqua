from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.deps import get_ai_router
from core.router import AIRouter, TaskType
from core.study.plans import (
    create_plan, get_plan, list_plans, delete_plan,
    add_task, list_tasks, complete_task,
    get_plan_with_tasks, start_session, end_session, get_stats,
    generate_plan,
)

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
    return get_stats()
