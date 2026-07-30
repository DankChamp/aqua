import json
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from core.deps import get_db
from .models import Document, Note

logger = logging.getLogger("aqua.documents")


def _migrate(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            authors TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            source_url TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            document_id INTEGER,
            class_std TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            note_type TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL DEFAULT 'user',
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, created_at);
    """)
    for col in ("class_std", "subject", "chapter", "note_type"):
        try:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        except Exception as exc:
            logger.debug("Migration column %s may already exist: %s", col, exc)
def _now() -> str:
    return datetime.utcnow().isoformat()


def add_document(title: str, content: str = "", authors: str = "", source: str = "manual",
                 source_url: str = "", file_path: str = "", summary: str = "",
                 tags: Optional[list[str]] = None, metadata: Optional[dict] = None) -> Document:
    conn = get_db()
    _migrate(conn)
    now = _now()
    tags_json = json.dumps(tags or [])
    meta_json = json.dumps(metadata or {})
    cur = conn.execute(
        "INSERT INTO documents (title, content, authors, source, source_url, file_path, summary, tags, metadata_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, content, authors, source, source_url, file_path, summary, tags_json, meta_json, now, now),
    )
    conn.commit()
    doc_id = cur.lastrowid
    from core.search.vector import index_document
    index_document(doc_id, title, content)
    from core.activity import add_activity
    add_activity("added_document", f"{title} ({source})")
    return get_document(doc_id)


def get_document(doc_id: int) -> Optional[Document]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        return None
    return _row_to_doc(row)


def list_documents(tag: Optional[str] = None, source: Optional[str] = None, limit: int = 50) -> list[Document]:
    conn = get_db()
    _migrate(conn)
    query = "SELECT * FROM documents"
    params = []
    conditions = []
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if source:
        conditions.append("source = ?")
        params.append(source)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_doc(r) for r in rows]


def search_documents(query: str, limit: int = 20) -> list[Document]:
    conn = get_db()
    _migrate(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM documents WHERE content LIKE ? OR title LIKE ? OR summary LIKE ? ORDER BY created_at DESC LIMIT ?",
        (like, like, like, limit),
    ).fetchall()
    return [_row_to_doc(r) for r in rows]


def delete_document(doc_id: int) -> bool:
    conn = get_db()
    _migrate(conn)
    cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    from core.search.vector import remove_document
    remove_document(doc_id)
    return cur.rowcount > 0


def _row_to_doc(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        authors=row["authors"],
        source=row["source"],
        source_url=row["source_url"],
        file_path=row["file_path"],
        summary=row["summary"],
        tags=json.loads(row["tags"]),
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def add_note(content: str, title: str = "", document_id: Optional[int] = None,
             class_std: str = "", subject: str = "", chapter: str = "",
             note_type: str = "") -> Note:
    conn = get_db()
    _migrate(conn)
    now = _now()
    cur = conn.execute(
        "INSERT INTO notes (title, content, document_id, class_std, subject, chapter, note_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, content, document_id, class_std, subject, chapter, note_type, now, now),
    )
    conn.commit()
    note_id = cur.lastrowid
    from core.search.vector import index_note
    index_note(note_id, title, content)
    from core.activity import add_activity
    add_activity("generated_notes", f"{note_type or 'detailed'} notes", class_std, subject, chapter)
    return get_note(note_id)


def get_note(note_id: int) -> Optional[Note]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        return None
    return Note(id=row["id"], title=row["title"], content=row["content"],
                document_id=row["document_id"], class_std=row["class_std"],
                subject=row["subject"], chapter=row["chapter"],
                note_type=row["note_type"],
                created_at=row["created_at"], updated_at=row["updated_at"])


def list_notes(document_id: Optional[int] = None, limit: int = 50,
               class_std: Optional[str] = None, subject: Optional[str] = None,
               chapter: Optional[str] = None, note_type: Optional[str] = None) -> list[Note]:
    conn = get_db()
    _migrate(conn)
    conditions = []
    params = []
    if document_id:
        conditions.append("document_id = ?")
        params.append(document_id)
    if class_std:
        conditions.append("class_std = ?")
        params.append(class_std)
    if subject:
        conditions.append("subject = ?")
        params.append(subject)
    if chapter:
        conditions.append("chapter = ?")
        params.append(chapter)
    if note_type:
        conditions.append("note_type = ?")
        params.append(note_type)
    sql = "SELECT * FROM notes"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_note(r) for r in rows]


def _row_to_note(row: sqlite3.Row) -> Note:
    return Note(id=row["id"], title=row["title"], content=row["content"],
                document_id=row["document_id"], class_std=row["class_std"],
                subject=row["subject"], chapter=row["chapter"],
                note_type=row["note_type"],
                created_at=row["created_at"], updated_at=row["updated_at"])


def search_notes(query: str, limit: int = 20) -> list[Note]:
    conn = get_db()
    _migrate(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM notes WHERE content LIKE ? OR title LIKE ? OR subject LIKE ? OR chapter LIKE ? "
        "ORDER BY created_at DESC LIMIT ?",
        (like, like, like, like, limit),
    ).fetchall()
    return [_row_to_note(r) for r in rows]


def edit_note(note_id: int, content: str, title: Optional[str] = None,
              class_std: Optional[str] = None, subject: Optional[str] = None,
              chapter: Optional[str] = None, note_type: Optional[str] = None) -> Optional[Note]:
    conn = get_db()
    _migrate(conn)
    now = _now()
    sets = ["content = ?", "updated_at = ?"]
    params = [content, now]
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if class_std is not None:
        sets.append("class_std = ?")
        params.append(class_std)
    if subject is not None:
        sets.append("subject = ?")
        params.append(subject)
    if chapter is not None:
        sets.append("chapter = ?")
        params.append(chapter)
    if note_type is not None:
        sets.append("note_type = ?")
        params.append(note_type)
    params.append(note_id)
    conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return get_note(note_id)


def delete_note(note_id: int) -> bool:
    conn = get_db()
    _migrate(conn)
    cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return cur.rowcount > 0


def list_subjects(class_std: Optional[str] = None) -> list[str]:
    conn = get_db()
    _migrate(conn)
    if class_std:
        rows = conn.execute("SELECT DISTINCT subject FROM notes WHERE class_std = ? AND subject != '' ORDER BY subject", (class_std,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT subject FROM notes WHERE subject != '' ORDER BY subject").fetchall()
    return [r["subject"] for r in rows]


def list_chapters(class_std: str, subject: str) -> list[str]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT DISTINCT chapter FROM notes WHERE class_std = ? AND subject = ? AND chapter != '' ORDER BY chapter",
        (class_std, subject),
    ).fetchall()
    return [r["chapter"] for r in rows]


async def generate_note(class_std: str, subject: str, chapter: str,
                        document_ids: Optional[list[int]] = None,
                        note_type: str = "detailed") -> Note:
    from core.deps import get_router
    from core.router import TaskType
    from .models import NOTE_TYPES, NOTE_TYPE_LABELS

    type_label = NOTE_TYPE_LABELS.get(note_type, "Detailed Notes")
    docs_text = ""
    if document_ids:
        for did in document_ids:
            doc = get_document(did)
            if doc:
                docs_text += f"\n--- {doc.title} ---\n{doc.content[:2000]}\n"

    prompt = (
        f"Generate {type_label} for Class {class_std} {subject}, Chapter: {chapter}.\n"
    )
    if docs_text:
        prompt += f"\nUse this source material:\n{docs_text[:5000]}\n"
    prompt += (
        "\nThe student will rely on these notes as their ONLY study resource, so they MUST be "
        "extremely comprehensive and cover the ENTIRE chapter in full detail. Include:\n"
        "- Every key concept, definition, and explanation from the chapter\n"
        "- All important formulas, equations, and theorems with worked examples\n"
        "- Step-by-step derivations where applicable\n"
        "- Diagrams described in words (since they cannot be drawn)\n"
        "- Real-world applications and examples for each concept\n"
        "- Common mistakes students make and how to avoid them\n"
        "- Exam-oriented tips and important points highlighted\n"
        "- Comparison tables for related concepts\n"
        "- A quick revision summary at the end\n"
        "- Practice questions with answers\n"
    )
    if note_type == "formula_sheet":
        prompt += "- Important formulas, equations, and theorems\n- Units and notation\n"
    elif note_type == "key_points":
        prompt += "- Bullet-point key takeaways\n- Common mistakes to avoid\n- Quick reference\n"
    elif note_type == "summary":
        prompt += "- Brief overview of the chapter\n- Main conclusions\n- Connection to next topics\n"
    else:
        prompt += "- Important formulas or equations (if applicable)\n- Examples\n- Key points to remember\n"
    prompt += "\nReturn the notes in clean markdown format. Use tables, bullet lists, and sections generously. Make sure the notes are LONG and THOROUGH — at least several pages worth of content."

    ai_router = get_router()
    result = await ai_router.run(
        TaskType.STUDY, prompt,
        system="You are a study note generator. Output detailed, well-structured notes in markdown.",
    )

    title = f"{subject} - {chapter}"
    return add_note(
        content=result.text,
        title=title,
        class_std=class_std,
        subject=subject,
        chapter=chapter,
        note_type=note_type,
    )
