from passlib.context import CryptContext
from app.repositories.user_repository import UserRepository
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.logger import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    @staticmethod
    def _truncate(password: str) -> str:
        return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(self._truncate(password))

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(self._truncate(plain_password), hashed_password)

    async def register(self, name: str, email: str, password: str) -> dict:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")
        password_hash = self.hash_password(password)
        user = await self.user_repo.create(email=email, name=name, password_hash=password_hash)
        return {
            "access_token": create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token({"sub": str(user.id)}),
            "user": user,
        }

    async def login(self, email: str, password: str) -> dict:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.password_hash:
            raise ValueError("Invalid email or password")
        if not self.verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        await self.user_repo.update_last_login(user)
        return {
            "access_token": create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token({"sub": str(user.id)}),
            "user": user,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token payload")
        user = await self.user_repo.get_by_id(int(user_id))
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        return {
            "access_token": create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token({"sub": str(user.id)}),
        }
