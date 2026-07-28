import json
import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from core.deps import get_db


@dataclass
class Flashcard:
    id: Optional[int] = None
    question: str = ""
    answer: str = ""
    topic: str = ""
    difficulty: int = 1
    review_count: int = 0
    last_reviewed: Optional[str] = None
    created_at: str = ""


@dataclass
class Quiz:
    id: Optional[int] = None
    title: str = ""
    topic: str = ""
    score: Optional[float] = None
    total: int = 0
    questions: list = None
    created_at: str = ""


def _migrate(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL DEFAULT '',
            answer TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            difficulty INTEGER NOT NULL DEFAULT 1,
            review_count INTEGER NOT NULL DEFAULT 0,
            last_reviewed TEXT,
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            score REAL,
            total INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL DEFAULT '',
            options TEXT NOT NULL DEFAULT '[]',
            correct_answer TEXT NOT NULL DEFAULT '',
            user_answer TEXT,
            is_correct INTEGER DEFAULT 0
        );
    """)


def _now() -> str:
    return datetime.utcnow().isoformat()


def add_flashcard(question: str, answer: str, topic: str = "", difficulty: int = 1) -> Flashcard:
    conn = get_db()
    _migrate(conn)
    cur = conn.execute(
        "INSERT INTO flashcards (question, answer, topic, difficulty, created_at) VALUES (?, ?, ?, ?, ?)",
        (question, answer, topic, difficulty, _now()),
    )
    conn.commit()
    from core.activity import add_activity
    add_activity("added_flashcard", f"{topic}: {question[:60]}", chapter=topic)
    return get_flashcard(cur.lastrowid)


def get_flashcard(card_id: int) -> Optional[Flashcard]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        return None
    return Flashcard(**dict(row))


def list_flashcards(topic: Optional[str] = None, limit: int = 100) -> list[Flashcard]:
    conn = get_db()
    _migrate(conn)
    if topic:
        rows = conn.execute(
            "SELECT * FROM flashcards WHERE topic = ? ORDER BY last_reviewed ASC NULLS FIRST LIMIT ?",
            (topic, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM flashcards ORDER BY last_reviewed ASC NULLS FIRST LIMIT ?", (limit,)
        ).fetchall()
    return [Flashcard(**dict(r)) for r in rows]


def review_flashcard(card_id: int, correct: bool) -> Optional[Flashcard]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        return None
    card = Flashcard(**dict(row))
    card.review_count += 1
    card.last_reviewed = _now()
    card.difficulty = max(1, card.difficulty - 1) if correct else min(5, card.difficulty + 1)
    conn.execute(
        "UPDATE flashcards SET review_count = ?, last_reviewed = ?, difficulty = ? WHERE id = ?",
        (card.review_count, card.last_reviewed, card.difficulty, card_id),
    )
    conn.commit()
    return card


def delete_flashcard(card_id: int) -> bool:
    conn = get_db()
    _migrate(conn)
    conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
    conn.commit()
    return conn.total_changes > 0


def create_quiz(title: str, topic: str, questions_data: list[dict]) -> Quiz:
    conn = get_db()
    _migrate(conn)
    now = _now()
    cur = conn.execute(
        "INSERT INTO quizzes (title, topic, total, created_at) VALUES (?, ?, ?, ?)",
        (title, topic, len(questions_data), now),
    )
    quiz_id = cur.lastrowid
    for qd in questions_data:
        conn.execute(
            "INSERT INTO quiz_questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)",
            (quiz_id, qd["question"], json.dumps(qd.get("options", [])), qd["correct_answer"]),
        )
    conn.commit()
    from core.activity import add_activity
    add_activity("generated_quiz", f"{title} ({len(questions_data)} questions)", chapter=topic)
    return get_quiz(quiz_id)


def get_quiz(quiz_id: int) -> Optional[Quiz]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not row:
        return None
    q_rows = conn.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?", (quiz_id,)).fetchall()
    quiz = Quiz(id=row["id"], title=row["title"], topic=row["topic"],
                score=row["score"], total=row["total"], created_at=row["created_at"], questions=[])
    for qr in q_rows:
        quiz.questions.append({
            "id": qr["id"],
            "question": qr["question"],
            "options": json.loads(qr["options"]),
            "correct_answer": qr["correct_answer"],
            "user_answer": qr["user_answer"],
            "is_correct": qr["is_correct"],
        })
    return quiz


def list_quizzes(limit: int = 20) -> list[Quiz]:
    conn = get_db()
    _migrate(conn)
    rows = conn.execute("SELECT * FROM quizzes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [Quiz(id=r["id"], title=r["title"], topic=r["topic"],
                 score=r["score"], total=r["total"], created_at=r["created_at"]) for r in rows]


def submit_answer(question_id: int, answer: str) -> bool:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,)).fetchone()
    if not row:
        return False
    correct = answer.strip().lower() == row["correct_answer"].strip().lower()
    conn.execute(
        "UPDATE quiz_questions SET user_answer = ?, is_correct = ? WHERE id = ?",
        (answer, 1 if correct else 0, question_id),
    )
    conn.commit()
    return True


def grade_quiz(quiz_id: int) -> Optional[dict]:
    conn = get_db()
    _migrate(conn)
    row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not row:
        return None
    rows = conn.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?", (quiz_id,)).fetchall()
    correct = sum(1 for r in rows if r["is_correct"] == 1)
    total = len(rows)
    score = (correct / total * 100) if total > 0 else 0
    conn.execute("UPDATE quizzes SET score = ?, total = ? WHERE id = ?", (score, total, quiz_id))
    conn.commit()
    return {"score": score, "correct": correct, "total": total}
