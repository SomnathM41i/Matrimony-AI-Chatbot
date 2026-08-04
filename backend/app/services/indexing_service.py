import asyncio
from app.core.logger import logger
from app.config import settings
from app.services.db_query_service import execute_param_query, safe_query
from app.services.embedding_service import build_profile_document, embed_batch, get_embedding_dimension
from app.services.vector_service import (
    upsert_batch, delete_collection, hash_id,
    COLLECTION_NAME,
)
from app.services.query_builder import build_profile_query
from app.services.db_query_service import sanitize_rows


def _fetch_all_active_profile_rows() -> list[dict]:
    sql = (
        "SELECT MatriID, Name, Age, Gender, Maritalstatus, Religion, Caste, "
        "City, Dist, State, Education, Occupation, Annualincome, Height, "
        "Photo1 "
        "FROM register WHERE LOWER(Status) = LOWER('Active') "
        "ORDER BY Regdate DESC"
    )
    return safe_query(sql)


async def fetch_all_active_profiles() -> list[dict]:
    return await asyncio.to_thread(_fetch_all_active_profile_rows)


async def reindex_all():
    logger.info("Starting full profile re-index...")
    rows = await fetch_all_active_profiles()
    if not rows:
        logger.info("No active profiles to index.")
        return

    clean = sanitize_rows(rows)
    logger.info(f"Total active profiles: {len(clean)}")

    from app.services.vector_service import get_client
    client = get_client(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
    )

    collections = client.get_collections().collections
    if any(c.name == COLLECTION_NAME for c in collections):
        logger.info("Re-creating collection for fresh index...")
        delete_collection(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    from app.services.vector_service import _ensure_collection
    _ensure_collection(client)

    embed_batch_size = 100
    total = len(clean)
    logger.info(f"Embedding and indexing {total} profiles in batches of {embed_batch_size}...")

    for i in range(0, total, embed_batch_size):
        batch_rows = clean[i:i + embed_batch_size]
        documents = [build_profile_document(r) for r in batch_rows]

        batch_embs = await embed_batch(documents)
        if not batch_embs:
            logger.warning(f"No embeddings for batch {i}-{i + len(batch_rows)}, skipping")
            continue

        points = []
        for row, vec in zip(batch_rows, batch_embs):
            from app.services.db_query_service import add_photo_url
            add_photo_url(row)
            points.append({
                "MatriID": row.get("MatriID", ""),
                "_vector": vec,
                "Name": row.get("Name", ""),
                "Age": row.get("Age"),
                "Gender": row.get("Gender", ""),
                "Caste": row.get("Caste", ""),
                "City": row.get("City", ""),
                "Dist": row.get("Dist", ""),
                "State": row.get("State", ""),
                "Religion": row.get("Religion", ""),
                "Maritalstatus": row.get("Maritalstatus", ""),
                "Education": row.get("Education", ""),
                "Occupation": row.get("Occupation", ""),
                "Photo1": row.get("Photo1", ""),
                "PhotoURL": row.get("PhotoURL", ""),
            })
        upsert_batch(points, host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        pct = min(i + embed_batch_size, total)
        logger.info(f"Indexed {pct}/{total} profiles ({(pct/total)*100:.0f}%)")

    logger.info(f"Re-index complete: {total} profiles indexed.")
