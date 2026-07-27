from aqua.db import get_session, Document, Note


def add_note(content: str, title: str = "", document_id: int | None = None) -> Note:
    session = get_session()
    try:
        note = Note(title=title, content=content, document_id=document_id)
        session.add(note)
        session.commit()
        session.refresh(note)
        return note
    finally:
        session.close()


def list_notes(document_id: int | None = None, limit: int = 50) -> list[Note]:
    session = get_session()
    try:
        query = session.query(Note)
        if document_id:
            query = query.filter(Note.document_id == document_id)
        return query.order_by(Note.created_at.desc()).limit(limit).all()
    finally:
        session.close()


def get_note(note_id: int) -> Note | None:
    session = get_session()
    try:
        return session.query(Note).filter_by(id=note_id).first()
    finally:
        session.close()


def search_notes(query: str, limit: int = 20) -> list[Note]:
    session = get_session()
    try:
        return (
            session.query(Note)
            .filter(Note.content.ilike(f"%{query}%"))
            .order_by(Note.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def edit_note(note_id: int, content: str, title: str | None = None) -> Note | None:
    session = get_session()
    try:
        note = session.query(Note).filter_by(id=note_id).first()
        if note:
            note.content = content
            if title is not None:
                note.title = title
            session.commit()
            session.refresh(note)
        return note
    finally:
        session.close()


def delete_note(note_id: int) -> bool:
    session = get_session()
    try:
        note = session.query(Note).filter_by(id=note_id).first()
        if note:
            session.delete(note)
            session.commit()
            return True
        return False
    finally:
        session.close()
