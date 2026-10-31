"""Configuration is local to the project; secrets are never logged."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import QuestionLanguage

PROJECT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    project_dir: Path = PROJECT_DIR
    data_dir: Path = PROJECT_DIR / "data"
    crops_path: Path = PROJECT_DIR / "config/crops.yaml"
    rules_path: Path = PROJECT_DIR / "app/risk/rules.yaml"
    mandi_config_path: Path = PROJECT_DIR / "config/mandi.yaml"
    database_url: str = "sqlite:///./runtime/kisansaathi.db"
    cache_path: Path = PROJECT_DIR / "runtime/tool_cache.sqlite3"
    data_mode: Literal["demo", "live"] = "demo"
    demo_scenario: Literal["rain", "dry", "heatwave", "api_failure", "stale_mandi", "no_mandi"] = "rain"
    default_language: QuestionLanguage = "hi"
    use_mock_llm: bool = True
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = Field(default=10, gt=0, le=60)
    tool_retries: int = Field(default=1, ge=0, le=1)
    weather_ttl_seconds: int = Field(default=3600, ge=0)
    weather_max_age_hours: float = Field(default=6, gt=0)
    mandi_ttl_seconds: int = Field(default=21600, ge=0)
    mandi_max_age_hours: float = Field(default=48, gt=0)
    data_gov_base_url: str = "https://api.data.gov.in/resource"
    data_gov_resource_id: str = ""
    data_gov_api_key: str = Field(default="", repr=False)
    groq_api_key: str = Field(default="", repr=False)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-3.8-flash"
    llm_timeout_seconds: float = Field(default=15, gt=0, le=60)
    api_base_url: str = "http://127.0.0.1:8000"
    cors_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    rate_limit_requests: int = Field(default=30, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    log_level: str = "INFO"

    @field_validator("cache_path", mode="after")
    @classmethod
    def absolute_cache(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_DIR / value


@lru_cache
def get_settings() -> Settings:
    return Settings()
