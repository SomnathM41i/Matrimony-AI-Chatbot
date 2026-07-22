from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.dependencies import get_db, get_authenticated_user
from app.schemas.auth_schema import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse, RefreshRequest
)
from app.schemas.common_schema import SuccessResponse
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.models.user_model import User
from app.models.chat_model import ChatMessage
from app.main import limiter
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    cookie_options = {
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        "access_token", access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **cookie_options,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **cookie_options,
    )


@router.post("/register", response_model=dict)
@limiter.limit("5/minute")
async def register(request: Request, response: Response, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        result = await auth_service.register(body.name, body.email, body.password)
        await db.commit()
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])
        return {
            "token_type": "bearer",
            "user": UserResponse.model_validate(result["user"]),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=dict)
@limiter.limit("10/minute")
async def login(request: Request, response: Response, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        result = await auth_service.login(body.email, body.password)
        await db.commit()
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])
        return {
            "token_type": "bearer",
            "user": UserResponse.model_validate(result["user"]),
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=dict)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise ValueError("Refresh token is missing")
        result = await auth_service.refresh_token(refresh_token)
        await db.commit()
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.coalesce(func.sum(ChatMessage.total_tokens), 0))
        .where(ChatMessage.user_id == user.id)
    )
    total_tokens = result.scalar() or 0
    resp = UserResponse.model_validate(user)
    resp.total_tokens = total_tokens
    return resp


@router.post("/logout", response_model=SuccessResponse)
async def logout(response: Response, user: User = Depends(get_authenticated_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return SuccessResponse(message="Logged out successfully")
