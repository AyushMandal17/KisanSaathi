"""Application factory supports isolated databases and injected tools in tests."""
from contextlib import asynccontextmanager
import logging
import yaml

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import create_database
from app.routers import farmers
from app.routers import advice


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
    application.state.limiter = advice.FarmerRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                               allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
    application.include_router(farmers.router)
    application.include_router(advice.router)

    @application.exception_handler(Exception)
    async def controlled_error(request, error):
        logging.getLogger(__name__).error("Request failed (%s)", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "Unable to complete this request. Please try again."})

    @application.get("/meta")
    def metadata():
        config = yaml.safe_load((settings.project_dir / "config/ui.yaml").read_text(encoding="utf-8"))
        return {**config, "data_mode": settings.data_mode, "demo_scenario": settings.demo_scenario,
                "mock_llm": settings.use_mock_llm}

    @application.get("/health")
    def health():
        return {"status": "ok", "data_mode": settings.data_mode, "mock_llm": settings.use_mock_llm}

    return application


app = create_app()
