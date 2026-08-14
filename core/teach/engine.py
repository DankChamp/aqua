import json
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from core.deps import get_db
from core.chat.memory import add_message, get_history
from core.profile import manager as profile_mgr

logger = logging.getLogger("aqua.teach")

TEACH_SYSTEM = """You are Aqua, a patient, skilled tutor teaching a student one-on-one.

RULES:
1. Explain concepts step by step — don't dump everything at once.
2. After each explanation, ask a comprehension question to check understanding.
3. If the student gets it right, affirm and move to the next concept.
4. If the student gets it wrong, simplify, give a different example, and ask again.
5. Teach like a warm, slightly flirty teacher: playful, patient, attentive, and confident. Keep it respectful and learning-focused.
6. Adapt to the student's level — if they're struggling, slow down.
7. Reference the provided notes and source material directly.
8. Keep responses concise but complete.
9. At natural breakpoints, suggest actions like "Shall I create flashcards from this?" or "Ready for the next concept?"
10. When the student asks a question, answer it thoroughly before continuing.
11. If the student asks you to remember something, acknowledge it briefly and use that fact later.

Start by greeting the student and introducing what you'll cover today."""


def _migrate(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teach_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            class_std TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            message_count INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def start_session(class_std: str, subject: str, chapter: str) -> str:
    conn = get_db()
    _migrate(conn)
    now = _now()
    import uuid
    session_id = f"teach_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO teach_sessions (session_id, class_std, subject, chapter, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, class_std, subject, chapter, now, now),
    )
    conn.commit()
    return session_id


def end_session(session_id: str):
    conn = get_db()
    _migrate(conn)
    conn.execute("UPDATE teach_sessions SET completed = 1, updated_at = ? WHERE session_id = ?",
                 (_now(), session_id))
    conn.commit()


def get_session(session_id: str) -> Optional[dict]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM teach_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def list_sessions(limit: int = 20) -> list[dict]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT * FROM teach_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


async def teach(ai_router, session_id: str, message: str) -> str:
    from core.router import TaskType
    from core.documents.manager import list_notes

    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    conn = get_db()
    conn.execute(
        "UPDATE teach_sessions SET message_count = message_count + 1, updated_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    conn.commit()

    add_message(session_id, "user", message)
    remembered = profile_mgr.remember_from_text(message)

    context_parts = [TEACH_SYSTEM]
    context_parts.append(
        f"You are teaching: Class {session['class_std']}, {session['subject']}, Chapter: {session['chapter']}"
    )

    notes = list_notes(
        class_std=session["class_std"],
        subject=session["subject"],
        chapter=session["chapter"],
        limit=10,
    )
    if notes:
        notes_block = "Here are the notes for this chapter (use as reference):\n"
        for n in notes:
            notes_block += f"\n--- {n.note_type or 'Notes'} ---\n{n.content[:2000]}\n"
        context_parts.append(notes_block)

    history = get_history(session_id, max_tokens=2000)
    if history:
        history_block = "Previous conversation:\n" + "\n".join(
            f"{m['role']}: {m['content']}" for m in history[:-1]
        )
        context_parts.append(history_block)

    profile_block = profile_mgr.to_context_block()
    if profile_block:
        context_parts.append(profile_block)

    system = "\n\n".join(context_parts)
    prompt = f"The student says: {message}\n\nRespond as a tutor."

    result = await ai_router.run(TaskType.STUDY, prompt, system=system)
    reply = result.text
    if remembered:
        reply = f"I'll remember that, sweetheart: {remembered['value']}.\n\n{reply}"
    add_message(session_id, "assistant", reply)
    return reply
