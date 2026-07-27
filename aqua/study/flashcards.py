import datetime

from aqua.db import get_session, Flashcard


def add_flashcard(question: str, answer: str, topic: str = "", difficulty: int = 1) -> Flashcard:
    session = get_session()
    try:
        card = Flashcard(question=question, answer=answer, topic=topic, difficulty=difficulty)
        session.add(card)
        session.commit()
        session.refresh(card)
        return card
    finally:
        session.close()


def list_flashcards(topic: str | None = None, limit: int = 100) -> list[Flashcard]:
    session = get_session()
    try:
        query = session.query(Flashcard)
        if topic:
            query = query.filter(Flashcard.topic == topic)
        return query.order_by(Flashcard.last_reviewed.asc().nullsfirst()).limit(limit).all()
    finally:
        session.close()


def review_flashcard(card_id: int, correct: bool) -> Flashcard | None:
    session = get_session()
    try:
        card = session.query(Flashcard).filter_by(id=card_id).first()
        if card:
            card.review_count += 1
            card.last_reviewed = datetime.datetime.utcnow()
            if correct:
                card.difficulty = max(1, card.difficulty - 1)
            else:
                card.difficulty = min(5, card.difficulty + 1)
            session.commit()
            session.refresh(card)
        return card
    finally:
        session.close()


def delete_flashcard(card_id: int) -> bool:
    session = get_session()
    try:
        card = session.query(Flashcard).filter_by(id=card_id).first()
        if card:
            session.delete(card)
            session.commit()
            return True
        return False
    finally:
        session.close()
