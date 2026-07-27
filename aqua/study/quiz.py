import random

from aqua.db import get_session, Quiz, QuizQuestion


def create_quiz(title: str, topic: str, questions_data: list[dict]) -> Quiz:
    session = get_session()
    try:
        quiz = Quiz(title=title, topic=topic)
        session.add(quiz)
        session.flush()

        for q_data in questions_data:
            q = QuizQuestion(
                quiz_id=quiz.id,
                question=q_data["question"],
                options=q_data.get("options", []),
                correct_answer=q_data["correct_answer"],
            )
            session.add(q)

        session.commit()
        session.refresh(quiz)
        return quiz
    finally:
        session.close()


def get_quiz(quiz_id: int) -> Quiz | None:
    session = get_session()
    try:
        return session.query(Quiz).filter_by(id=quiz_id).first()
    finally:
        session.close()


def list_quizzes(limit: int = 20) -> list[Quiz]:
    session = get_session()
    try:
        return session.query(Quiz).order_by(Quiz.created_at.desc()).limit(limit).all()
    finally:
        session.close()


def submit_answer(question_id: int, answer: str) -> QuizQuestion | None:
    session = get_session()
    try:
        q = session.query(QuizQuestion).filter_by(id=question_id).first()
        if q:
            q.user_answer = answer
            q.is_correct = 1 if answer.strip().lower() == q.correct_answer.strip().lower() else 0
            session.commit()
            session.refresh(q)
        return q
    finally:
        session.close()


def grade_quiz(quiz_id: int) -> dict | None:
    session = get_session()
    try:
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            return None

        correct = sum(1 for q in quiz.questions if q.is_correct == 1)
        total = len(quiz.questions)
        score = (correct / total * 100) if total > 0 else 0

        quiz.score = score
        quiz.total = total
        session.commit()

        return {"score": score, "correct": correct, "total": total}
    finally:
        session.close()
