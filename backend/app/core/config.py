from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow overriding by real environment variables
        extra="ignore",
    )

    rag_service_url: str = "http://127.0.0.1:8060"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
