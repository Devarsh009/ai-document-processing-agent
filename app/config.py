from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    Loads from .env if present, with sensible defaults for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Groq LLM service",
    )
    LLM_MODEL: str = Field(
        default="groq/llama-3.1-8b-instant",
        description="LLM model identifier used by CrewAI agents",
    )
    UPLOAD_DIR: str = Field(
        default="uploads",
        description="Directory to store uploaded files for worker processing",
    )
    DATABASE_PATH: str = Field(
        default="jobs.db",
        description="Path to SQLite persistent database for job lifecycle tracking",
    )
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.70,
        description="Confidence threshold below which documents route to manual review",
    )
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum allowed upload size in bytes",
    )
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".txt", ".pdf", ".docx"],
        description="Supported file extensions for document ingestion",
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout in seconds for external provider calls",
    )

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://'")
        return v

    @field_validator("CONFIDENCE_THRESHOLD")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v


settings = Settings()
