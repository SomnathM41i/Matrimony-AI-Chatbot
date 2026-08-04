import threading
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.core.logger import logger


# Single source of truth for the model name so every caller shares one instance.
DEFAULT_MODEL = settings.EMBEDDING_MODEL
FALLBACK_MODEL = "intfloat/multilingual-e5-small"

_model_instance = None
_model_name = None
_model_lock = threading.Lock()


def get_embedding_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    global _model_instance, _model_name
    if _model_instance is not None and _model_name == model_name:
        return _model_instance
    with _model_lock:
        # Re-check inside the lock: a concurrent caller may have loaded it already.
        if _model_instance is None or _model_name != model_name:
            logger.info(f"Loading embedding model: {model_name}")
            _model_instance = SentenceTransformer(model_name)
            _model_name = model_name
            logger.info(f"Embedding model loaded. Dimension: {_model_instance.get_sentence_embedding_dimension()}")
    return _model_instance


def warmup_embedding_model() -> None:
    """Load the model once at startup so no user request pays the load cost."""
    try:
        get_embedding_model()
    except Exception as e:
        logger.warning(f"Embedding model warmup failed: {e}")


def unload_embedding_model() -> None:
    """Release the embedding model from memory.

    The model (~2GB for bge-m3) is lazy-loaded on first use. Call this after
    a runtime semantic-search fallback completes so it is never kept resident
    between requests (important on RAM-constrained hosts).
    """
    global _model_instance, _model_name
    with _model_lock:
        if _model_instance is not None:
            logger.info("Unloading embedding model to free memory")
            _model_instance = None
            _model_name = None
            try:
                import gc
                gc.collect()
            except Exception:
                pass


def get_embedding_dimension(model_name: str = DEFAULT_MODEL) -> int:
    model = get_embedding_model(model_name)
    return model.get_sentence_embedding_dimension()


async def embed_text(text: str, model_name: str = DEFAULT_MODEL) -> list[float]:
    import asyncio
    model = get_embedding_model(model_name)

    def _encode():
        return model.encode(text, normalize_embeddings=True)

    embedding = await asyncio.to_thread(_encode)
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return list(embedding)


async def embed_batch(texts: list[str], model_name: str = DEFAULT_MODEL) -> list[list[float]]:
    import asyncio
    if not texts:
        return []
    model = get_embedding_model(model_name)

    def _encode():
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    embeddings = await asyncio.to_thread(_encode)
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
