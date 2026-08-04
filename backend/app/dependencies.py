from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db_session
from app.core.auth import get_current_user
from app.models.user_model import User


# get_db must be the SAME dependency callable as get_db_session so that the
# authenticated `user` object (loaded in get_current_user via get_db_session)
# lives in the same SQLAlchemy session as the endpoint's `db`. Using two
# different generator dependencies here created two separate sessions per
# request, so mutations like user.matri_id = ... (set on the auth session's
# object) were silently lost when the endpoint committed the other session.
get_db = get_db_session


async def get_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


async def require_admin(
    current_user: User = Depends(get_authenticated_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
