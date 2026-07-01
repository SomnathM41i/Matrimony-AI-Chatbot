from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.core.auth import get_current_user
from app.models.user_model import User


async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


async def get_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
