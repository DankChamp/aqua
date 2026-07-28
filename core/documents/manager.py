import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import get_settings
from core.deps import get_db
from .models import Document, Note


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
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    from core.search.vector import remove_document
    remove_document(doc_id)
    return conn.total_changes > 0


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


def add_note(content: str, title: str = "", document_id: Optional[int] = None) -> Note:
    conn = get_db()
    _migrate(conn)
    now = _now()
    cur = conn.execute(
        "INSERT INTO notes (title, content, document_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, content, document_id, now, now),
    )
    conn.commit()
    note_id = cur.lastrowid
    from core.search.vector import index_note
    index_note(note_id, title, content)
    return get_note(note_id)


def get_note(note_id: int) -> Optional[Note]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        return None
    return Note(id=row["id"], title=row["title"], content=row["content"],
                document_id=row["document_id"], created_at=row["created_at"], updated_at=row["updated_at"])


def list_notes(document_id: Optional[int] = None, limit: int = 50) -> list[Note]:
    conn = get_db()
    _migrate(conn)
    if document_id:
        rows = conn.execute(
            "SELECT * FROM notes WHERE document_id = ? ORDER BY created_at DESC LIMIT ?",
            (document_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [Note(id=r["id"], title=r["title"], content=r["content"],
                 document_id=r["document_id"], created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]


def search_notes(query: str, limit: int = 20) -> list[Note]:
    conn = get_db()
    _migrate(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM notes WHERE content LIKE ? OR title LIKE ? ORDER BY created_at DESC LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [Note(id=r["id"], title=r["title"], content=r["content"],
                 document_id=r["document_id"], created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]


def edit_note(note_id: int, content: str, title: Optional[str] = None) -> Optional[Note]:
    conn = get_db()
    _migrate(conn)
    now = _now()
    if title is not None:
        conn.execute("UPDATE notes SET content = ?, title = ?, updated_at = ? WHERE id = ?",
                     (content, title, now, note_id))
    else:
        conn.execute("UPDATE notes SET content = ?, updated_at = ? WHERE id = ?",
                     (content, now, note_id))
    conn.commit()
    return get_note(note_id)


def delete_note(note_id: int) -> bool:
    conn = get_db()
    _migrate(conn)
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return conn.total_changes > 0
