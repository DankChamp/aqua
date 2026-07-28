import sqlite3
from datetime import datetime
from typing import Optional

from core.deps import get_db


def _migrate(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            class_std TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def add_activity(action: str, detail: str = "", class_std: str = "",
                 subject: str = "", chapter: str = ""):
    conn = get_db()
    _migrate(conn)
    conn.execute(
        "INSERT INTO activity_log (action, detail, class_std, subject, chapter, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (action, detail, class_std, subject, chapter, _now()),
    )
    conn.commit()


def get_activity(limit: int = 20) -> list[dict]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]
