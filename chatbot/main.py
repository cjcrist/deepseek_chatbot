"""FastAPI entrypoint for the chatbot service."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from chatbot.api.routes import router
from chatbot.config import get_settings
from chatbot.db import create_async_db_engine, create_async_session_factory
from chatbot.services.chat_service import ChatService
from chatbot.services.deepseek_client import DeepSeekClient


def _run_alembic_upgrade_sync() -> None:
    """Apply SQL migrations (sync — Alembic driver matches Settings.database_url)."""
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources for the application."""
    settings = get_settings()
    await asyncio.to_thread(_run_alembic_upgrade_sync)

    engine = create_async_db_engine(settings.database_url_async)
    session_factory = create_async_session_factory(engine)

    deepseek_client = DeepSeekClient(
        token=settings.deepinfra_token,
        base_url=settings.deepinfra_base_url,
        model=settings.deepseek_model,
        timeout_seconds=settings.request_timeout_seconds,
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.chat_service = ChatService(
        session_factory=session_factory,
        deepseek_client=deepseek_client,
        archive_retention_days=settings.chat_archive_retention_days,
    )

    try:
        yield
    finally:
        await deepseek_client.aclose()
        await engine.dispose()


app = FastAPI(
    title="DeepSeek Chatbot API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
