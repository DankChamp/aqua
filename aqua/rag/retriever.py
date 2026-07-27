from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aqua.rag.vector_store import VectorStore

_store = None


def get_store():
    global _store
    if _store is None:
        from aqua.rag.vector_store import VectorStore
        _store = VectorStore()
    return _store


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def index_document(document_id: int, content: str):
    store = get_store()
    chunks = chunk_text(content)
    embedding_ids = store.add_document_chunks(document_id, chunks)
    return chunks, embedding_ids


def search(query: str, n_results: int = 5, document_id: int | None = None) -> list[dict]:
    store = get_store()
    return store.search(query, n_results=n_results, document_id=document_id)


def delete_document(document_id: int):
    store = get_store()
    store.delete_document_chunks(document_id)
