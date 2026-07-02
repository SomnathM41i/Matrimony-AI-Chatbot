from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-secret-key"
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/chatbot.db"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VERIFY_SSL: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "matrimony"
    DB_CONNECT_TIMEOUT: int = 10

    ALLOWED_SQL_TABLES: str = "register,membershipplan,siteconfig,cms,successstory,testimonial,agents,agent_commissions,agent_customers,agent_plan_assignments,agent_sales,agent_withdrawal_requests"

    PHOTO_BASE_URL: str = "https://weddingsparampara.com/photo/"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_MESSAGE_LENGTH: int = 5000

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_tables_set(self) -> set:
        return {t.strip() for t in self.ALLOWED_SQL_TABLES.split(",") if t.strip()}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
