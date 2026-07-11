"""
RiskLens AI — Application Configuration
Centralized settings loaded from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file or environment variables."""

    # --- Application ---
    app_name: str = Field(default="RiskLens AI")
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=True)
    app_version: str = Field(default="1.0.0")
    api_key: str = Field(default="risklens-dev-key-2026")

    # --- FastAPI ---
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # --- MongoDB Atlas ---
    mongodb_uri: str = Field(default="")  # Must be set via MONGODB_URI env var
    mongodb_db_name: str = Field(default="portfolio_risk")

    # --- Kafka ---
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_group_id: str = Field(default="risklens-consumers")

    # --- Anthropic Claude API ---
    anthropic_api_key: str = Field(default="")
    claude_model: str = Field(default="claude-sonnet-4-20250514")
    claude_max_tokens: int = Field(default=1024)
    claude_temperature: float = Field(default=0.3)

    # --- LangSmith ---
    langchain_tracing_v2: bool = Field(default=True)
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="risklens-ai")

    # --- Yahoo Finance ---
    yahoo_finance_poll_interval_seconds: int = Field(default=60)

    # --- Email (SMTP) ---
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="risklens-alerts@risklens.ai")

    # --- Jira ---
    jira_base_url: str = Field(default="")
    jira_email: str = Field(default="")
    jira_api_token: str = Field(default="")
    jira_project_key: str = Field(default="RISK")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — loads .env once."""
    return Settings()
