from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.runtime import get_app_root

BASE_DIR = get_app_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rag_service_url: str = "http://127.0.0.1:8060"
    llm_model: str = "llama3.1:70b"
    model_api_base_url: str | None = None
    model_api_key: str | None = None
    llm_max_tokens: int = 1024
    cors_origins: list[str] = ["*"]
    server_host: str = "localhost"
    server_port: int = 8000
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
