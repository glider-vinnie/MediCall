from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.voice import router as voice_router
from app.core.config import Settings, get_settings
from app.db.database import Database, create_schema
from app.db.seed import seed_database
from app.domain.errors import DomainError
from app.voice.events import VoiceEventHub
from app.voice.pipeline import VoicePipelineFactory
from app.voice.session import VoiceSessionManager


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        create_schema(database)
        with database.session_factory() as session:
            seed_database(session)
        yield
        await application.state.voice_sessions.cleanup_all()

    app = FastAPI(title="MediCall AI API", version="0.1.0")
    app.router.lifespan_context = lifespan
    app.state.database = database
    app.state.settings = settings
    app.state.voice_events = VoiceEventHub()
    app.state.voice_sessions = VoiceSessionManager()
    app.state.voice_pipeline = VoicePipelineFactory(settings, database, app.state.voice_events)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.message, "code": error.code},
        )
    return app


app = create_app()
