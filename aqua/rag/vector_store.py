import uuid

from aqua.config import load_config


class VectorStore:
    def __init__(self):
        import chromadb
        from chromadb.config import Settings

        config = load_config()
        self.client = chromadb.PersistentClient(
            path=config["chroma_path"],
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="aqua_documents",
            metadata={"hnsw:space": "cosine"},
        )

    def add_document_chunks(self, document_id: int, chunks: list[str]) -> list[str]:
        from aqua.rag.embeddings import embed_texts

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
        embeddings = embed_texts(chunks)

        self.collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return ids

    def search(self, query: str, n_results: int = 5, document_id: int | None = None) -> list[dict]:
        from aqua.rag.embeddings import embed_texts
        query_embedding = embed_texts([query])[0]

        where = None
        if document_id is not None:
            where = {"document_id": document_id}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )

        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "score": results["distances"][0][i],
                "metadata": results["metadatas"][0][i],
            })
        return output

    def delete_document_chunks(self, document_id: int):
        self.collection.delete(where={"document_id": document_id})
