import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.logger import logger


DEFAULT_MODEL = "BAAI/bge-m3"
FALLBACK_MODEL = "intfloat/multilingual-e5-small"

_model_instance = None
_model_name = None


def get_embedding_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    global _model_instance, _model_name
    if _model_instance is None or _model_name != model_name:
        logger.info(f"Loading embedding model: {model_name}")
        _model_instance = SentenceTransformer(model_name)
        _model_name = model_name
        logger.info(f"Embedding model loaded. Dimension: {_model_instance.get_sentence_embedding_dimension()}")
    return _model_instance


def get_embedding_dimension(model_name: str = DEFAULT_MODEL) -> int:
    model = get_embedding_model(model_name)
    return model.get_sentence_embedding_dimension()


def embed_text(text: str, model_name: str = DEFAULT_MODEL) -> list[float]:
    model = get_embedding_model(model_name)
    embedding = model.encode(text, normalize_embeddings=True)
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return list(embedding)


def embed_batch(texts: list[str], model_name: str = DEFAULT_MODEL) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [e.tolist() if isinstance(e, np.ndarray) else list(e) for e in embeddings]


def build_profile_document(profile: dict) -> str:
    parts = []
    for key, value in profile.items():
        if value and key not in (
            "MatriID", "Photo1", "PhotoURL", "Password",
            "Status", "Regdate", "password", "Mobile",
        ):
            if isinstance(value, str):
                value = value.strip()
                if value and value.lower() not in ("nophoto.jpg", "", "null", "none"):
                    parts.append(f"{key}: {value}")
    return ". ".join(parts)
