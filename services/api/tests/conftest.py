from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'medicall-test.db'}",
        gemini_api_key="test-gemini-key",
        elevenlabs_api_key="test-elevenlabs-key",
        elevenlabs_voice_id="test-voice-id",
    )
    return create_app(settings)


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(app, client) -> Generator[Session, None, None]:
    database_session = app.state.database.session_factory()
    try:
        yield database_session
    finally:
        database_session.close()
