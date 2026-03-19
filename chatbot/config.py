"""Application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the chatbot service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    deepinfra_token: str = Field(alias="DEEPINFRA_TOKEN")
    deepinfra_base_url: str = Field(
        default="https://api.deepinfra.com/v1",
        alias="DEEPINFRA_BASE_URL",
    )
    deepseek_model: str = Field(
        default="deepseek-ai/DeepSeek-V3.2",
        alias="DEEPSEEK_MODEL",
    )
    request_timeout_seconds: float = Field(default=600.0, alias="REQUEST_TIMEOUT_SECONDS")

    chat_archive_retention_days: int = Field(
        default=30,
        alias="CHAT_ARCHIVE_RETENTION_DAYS",
        description="Archived chats older than this many days are deleted from the database.",
    )

    postgres_user: str = Field(default="pguser", alias="POSTGRES_USER")
    postgres_password: str = Field(default="pgpass", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="pgdb", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy URL (Alembic, tooling)."""
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_async(self) -> str:
        """Async SQLAlchemy URL for the FastAPI app."""
        return (
            "postgresql+psycopg_async://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
