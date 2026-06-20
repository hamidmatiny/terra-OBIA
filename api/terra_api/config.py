"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Terra OBIA API service."""

    model_config = SettingsConfigDict(env_prefix="TERRA_", env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = None
    models_dir: Path = Path("models")
    job_output_dir: Path = Path("outputs/jobs")


settings = Settings()
