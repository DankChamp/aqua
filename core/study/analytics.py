from datetime import datetime, date, timedelta

from core.deps import get_db
from core.activity import get_streak, _migrate as activity_migrate
from core.study.flashcards import _migrate as flashcards_migrate
from core.documents.manager import _migrate as docs_migrate
from core.study.plans import _migrate as plans_migrate


def get_study_stats() -> dict:
    conn = get_db()
    activity_migrate(conn)
    flashcards_migrate(conn)
    docs_migrate(conn)
    plans_migrate(conn)

    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    card_count = conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0]
    review_count = conn.execute(
        "SELECT COALESCE(SUM(review_count), 0) FROM flashcards"
    ).fetchone()[0]

    due_cards = conn.execute(
        "SELECT COUNT(*) FROM flashcards WHERE next_review_at IS NOT NULL AND next_review_at <= ?",
        (datetime.utcnow().isoformat(),),
    ).fetchone()[0]

    quiz_count = conn.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    quiz_graded = conn.execute(
        "SELECT COUNT(*) FROM quizzes WHERE score IS NOT NULL"
    ).fetchone()[0]

    avg_score = conn.execute(
        "SELECT COALESCE(AVG(score), 0) FROM quizzes WHERE score IS NOT NULL"
    ).fetchone()[0]

    total_questions = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM quizzes"
    ).fetchone()[0]

    total_plans = conn.execute("SELECT COUNT(*) FROM study_plans").fetchone()[0]
    completed_tasks = conn.execute(
        "SELECT COUNT(*) FROM study_plan_tasks WHERE completed = 1"
    ).fetchone()[0]
    total_tasks = conn.execute(
        "SELECT COUNT(*) FROM study_plan_tasks"
    ).fetchone()[0]
    study_minutes = conn.execute(
        "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions"
    ).fetchone()[0]

    streak = get_streak()

    return {
        "documents": doc_count,
        "notes": note_count,
        "flashcards": card_count,
        "total_reviews": review_count,
        "due_cards": due_cards,
        "quizzes": quiz_count,
        "quizzes_graded": quiz_graded,
        "avg_score": round(avg_score, 1),
        "total_questions": total_questions,
        "plans": total_plans,
        "tasks_completed": completed_tasks,
        "total_tasks": total_tasks,
        "study_minutes": study_minutes,
        "streak": streak,
    }


def get_quiz_history(limit: int = 10) -> list[dict]:
    conn = get_db()
    flashcards_migrate(conn)
    rows = conn.execute(
        "SELECT id, title, topic, score, total, created_at FROM quizzes "
        "WHERE score IS NOT NULL ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_daily_activity(days: int = 30) -> list[dict]:
    conn = get_db()
    activity_migrate(conn)
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT substr(created_at, 1, 10) as day, COUNT(*) as count "
        "FROM activity_log WHERE created_at >= ? "
        "GROUP BY day ORDER BY day ASC",
        (cutoff,),
    ).fetchall()
    result = []
    for r in rows:
        result.append({"date": r["day"], "count": r["count"]})
    day_map = {d["date"]: d["count"] for d in result}
    full = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        full.append({"date": d, "count": day_map.get(d, 0)})
    return full


def get_flashcard_reviews(days: int = 30) -> list[dict]:
    conn = get_db()
    flashcards_migrate(conn)
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT substr(last_reviewed, 1, 10) as day, COUNT(*) as count "
        "FROM flashcards WHERE last_reviewed >= ? "
        "GROUP BY day ORDER BY day ASC",
        (cutoff,),
    ).fetchall()
    day_map = {r["day"]: r["count"] for r in rows}
    full = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        full.append({"date": d, "count": day_map.get(d, 0)})
    return full


def get_quiz_score_trend(limit: int = 10) -> list[dict]:
    conn = get_db()
    flashcards_migrate(conn)
    rows = conn.execute(
        "SELECT id, title, score, total, created_at FROM quizzes "
        "WHERE score IS NOT NULL ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    result = []
    for r in reversed(rows):
        pct = round(r["score"] / r["total"] * 100, 1) if r["total"] > 0 else 0
        result.append({
            "id": r["id"],
            "title": r["title"],
            "score": r["score"],
            "total": r["total"],
            "pct": pct,
            "created_at": r["created_at"],
        })
    return result


def get_study_time_trend(days: int = 30) -> list[dict]:
    conn = get_db()
    plans_migrate(conn)
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT substr(started_at, 1, 10) as day, "
        "COALESCE(SUM(duration_minutes), 0) as minutes "
        "FROM study_sessions WHERE started_at >= ? "
        "GROUP BY day ORDER BY day ASC",
        (cutoff,),
    ).fetchall()
    day_map = {r["day"]: r["minutes"] for r in rows}
    full = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        full.append({"date": d, "minutes": day_map.get(d, 0)})
    return full
