import asyncio
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_authenticated_user
from app.models.user_model import User
from app.services.db_query_service import get_database_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def stats(user: User = Depends(get_authenticated_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return await asyncio.to_thread(get_database_stats)
