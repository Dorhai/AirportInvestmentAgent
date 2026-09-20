from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    UNIVERSE_TTL_SECONDS: int = 3600
    UNIVERSE_WARM_ON_STARTUP: bool = True
    BTS_APP_ID: str | None = None
    BTS_T100_SEGMENT_PATH: str | None = None
    BTS_ONTIME_CSV_PATH: str | None = None
    BTS_ONTIME_DATA_DIR: str | None = None
    WEATHER_ENABLED: bool = True
    HTTP_TIMEOUT_S: float = 4.0
    BULK_HTTP_TIMEOUT_S: float = 30.0
    HTTP_USER_AGENT: str = "AirportIQ/1.0 (+contact)"
    BTS_TRAILING_MONTHS: int = 12
    TTS_ENABLED: bool = True
    TTS_MODEL: str = "tts-1-hd"
    TTS_VOICE: str = "nova"
    TTS_MAX_CHARS: int = 4096

    model_config = SettingsConfigDict(env_file=str(_REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()
