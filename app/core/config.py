from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    openai_api_key: SecretStr | None = None
    openai_api_key_file: Path | None = None
    openai_model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "gpt-5.6-luna"
    openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "medium"
    evaluation_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    evaluation_max_retries: int = Field(default=2, ge=0, le=5)
    evaluation_max_input_chars: int = Field(default=20_000, ge=1_000, le=100_000)
    evaluation_max_output_tokens: int = Field(default=3_000, ge=100, le=10_000)
    evaluation_rate_limit_per_minute: int = Field(default=10, ge=1, le=120)
    ocr_max_bytes: int = Field(default=8_000_000, ge=100_000, le=20_000_000)
    ocr_max_pixels: int = Field(default=20_000_000, ge=1_000_000, le=50_000_000)
    ocr_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    ocr_max_concurrency: int = Field(default=1, ge=1, le=4)
    build_analysis_max_output_tokens: int = Field(default=4000, ge=500, le=10000)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def read_openai_api_key(settings: Settings) -> str | None:
    """Read a key without ever including its value in validation errors or logs."""
    if settings.openai_api_key:
        return settings.openai_api_key.get_secret_value()
    if settings.openai_api_key_file:
        try:
            value = settings.openai_api_key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return value or None
    return None
