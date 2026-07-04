from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-secret-key"

    @field_validator("SECRET_KEY")
    @classmethod
    def check_secret_key(cls, v: str) -> str:
        if not v or v == "change-me-secret-key":
            raise ValueError(
                "SECRET_KEY must be changed from the default. "
                "Generate a strong key and set it in .env"
            )
        return v
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/chatbot.db"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GROQ_API_KEY: str = ""
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VERIFY_SSL: bool = True

    DEFAULT_TEMPERATURE: float = 0.5
    DEFAULT_MAX_TOKENS: int = 1200

    INTENT_MODEL: str = "llama-3.1-8b-instant"
    INTENT_TEMPERATURE: float = 0.0
    INTENT_MAX_TOKENS: int = 10
    INTENT_MESSAGE_TRUNCATION: int = 500

    SQL_TEMPERATURE: float = 0.0
    SQL_MAX_TOKENS: int = 900

    FORMAT_TEMPERATURE: float = 0.2
    FORMAT_MAX_TOKENS: int = 1400

    MAX_PAYLOAD_CHARS: int = 20000
    MAX_FIELD_CHARS: int = 200
    MAX_ROWS_IN_PAYLOAD: int = 15

    MAX_ROWS_BEFORE_NARROW: int = 10

    SQL_LIMIT: int = 20

    LLM_MAX_RETRIES: int = 4
    LLM_BASE_DELAY: float = 1.0
    RETRYABLE_STATUSES: str = "429,500,502,503,504"
    LLM_TIMEOUT: int = 30
    LLM_PROMPT_TRUNCATION: int = 3000
    LLM_MESSAGE_TRUNCATION: int = 5000

    CHAT_TITLE_TRUNCATION: int = 60

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "matrimony"
    DB_CONNECT_TIMEOUT: int = 10
    DB_SSL_CA: str = ""
    DB_POOL_SIZE: int = 5

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

    @property
    def retryable_statuses_set(self) -> set[int]:
        return {int(s.strip()) for s in self.RETRYABLE_STATUSES.split(",") if s.strip()}

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "case_sensitive": True,
    }


settings = Settings()
