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
    ASSISTANT_NAME: str = "MyVivahAI"
    PLATFORM_NAME: str = "Dishavadhuvar"
    # "soft": welcome + ask for the MatriID once, then allow guest browsing.
    # "hard": block all service until a MatriID is linked.
    MATRI_ID_GATE_MODE: str = "soft"
    # When the chat onboarding may start searching early (CF-3):
    #   gender_plus_core (default) | gender_only | full_only
    ONBOARDING_SEARCH_STRATEGY: str = "gender_plus_core"
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

    CEREBRAS_API_KEY: str = ""
    CEREBRAS_API_URL: str = "https://api.cerebras.ai/v1/chat/completions"
    CEREBRAS_MODEL: str = "llama-3.3-70b"

    GEMINI_API_KEY: str = ""
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    ZEN_API_KEY: str = ""
    ZEN_API_URL: str = "https://opencode.ai/zen/v1/chat/completions"
    ZEN_MODEL: str = "deepseek-v4-flash-free"

    LLM_PROVIDER: str = "groq"   # "ollama" | "zen" | "groq" | "cerebras" | "gemini"

    DEFAULT_TEMPERATURE: float = 0.5
    DEFAULT_MAX_TOKENS: int = 1200

    INTENT_MODEL: str = "llama-3.1-8b-instant"
    INTENT_TEMPERATURE: float = 0.0
    INTENT_MAX_TOKENS: int = 10
    INTENT_MESSAGE_TRUNCATION: int = 500

    SQL_TEMPERATURE: float = 0.0
    SQL_MAX_TOKENS: int = 900

    FORMAT_TEMPERATURE: float = 0.0
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
    CHAT_HISTORY_LIMIT: int = 30
    CONTEXT_TIMEOUT_SECONDS: int = 3600
    ROUTER_THRESHOLD: float = 0.1
    ROUTER_CONFIDENCE_THRESHOLD: float = 0.05
    APP_TIMEZONE: str = "Asia/Kolkata"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 100
    # Vector search is an optional fallback used only when SQL returns no
    # suitable rows. Disable to save RAM (the embedding model is ~2GB).
    VECTOR_FALLBACK_ENABLED: bool = True

    DB_HOST: str = ""
    DB_PORT: int = 3306
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = ""
    DB_CONNECT_TIMEOUT: int = 10
    DB_SSL_CA: str = ""
    DB_POOL_SIZE: int = 5

    ALLOWED_SQL_TABLES: str = "register,siteconfig,cms,successstory,testimonial,banners,news,seo,packages,activity"

    PHOTO_BASE_URL: str = "https://dishavadhuvar.in/gallary/"

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




