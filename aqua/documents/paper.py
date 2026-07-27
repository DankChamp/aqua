from aqua.db import get_session, Document, Tag, Note


def add_document(
    title: str,
    content: str = "",
    authors: str = "",
    source: str = "manual",
    source_url: str = "",
    file_path: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> Document:
    session = get_session()
    try:
        doc = Document(
            title=title,
            content=content,
            authors=authors,
            source=source,
            source_url=source_url,
            file_path=file_path,
            summary=summary,
            metadata_json=metadata or {},
        )
        if tags:
            for tag_name in tags:
                tag = session.query(Tag).filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    session.add(tag)
                doc.tags.append(tag)

        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc
    finally:
        session.close()


def list_documents(tag: str | None = None, source: str | None = None, limit: int = 50) -> list[Document]:
    session = get_session()
    try:
        query = session.query(Document)
        if tag:
            query = query.filter(Document.tags.any(Tag.name == tag))
        if source:
            query = query.filter(Document.source == source)
        return query.order_by(Document.created_at.desc()).limit(limit).all()
    finally:
        session.close()


def get_document(doc_id: int) -> Document | None:
    session = get_session()
    try:
        return session.query(Document).filter_by(id=doc_id).first()
    finally:
        session.close()


def search_documents(query: str, limit: int = 20) -> list[Document]:
    session = get_session()
    try:
        return (
            session.query(Document)
            .filter(Document.content.ilike(f"%{query}%"))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def delete_document(doc_id: int) -> bool:
    session = get_session()
    try:
        doc = session.query(Document).filter_by(id=doc_id).first()
        if doc:
            session.delete(doc)
            session.commit()
            return True
        return False
    finally:
        session.close()
