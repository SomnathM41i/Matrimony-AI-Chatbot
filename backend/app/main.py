from contextlib import asynccontextmanager
import time
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.core.logger import logger
from app.core.limiter import limiter
from app.database import create_tables


class RequestLoggingMiddleware:
    """Assigns an X-Request-ID to every request and logs method/path/status/duration.

    Uses a pure ASGI middleware (instead of BaseHTTPMiddleware) so that
    Server-Sent Events / streaming responses are not buffered.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        request_id = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode("latin-1", errors="ignore")[:64] or None
                break
        if not request_id:
            request_id = uuid.uuid4().hex[:12]
        scope["request_id"] = request_id

        status_code = None
        method = scope.get("method", "?")
        path = scope.get("path", "?")

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000)
            code = status_code or 0
            log_fn = logger.warning if code >= 400 else logger.info
            log_fn(
                "http %s %s -> %s [%sms] [req=%s]",
                method, path, code, duration_ms, request_id,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"myvivahai Chatbot starting [{settings.APP_ENV}]")
    await create_tables()

    from app.services.schema_discovery import refresh_cache
    refresh_cache()

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

app.add_middleware(RequestLoggingMiddleware)

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
from app.api.profile_routes import router as profile_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(commercial_admin_router)
app.include_router(profile_router)


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
                "ollama": "qwen2.5:7b-instruct",
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
