import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float,
    ForeignKey, Table, JSON,
)
from sqlalchemy.orm import relationship

from aqua.db.schema import Base

document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id")),
    Column("tag_id", Integer, ForeignKey("tags.id")),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), default="")
    source = Column(String(50), default="manual")  # manual, pdf, url, arxiv
    source_url = Column(String(1000), default="")
    file_path = Column(String(1000), default="")
    content = Column(Text, default="")
    summary = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    tags = relationship("Tag", secondary=document_tags, lazy="selectin")
    notes = relationship("Note", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(100), default="")

    document = relationship("Document", back_populates="chunks")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    title = Column(String(500), default="")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="notes")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    topic = Column(String(200), default="")
    difficulty = Column(Integer, default=1)  # 1-5
    review_count = Column(Integer, default=0)
    last_reviewed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), default="")
    topic = Column(String(200), default="")
    score = Column(Float, nullable=True)
    total = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, default=list)  # list of strings for multiple choice
    correct_answer = Column(String(500), nullable=False)
    user_answer = Column(String(500), nullable=True)
    is_correct = Column(Integer, nullable=True)

    quiz = relationship("Quiz", back_populates="questions")
