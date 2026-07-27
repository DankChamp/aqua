from aqua.config import load_config

_model = None


def get_embedding_model():
    global _model
    if _model is not None:
        return _model

    config = load_config()
    provider = config["embeddings"]["provider"]

    if provider == "sentence-transformers":
        from sentence_transformers import SentenceTransformer

        model_name = config["embeddings"]["model"]
        _model = SentenceTransformer(model_name)
        return _model
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts).tolist()
