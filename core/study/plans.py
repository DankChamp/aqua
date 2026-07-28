import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from core.deps import get_db

logger = logging.getLogger("aqua.study.plans")


@dataclass
class StudyPlan:
    id: Optional[int] = None
    title: str = ""
    topic: str = ""
    description: str = ""
    duration_days: int = 7
    document_ids: str = "[]"
    progress: float = 0.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StudyPlanTask:
    id: Optional[int] = None
    plan_id: int = 0
    day: int = 1
    title: str = ""
    description: str = ""
    duration_minutes: int = 30
    completed: bool = False
    completed_at: Optional[str] = None
    resource_ids: str = "[]"


@dataclass
class StudySession:
    id: Optional[int] = None
    plan_id: int = 0
    task_id: Optional[int] = None
    started_at: str = ""
    ended_at: Optional[str] = None
    duration_minutes: int = 0
    notes: str = ""
    rating: Optional[int] = None


def _migrate(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            duration_days INTEGER NOT NULL DEFAULT 7,
            document_ids TEXT NOT NULL DEFAULT '[]',
            progress REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS study_plan_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            duration_minutes INTEGER NOT NULL DEFAULT 30,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            resource_ids TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (plan_id) REFERENCES study_plans(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            task_id INTEGER,
            started_at TEXT NOT NULL DEFAULT '',
            ended_at TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            rating INTEGER,
            FOREIGN KEY (plan_id) REFERENCES study_plans(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_study_tasks_plan ON study_plan_tasks(plan_id, day);
        CREATE INDEX IF NOT EXISTS idx_study_sessions_plan ON study_sessions(plan_id);
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def _row_to_plan(row: sqlite3.Row) -> StudyPlan:
    return StudyPlan(
        id=row["id"],
        title=row["title"],
        topic=row["topic"],
        description=row["description"],
        duration_days=row["duration_days"],
        document_ids=row["document_ids"],
        progress=row["progress"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_task(row: sqlite3.Row) -> StudyPlanTask:
    return StudyPlanTask(
        id=row["id"],
        plan_id=row["plan_id"],
        day=row["day"],
        title=row["title"],
        description=row["description"],
        duration_minutes=row["duration_minutes"],
        completed=bool(row["completed"]),
        completed_at=row["completed_at"],
        resource_ids=row["resource_ids"],
    )


def create_plan(title: str, topic: str, description: str, duration_days: int,
                document_ids: list[int] | None = None) -> StudyPlan:
    conn = get_db()
    _migrate(conn)
    now = _now()
    ids_json = json.dumps(document_ids or [])
    cur = conn.execute(
        "INSERT INTO study_plans (title, topic, description, duration_days, document_ids, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, topic, description, duration_days, ids_json, now, now),
    )
    conn.commit()
    return get_plan(cur.lastrowid)


def get_plan(plan_id: int) -> Optional[StudyPlan]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM study_plans WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_plan(row) if row else None


def list_plans(limit: int = 20) -> list[StudyPlan]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT * FROM study_plans ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_plan(r) for r in rows]


def delete_plan(plan_id: int) -> bool:
    conn = get_db()
    _migrate(conn)
    conn.execute("DELETE FROM study_plan_tasks WHERE plan_id = ?", (plan_id,))
    conn.execute("DELETE FROM study_plans WHERE id = ?", (plan_id,))
    conn.commit()
    return conn.total_changes > 0


def add_task(plan_id: int, day: int, title: str, description: str = "",
             duration_minutes: int = 30, resource_ids: list[int] | None = None) -> StudyPlanTask:
    conn = get_db()
    _migrate(conn)
    rid_json = json.dumps(resource_ids or [])
    cur = conn.execute(
        "INSERT INTO study_plan_tasks (plan_id, day, title, description, duration_minutes, resource_ids) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (plan_id, day, title, description, duration_minutes, rid_json),
    )
    conn.commit()
    return get_task(cur.lastrowid)


def get_task(task_id: int) -> Optional[StudyPlanTask]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM study_plan_tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def list_tasks(plan_id: int) -> list[StudyPlanTask]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT * FROM study_plan_tasks WHERE plan_id = ? ORDER BY day ASC, id ASC", (plan_id,)
    ).fetchall()
    return [_row_to_task(r) for r in rows]


def complete_task(task_id: int) -> Optional[StudyPlanTask]:
    conn = get_db()
    _migrate(conn)
    now = _now()
    conn.execute(
        "UPDATE study_plan_tasks SET completed = 1, completed_at = ? WHERE id = ? AND completed = 0",
        (now, task_id),
    )
    conn.commit()
    task = get_task(task_id)
    if task:
        _recalc_progress(task.plan_id)
    return task


def _recalc_progress(plan_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as total, SUM(CASE WHEN completed THEN 1 ELSE 0 END) as done "
        "FROM study_plan_tasks WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    total = row["total"] or 0
    done = row["done"] or 0
    progress = (done / total * 100) if total > 0 else 0.0
    conn.execute("UPDATE study_plans SET progress = ?, updated_at = ? WHERE id = ?",
                 (progress, _now(), plan_id))
    conn.commit()


def get_plan_with_tasks(plan_id: int) -> Optional[dict]:
    plan = get_plan(plan_id)
    if not plan:
        return None
    tasks = list_tasks(plan_id)
    return {
        **asdict(plan),
        "tasks": [asdict(t) for t in tasks],
    }


def start_session(plan_id: int, task_id: Optional[int] = None) -> StudySession:
    conn = get_db()
    _migrate(conn)
    now = _now()
    cur = conn.execute(
        "INSERT INTO study_sessions (plan_id, task_id, started_at) VALUES (?, ?, ?)",
        (plan_id, task_id, now),
    )
    conn.commit()
    sid = cur.lastrowid
    row = conn.execute("SELECT * FROM study_sessions WHERE id = ?", (sid,)).fetchone()
    return StudySession(**dict(row))


def end_session(session_id: int, notes: str = "", rating: Optional[int] = None) -> Optional[StudySession]:
    conn = get_db()
    _migrate(conn)
    now = _now()
    row = conn.execute("SELECT * FROM study_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    started = datetime.fromisoformat(row["started_at"])
    duration = int((datetime.utcnow() - started).total_seconds() / 60)
    conn.execute(
        "UPDATE study_sessions SET ended_at = ?, duration_minutes = ?, notes = ?, rating = ? WHERE id = ?",
        (now, duration, notes, rating, session_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM study_sessions WHERE id = ?", (session_id,)).fetchone()
    return StudySession(**dict(row))


def get_stats() -> dict:
    conn = get_db()
    _migrate(conn)
    total_plans = conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0]
    total_tasks = conn.execute("SELECT COUNT(*) FROM study_plan_tasks").fetchone()[0]
    completed_tasks = conn.execute("SELECT COUNT(*) FROM study_plan_tasks WHERE completed = 1").fetchone()[0]
    total_minutes = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions").fetchone()[0]
    return {
        "total_plans": total_plans,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_study_minutes": total_minutes,
    }


async def generate_plan(topic: str, document_ids: list[int], duration_days: int = 7) -> StudyPlan:
    from core.deps import get_router
    from core.router import TaskType
    from core.documents.manager import get_document

    docs_text = ""
    for did in document_ids:
        doc = get_document(did)
        if doc:
            docs_text += f"\n--- Document: {doc.title} ---\n{doc.content[:1500]}\n"

    prompt = (
        f"Create a {duration_days}-day study plan for the topic: {topic}.\n"
        f"Here are the source documents:\n{docs_text[:4000]}\n\n"
        "Return ONLY a valid JSON object with this structure:\n"
        "{\n"
        '  "title": "Plan title",\n'
        '  "description": "Brief description of the plan",\n'
        '  "tasks": [\n'
        "    {\n"
        '      "day": 1,\n'
        '      "title": "Task title",\n'
        '      "description": "What to do",\n'
        '      "duration_minutes": 45\n'
        "    }\n"
        "  ]\n"
        "}\n"
        f"Generate exactly {duration_days * 2} tasks spread across the {duration_days} days."
    )

    ai_router = get_router()
    result = await ai_router.run(TaskType.STUDY, prompt, system="You are a study planner. Output only valid JSON.")
    raw = result.text.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    data = json.loads(raw)
    plan = create_plan(
        title=data.get("title", f"Study Plan: {topic}"),
        topic=topic,
        description=data.get("description", ""),
        duration_days=duration_days,
        document_ids=document_ids,
    )

    for t in data.get("tasks", []):
        add_task(
            plan_id=plan.id,
            day=t.get("day", 1),
            title=t.get("title", ""),
            description=t.get("description", ""),
            duration_minutes=t.get("duration_minutes", 30),
            resource_ids=document_ids,
        )

    return plan
