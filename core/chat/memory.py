from datetime import datetime
from typing import Optional

from core.deps import get_db

MAX_TOKENS = 4000


def _ensure_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL DEFAULT 'user',
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, created_at)")
    conn.commit()


def add_message(session_id: str, role: str, content: str):
    _ensure_table()
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now),
    )
    conn.commit()


def get_history(session_id: str, max_tokens: int = MAX_TOKENS) -> list[dict]:
    _ensure_table()
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    trimmed = []
    token_estimate = 0
    for m in reversed(messages):
        tokens = len(m["content"]) // 4 + 10
        if token_estimate + tokens > max_tokens:
            break
        trimmed.insert(0, m)
        token_estimate += tokens
    return trimmed


def clear_session(session_id: str):
    _ensure_table()
    conn = get_db()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.commit()


def list_sessions() -> list[str]:
    _ensure_table()
    conn = get_db()
    rows = conn.execute(
        "SELECT session_id FROM chat_messages GROUP BY session_id ORDER BY MAX(created_at) DESC"
    ).fetchall()
    return [r["session_id"] for r in rows]
