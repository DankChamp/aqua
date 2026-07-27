from aqua.db.schema import engine, SessionLocal, Base
from aqua.db.models import (Document, Note, Flashcard, Quiz, QuizQuestion, Tag, document_tags)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
