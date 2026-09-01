from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jobs Aggregator"
    environment: str = "development"
    database_url: str = "sqlite:///./jobs.db"
    admin_api_key: str | None = None
    log_level: str = "INFO"

    theirstack_api_key: str | None = None
    theirstack_base_url: str = "https://api.theirstack.com"

    us_only: bool = True
    posted_within_hours: int = 24
    sync_interval_minutes: int = 120
    sync_scheduler_enabled: bool = True
    sync_on_startup: bool = False
    max_pages_per_source: int = 5
    page_size: int = 100
    http_timeout_seconds: float = 30.0
    source_config_path: Path = Path("config/sources.yaml")

    target_titles: str = (
        "Software Engineer,AI Engineer,Machine Learning Engineer,LLM Engineer,"
        "Data Engineer,Data Scientist,Python Developer,Backend Engineer,Full Stack Engineer"
    )
    target_skills: str = (
        "Python,FastAPI,Django,Flask,JavaScript,TypeScript,React,SQL,AWS,Docker,"
        "Kubernetes,Machine Learning,LLM,RAG,AI Agents"
    )
    preferred_locations: str = "New York,NYC,New Jersey,NJ,Remote"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Some cloud providers still expose the legacy SQLAlchemy scheme.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://") and "+" not in value.split(":", 1)[0]:
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def target_title_list(self) -> list[str]:
        return self._csv(self.target_titles)

    @property
    def target_skill_list(self) -> list[str]:
        return self._csv(self.target_skills)

    @property
    def preferred_location_list(self) -> list[str]:
        return self._csv(self.preferred_locations)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
