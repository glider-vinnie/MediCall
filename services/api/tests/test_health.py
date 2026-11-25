from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_check_reports_demo_mode() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        app_mode="live",  # Legacy field must not override effective provider readiness.
        gemini_api_key=None,
        elevenlabs_api_key=None,
        elevenlabs_voice_id=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "medicall-api",
        "mode": "demo",
    }


def test_health_and_voice_config_report_the_same_live_mode(client: TestClient) -> None:
    health = client.get("/api/health")
    voice = client.get("/api/voice/config")

    assert health.status_code == 200
    assert voice.status_code == 200
    assert health.json()["mode"] == "live"
    assert voice.json()["mode"] == "live"
