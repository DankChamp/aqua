import sqlite3
from functools import lru_cache

from config import get_settings


_db_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        settings = get_settings()
        _db_conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA busy_timeout=5000")
    return _db_conn


@lru_cache
def get_router():
    from core.router import AIRouter
    return AIRouter(get_settings())
