from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Configuration loaded from environment variables and a local .env file."""

    # Resolve relative to services/api, rather than the process working directory.
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_mode: str = "demo"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    database_url: str = "sqlite:///../../data/medicall.db"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_stt_model: str = "scribe_v2_realtime"
    elevenlabs_tts_model: str = "eleven_flash_v2_5"
    voice_language: str = "en"
    voice_ice_servers: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def voice_missing_configuration(self) -> list[str]:
        return [name for name, present in self.voice_configuration_presence.items() if not present]

    @property
    def voice_configuration_presence(self) -> dict[str, bool]:
        """Safe readiness diagnostic: intentionally reports no configuration values."""
        return {
            "GEMINI_API_KEY": bool(self.gemini_api_key),
            "ELEVENLABS_API_KEY": bool(self.elevenlabs_api_key),
            "ELEVENLABS_VOICE_ID": bool(self.elevenlabs_voice_id),
        }

    @property
    def voice_is_configured(self) -> bool:
        return not self.voice_missing_configuration

    @property
    def effective_voice_mode(self) -> str:
        """Return the runtime mode based on the credentials the voice service uses."""
        return "live" if self.voice_is_configured else "demo"

    @property
    def ice_servers(self) -> list[str]:
        return [server.strip() for server in self.voice_ice_servers.split(",") if server.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
