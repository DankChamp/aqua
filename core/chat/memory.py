from datetime import datetime

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def _ensure_session(session_id: str):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO chat_sessions (session_id, name, created_at) VALUES (?, ?, ?)",
        (session_id, "", now),
    )
    conn.commit()


def add_message(session_id: str, role: str, content: str):
    _ensure_table()
    _ensure_session(session_id)
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now),
    )
    conn.commit()
    if role == "user":
        _auto_name(session_id, content)


def _auto_name(session_id: str, first_message: str):
    name = first_message.strip()[:60]
    if name:
        conn = get_db()
        cur = conn.execute("SELECT name FROM chat_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row and not row["name"]:
            conn.execute("UPDATE chat_sessions SET name = ? WHERE session_id = ?", (name, session_id))
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


def get_session_messages(session_id: str) -> list[dict]:
    _ensure_table()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def clear_session(session_id: str):
    _ensure_table()
    conn = get_db()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
    conn.commit()


def list_session_details() -> list[dict]:
    _ensure_table()
    conn = get_db()
    rows = conn.execute("""
        SELECT s.session_id, s.name, s.created_at,
               COUNT(m.id) as message_count,
               MAX(m.created_at) as last_activity
        FROM chat_sessions s
        LEFT JOIN chat_messages m ON m.session_id = s.session_id
        GROUP BY s.session_id
        ORDER BY last_activity DESC
    """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d["message_count"] == 0:
            conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (d["session_id"],))
            conn.commit()
            continue
        if not d["name"]:
            first = conn.execute(
                "SELECT content FROM chat_messages WHERE session_id = ? AND role = 'user' ORDER BY created_at ASC LIMIT 1",
                (d["session_id"],),
            ).fetchone()
            d["name"] = (first["content"][:60] if first else "Untitled") if first else "Untitled"
        result.append(d)
    return result


def rename_session(session_id: str, name: str):
    _ensure_table()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO chat_sessions (session_id, name, created_at) VALUES (?, ?, COALESCE((SELECT created_at FROM chat_sessions WHERE session_id = ?), ?))",
        (session_id, name, session_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


def edit_message(message_id: int, new_content: str) -> bool:
    _ensure_table()
    conn = get_db()
    cur = conn.execute(
        "UPDATE chat_messages SET content = ? WHERE id = ?", (new_content, message_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_message(message_id: int) -> bool:
    _ensure_table()
    conn = get_db()
    cur = conn.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    conn.commit()
    return cur.rowcount > 0
