from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.core.logger import logger
from app.core.limiter import limiter
from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"myvivahai Chatbot starting [{settings.APP_ENV}]")
    await create_tables()

    from app.services.schema_discovery import refresh_cache
    refresh_cache()

    # Load the embedding model once here instead of inside the first user request.
    # Runs in a worker thread so startup and /health stay responsive.
    import asyncio
    from app.services.embedding_service import warmup_embedding_model
    # Keep a reference for the lifetime of the app so the task is not garbage collected.
    app.state.warmup_task = asyncio.create_task(asyncio.to_thread(warmup_embedding_model))

    try:
        from app.services.vector_service import get_client, COLLECTION_NAME
        client = get_client(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            logger.info("Qdrant collection not found, triggering auto re-index...")
            from app.services.indexing_service import reindex_all
            await reindex_all()
        else:
            col_info = client.get_collection(COLLECTION_NAME)
            points = getattr(col_info, 'points_count', getattr(col_info, 'vectors_count', 0))
            if points == 0:
                logger.info("Qdrant collection empty, triggering auto re-index...")
                from app.services.indexing_service import reindex_all
                await reindex_all()
            else:
                logger.info(f"Qdrant collection ready ({points} points)")
    except Exception as e:
        logger.warning(f"Qdrant not available at startup: {e}")

    yield
    logger.info("myvivahai Chatbot shutting down")


app = FastAPI(
    title="myvivahai Chatbot API",
    description="myvivahai - AI Matrimony Chatbot",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.auth_routes import router as auth_router
from app.api.chat_routes import router as chat_router
from app.api.history_routes import router as history_router
from app.api.admin_routes import router as admin_router
from app.api.commercial_admin_routes import router as commercial_admin_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(commercial_admin_router)


@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(content={"error": "Not found"}, status_code=404)


@app.exception_handler(500)
async def server_error(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(content={"error": "Internal server error"}, status_code=500)


@app.get("/health")
async def health():
    from app.services.db_query_service import check_db_connection
    db_ok = await check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "version": "2.0.0",
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": {
                "ollama": "qwen2.5:3b-instruct-q4_K_M",
                "groq": "llama-3.3-70b-versatile",
                "cerebras": "llama-3.3-70b",
                "gemini": "gemini-2.5-flash",
            }.get(settings.LLM_PROVIDER, "llama-3.3-70b-versatile"),
        },
    }


@app.get("/")
async def root():
    return {
        "status": "running",
        "app": "myvivahai AI Matrimony Chatbot",
        "version": "2.0.0",
        "docs": "/docs",
    }
