from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://soundsnap:soundsnap@localhost:5432/soundsnap"
    typesense_api_key: str = "xyz"
    typesense_host: str = "localhost"
    typesense_port: int = 8108
    typesense_protocol: str = "http"

    storage_backend: str = "local"
    local_storage_path: str = "./audio"
    gcs_bucket: str | None = None
    gcs_project_id: str | None = None
    gcs_credentials_path: str | None = None

    generator: str = "mock"
    generator_fallback_to_mock: bool = True
    generation_daily_limit: int = 10
    elevenlabs_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
