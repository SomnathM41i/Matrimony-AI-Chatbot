from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.core.logger import logger
from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"myvivahai Chatbot starting [{settings.APP_ENV}]")
    await create_tables()
    yield
    logger.info("myvivahai Chatbot shutting down")


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

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
from app.api.commercial_routes import router as commercial_router
from app.api.commercial_admin_routes import router as commercial_admin_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(commercial_router)
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
    }


@app.get("/")
async def root():
    return {
        "status": "running",
        "app": "myvivahai AI Matrimony Chatbot",
        "version": "2.0.0",
        "docs": "/docs",
    }
