from app.core.config import ENV_FILE, Settings


def test_env_file_is_anchored_to_backend_directory() -> None:
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent.name == "api"


def test_voice_configuration_presence_never_contains_values() -> None:
    settings = Settings(
        gemini_api_key="configured",
        elevenlabs_api_key="configured",
        elevenlabs_voice_id="configured",
    )

    assert settings.voice_configuration_presence == {
        "GEMINI_API_KEY": True,
        "ELEVENLABS_API_KEY": True,
        "ELEVENLABS_VOICE_ID": True,
    }
    assert settings.voice_missing_configuration == []
