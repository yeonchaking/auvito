"""Settings management with dotenv and YAML config loading."""

import os
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    youtube_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""

    # Paths
    workspace_root: str = "workspace"
    db_path: str = "workspace/youtube_pipeline.db"

    class Config:
        env_file = ".env"
        case_sensitive = False


def load_settings() -> tuple[Settings, dict]:
    """Load settings from .env and YAML config."""
    settings = Settings()

    # Load default config
    config_path = Path(__file__).parent / "config" / "default.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return settings, config


def get_config() -> dict:
    """Get config dict."""
    _, config = load_settings()
    return config
