"""Application factory supports isolated databases and injected tools in tests."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.db import create_database
from app.routers import farmers


def create_app(settings: Settings | None = None, tools=None, llm=None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    engine, session_factory = create_database(settings)

    @asynccontextmanager
    async def lifespan(application):
        yield
        engine.dispose()

    application = FastAPI(title="KisanSaathi", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.session_factory = session_factory
    application.state.tools = tools
    application.state.llm = llm
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                               allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
    application.include_router(farmers.router)

    @application.get("/health")
    def health():
        return {"status": "ok", "data_mode": settings.data_mode, "mock_llm": settings.use_mock_llm}

    return application


app = create_app()
