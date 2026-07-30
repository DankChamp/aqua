import sqlite3
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
