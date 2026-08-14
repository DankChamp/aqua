import sqlite3
import re
from datetime import datetime
from typing import Optional

from core.deps import get_db


def _migrate(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def get_all() -> list[dict]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute("SELECT * FROM profile WHERE key != 'system_prompt' ORDER BY category, key").fetchall()
    return [dict(r) for r in rows]


def get(key: str) -> Optional[str]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set(key: str, value: str, category: str = ""):
    conn = get_db()
    _migrate(conn)
    now = _now()
    conn.execute(
        "INSERT INTO profile (key, value, category, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?, category = ?, updated_at = ?",
        (key, value, category, now, value, category, now),
    )
    conn.commit()


def delete(key: str) -> bool:
    conn = get_db()
    _migrate(conn)
    cur = conn.execute("DELETE FROM profile WHERE key = ?", (key,))
    conn.commit()
    return cur.rowcount > 0


def get_system_prompt() -> str:
    return get("system_prompt") or ""


def set_system_prompt(text: str):
    set("system_prompt", text, "system")


def remember_from_text(text: str, category: str = "memory") -> Optional[dict]:
    """
    Store user facts when they explicitly ask Aqua to remember something,
    plus common personal facts that are usually intended as memory.
    """
    value = _extract_memory_value(text)
    if not value:
        return None

    key = _memory_key(value)
    set(key, value, category)
    return {"key": key, "value": value, "category": category}


def _extract_memory_value(text: str) -> Optional[str]:
    clean = " ".join((text or "").strip().split())
    if not clean:
        return None

    explicit_patterns = [
        r"\b(?:please\s+)?remember(?:\s+that)?\s+(.+)",
        r"\b(?:you\s+should\s+|you\s+need\s+to\s+)?remember(?:\s+that)?\s+(.+)",
        r"\b(?:keep|note)\s+(?:in\s+mind\s+)?(?:that\s+)?(.+)",
        r"\b(?:save|store)\s+(?:this|that|it)?\s*(?:fact|memory)?\s*:?\s*(.+)",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            return _normalize_memory(match.group(1))

    personal_fact_patterns = [
        r"\b(my\s+(?:name|nickname|exam|goal|target|school|college|class|grade|subject|chapter|preference|weakness|strength|schedule)\s+is\s+.+)",
        r"\b(i\s+(?:like|love|hate|prefer|struggle\s+with|need\s+help\s+with|want\s+to\s+learn)\s+.+)",
        r"\b(i\s+am\s+(?:in\s+class|in\s+grade|preparing\s+for|studying|weak\s+in|strong\s+in|interested\s+in)\s+.+)",
    ]
    for pattern in personal_fact_patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            return _normalize_memory(match.group(1))
    return None


def _normalize_memory(value: str) -> Optional[str]:
    value = value.strip(" .!?:;\"'")
    if len(value) < 3:
        return None
    return value[:500]


def _memory_key(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:42]
    if not slug:
        slug = "fact"
    key = f"memory_{slug}"
    if len(key) > 64:
        key = key[:64].rstrip("_")
    return key


def to_context_block() -> str:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT key, value, category FROM profile WHERE key != 'system_prompt' ORDER BY category, key"
    ).fetchall()
    if not rows:
        return ""
    lines = ["\n== About You =="]
    for r in rows:
        cat = f" ({r['category']})" if r["category"] else ""
        lines.append(f"{r['key']}: {r['value']}{cat}")
    return "\n".join(lines)
