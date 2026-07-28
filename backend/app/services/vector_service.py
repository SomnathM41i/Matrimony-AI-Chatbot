import time
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.logger import logger


COLLECTION_NAME = "profiles"
VECTOR_SIZE = 1024
PAYLOAD_INDEXED_FIELDS = ["Gender", "Caste", "City", "Religion", "Maritalstatus"]

MAX_UPSERT_RETRIES = 3


_client_instance = None


def get_client(host: str = "localhost", port: int = 6333) -> QdrantClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = QdrantClient(host=host, port=port, timeout=120)
        _ensure_collection(_client_instance)
    return _client_instance


def _ensure_collection(client: QdrantClient):
    collections = client.get_collections().collections
    if any(c.name == COLLECTION_NAME for c in collections):
        return
    logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )
    for field in PAYLOAD_INDEXED_FIELDS:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_type=models.PayloadSchemaType.KEYWORD,
        )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="Age",
        field_type=models.PayloadSchemaType.INTEGER,
    )


def upsert_profile(matri_id: str, vector: list[float], payload: dict, host: str = "localhost", port: int = 6333):
    client = get_client(host=host, port=port)
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[models.PointStruct(id=hash_id(matri_id), vector=vector, payload=payload)],
    )


def upsert_batch(profiles: list[dict], host: str = "localhost", port: int = 6333):
    if not profiles:
        return
    client = get_client(host=host, port=port)
    points = []
    for p in profiles:
        points.append(models.PointStruct(
            id=hash_id(p.get("MatriID", "")),
            vector=p.get("_vector", []),
            payload={k: v for k, v in p.items() if not k.startswith("_")},
        ))
    for attempt in range(MAX_UPSERT_RETRIES):
        try:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            return
        except Exception as e:
            if attempt < MAX_UPSERT_RETRIES - 1:
                logger.warning(f"Upsert failed (attempt {attempt + 1}), retrying: {e}")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Upsert failed after {MAX_UPSERT_RETRIES} attempts: {e}")
                raise


def hash_id(matri_id: str) -> int:
    return abs(hash(matri_id)) % (2**63 - 1)


def search_with_filters(
    query_vector: list[float],
    filters: dict | None = None,
    limit: int = 10,
    host: str = "localhost",
    port: int = 6333,
) -> list[dict]:
    client = get_client(host=host, port=port)
    must_conditions = []

    if filters:
        gender = filters.get("gender")
        if gender:
            must_conditions.append(models.FieldCondition(
                key="Gender", match=models.MatchValue(value=gender.capitalize()),
            ))

        caste = filters.get("caste")
        if caste:
            must_conditions.append(models.FieldCondition(
                key="Caste", match=models.MatchValue(value=caste),
            ))

        city = filters.get("city")
        if city:
            must_conditions.append(models.FieldCondition(
                key="City", match=models.MatchValue(value=city),
            ))

        religion = filters.get("religion")
        if religion:
            must_conditions.append(models.FieldCondition(
                key="Religion", match=models.MatchValue(value=religion.capitalize()),
            ))

        marital_status = filters.get("marital_status")
        if marital_status:
            must_conditions.append(models.FieldCondition(
                key="Maritalstatus", match=models.MatchValue(value=marital_status),
            ))

        age_min = filters.get("age_min")
        if age_min is not None:
            must_conditions.append(models.FieldCondition(
                key="Age", range=models.Range(gte=age_min),
            ))

        age_max = filters.get("age_max")
        if age_max is not None:
            must_conditions.append(models.FieldCondition(
                key="Age", range=models.Range(lte=age_max),
            ))

    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
    )

    return [r.payload for r in results.points if r.score >= 0.5]


def delete_collection(host: str = "localhost", port: int = 6333):
    client = get_client(host=host, port=port)
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted collection: {COLLECTION_NAME}")
    except Exception:
        pass
