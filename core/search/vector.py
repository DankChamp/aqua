import logging
from typing import Optional

logger = logging.getLogger("aqua.search")

_client = None
_HAS_CHROMA = False
_ONNX_EF = None


def _lazy_init():
    global _client, _HAS_CHROMA, _ONNX_EF
    if _client is not None:
        return
    try:
        import chromadb
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        _client = chromadb.PersistentClient(
            path=str(__import__("config").get_settings().db_path.parent / "chroma")
        )
        _ONNX_EF = ONNXMiniLM_L6_V2()
        _HAS_CHROMA = True
        logger.info("ChromaDB + ONNX MiniLM loaded")
    except Exception as exc:
        logger.warning("Vector search unavailable: %s", exc)
        _HAS_CHROMA = False


def _coll(name: str):
    _lazy_init()
    if not _HAS_CHROMA:
        return None
    try:
        return _client.get_or_create_collection(name, embedding_function=_ONNX_EF)
    except Exception:
        return None


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    for w in words:
        if current_len + len(w) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(w)
        current_len += len(w) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks if chunks else [text[:max_chars]]


def index_document(doc_id: int, title: str, content: str):
    col = _coll("documents")
    if col is None:
        return
    chunks = _chunk_text(f"{title}\n{content}")
    ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metas = [{"source": "document", "doc_id": str(doc_id), "title": title, "chunk": str(i)} for i in range(len(chunks))]
    try:
        existing = col.get(where={"doc_id": str(doc_id)})
        if existing and existing["ids"]:
            col.delete(ids=existing["ids"])
        col.add(documents=chunks, ids=ids, metadatas=metas)
        logger.info("Indexed document %s (%d chunks)", doc_id, len(chunks))
    except Exception as exc:
        logger.warning("Failed to index document %s: %s", doc_id, exc)


def remove_document(doc_id: int):
    col = _coll("documents")
    if col is None:
        return
    try:
        existing = col.get(where={"doc_id": str(doc_id)})
        if existing and existing["ids"]:
            col.delete(ids=existing["ids"])
    except Exception:
        pass


def index_note(note_id: int, title: str, content: str):
    col = _coll("notes")
    if col is None:
        return
    try:
        col.add(
            documents=[f"{title}\n{content}"],
            ids=[f"note_{note_id}"],
            metadatas=[{"source": "note", "note_id": str(note_id), "title": title}],
        )
        logger.info("Indexed note %s", note_id)
    except Exception as exc:
        logger.warning("Failed to index note %s: %s", note_id, exc)


def search_chunks(query: str, top_k: int = 3) -> list[dict]:
    _lazy_init()
    if not _HAS_CHROMA:
        return []
    results = []
    for col_name in ("documents", "notes"):
        col = _coll(col_name)
        if col is None:
            continue
        try:
            res = col.query(query_texts=[query], n_results=top_k)
            if res and res["ids"] and res["ids"][0]:
                for i, doc_id in enumerate(res["ids"][0]):
                    meta = res["metadatas"][0][i] if res["metadatas"] else {}
                    results.append({
                        "id": doc_id,
                        "text": res["documents"][0][i][:500] if res["documents"] else "",
                        "score": float(res["distances"][0][i]) if res.get("distances") else 0.0,
                        "source": meta.get("source", "unknown"),
                        "title": meta.get("title", ""),
                    })
        except Exception as exc:
            logger.debug("Search failed on %s: %s", col_name, exc)
    results.sort(key=lambda x: x["score"])
    return results[:top_k]


def hybrid_search(query: str, limit: int = 10) -> dict:
    from core.documents.manager import search_documents as text_search_docs
    from core.documents.manager import search_notes as text_search_notes

    docs = text_search_docs(query, limit=limit)
    notes = text_search_notes(query, limit=limit)
    vec = search_chunks(query, top_k=limit)

    return {
        "documents": [{"id": d.id, "title": d.title, "content": d.content[:500]} for d in docs],
        "notes": [{"id": n.id, "title": n.title, "content": n.content[:500]} for n in notes],
        "vector": vec,
    }
