from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_authenticated_user
from app.schemas.auth_schema import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse, RefreshRequest
)
from app.schemas.common_schema import SuccessResponse
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.models.user_model import User
from app.main import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=dict)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        result = await auth_service.register(body.name, body.email, body.password)
        await db.commit()
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": "bearer",
            "user": UserResponse.model_validate(result["user"]),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=dict)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        result = await auth_service.login(body.email, body.password)
        await db.commit()
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": "bearer",
            "user": UserResponse.model_validate(result["user"]),
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    try:
        result = await auth_service.refresh_token(body.refresh_token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_authenticated_user)):
    return UserResponse.model_validate(user)


@router.post("/logout", response_model=SuccessResponse)
async def logout(user: User = Depends(get_authenticated_user)):
    return SuccessResponse(message="Logged out successfully")
