import sqlite3
from datetime import datetime, date, timedelta

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


def _today_str() -> str:
    return date.today().isoformat()


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


def get_streak() -> dict:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute(
        "SELECT DISTINCT substr(created_at, 1, 10) as day FROM activity_log ORDER BY day DESC"
    ).fetchall()
    unique_days = [r["day"] for r in rows if r["day"]]

    streak = 0
    today_iso = _today_str()
    check = today_iso
    today_count = 0

    for day_str in unique_days:
        if day_str == today_iso:
            today_count += 1
            continue
        break

    today_activity = conn.execute(
        "SELECT COUNT(*) as c FROM activity_log WHERE substr(created_at, 1, 10) = ?",
        (today_iso,),
    ).fetchone()
    today_count = today_activity["c"] if today_activity else 0

    if today_count > 0:
        streak = 1
        check = (date.today() - timedelta(days=1)).isoformat()
    else:
        check = today_iso

    for day_str in unique_days:
        if day_str == check:
            streak += 1
            check = (date.fromisoformat(check) - timedelta(days=1)).isoformat()
        elif day_str < check:
            break

    return {"streak": streak, "today_count": today_count, "today": today_iso}
