from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        return v.encode("utf-8")[:72].decode("utf-8", errors="ignore")


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        return v.encode("utf-8")[:72].decode("utf-8", errors="ignore")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    profile_image: Optional[str] = None
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    refresh_token: str
