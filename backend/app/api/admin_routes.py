from fastapi import APIRouter, Depends
from app.dependencies import get_authenticated_user
from app.models.user_model import User
from app.services.db_query_service import check_db_connection, get_database_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/health")
async def health():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }


@router.get("/stats")
async def stats(user: User = Depends(get_authenticated_user)):
    return get_database_stats()
