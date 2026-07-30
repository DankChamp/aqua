import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.deps import get_db

logger = logging.getLogger("aqua.study.progress")


@dataclass
class ChapterProgress:
    class_std: str = ""
    subject: str = ""
    chapter: str = ""
    status: str = "not_started"
    notes_count: int = 0
    flashcards_count: int = 0
    quiz_score: Optional[float] = None
    quiz_taken: bool = False
    taught: bool = False
    last_studied: Optional[str] = None


def _migrate(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chapter_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_std TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'not_started',
            notes_count INTEGER NOT NULL DEFAULT 0,
            flashcards_count INTEGER NOT NULL DEFAULT 0,
            quiz_score REAL,
            quiz_taken INTEGER NOT NULL DEFAULT 0,
            taught INTEGER NOT NULL DEFAULT 0,
            last_studied TEXT,
            UNIQUE(class_std, subject, chapter)
        )
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def _ensure_progress(class_std: str, subject: str, chapter: str):
    conn = get_db()
    _migrate(conn)
    existing = conn.execute(
        "SELECT id FROM chapter_progress WHERE class_std = ? AND subject = ? AND chapter = ?",
        (class_std, subject, chapter),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO chapter_progress (class_std, subject, chapter, status) VALUES (?, ?, ?, ?)",
            (class_std, subject, chapter, "not_started"),
        )
        conn.commit()


def update_progress(class_std: str, subject: str, chapter: str, **kwargs):
    conn = get_db()
    _migrate(conn)
    _ensure_progress(class_std, subject, chapter)
    sets = ["last_studied = ?"]
    params = [_now()]
    for key, value in kwargs.items():
        if key in ("notes_count", "flashcards_count"):
            sets.append(f"{key} = COALESCE((SELECT {key} FROM chapter_progress WHERE "
                        f"class_std = ? AND subject = ? AND chapter = ?), 0) + ?")
            params.extend([class_std, subject, chapter, value])
        elif key == "quiz_score":
            sets.append(f"{key} = ?")
            params.append(value)
        elif key in ("quiz_taken", "taught"):
            sets.append(f"{key} = ?")
            params.append(1 if value else 0)
        elif key == "status":
            sets.append(f"{key} = ?")
            params.append(value)
    params.extend([class_std, subject, chapter])
    conn.execute(
        f"UPDATE chapter_progress SET {', '.join(sets)} WHERE class_std = ? AND subject = ? AND chapter = ?",
        params,
    )
    conn.commit()


def get_progress(class_std: Optional[str] = None, subject: Optional[str] = None) -> list[dict]:
    conn = get_db()
    _migrate(conn)
    conditions = []
    params = []
    if class_std:
        conditions.append("class_std = ?")
        params.append(class_std)
    if subject:
        conditions.append("subject = ?")
        params.append(subject)
    sql = "SELECT * FROM chapter_progress"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY class_std, subject, chapter"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
