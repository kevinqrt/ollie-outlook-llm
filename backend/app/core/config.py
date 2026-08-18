from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rag_service_url: str = "http://127.0.0.1:8060"
    llm_model: str = "llama3.1:70b"
    cors_origins: list[str] = ["*"]

    vector_store_path: str = "./chroma_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 100

    model_api_base_url: str | None = None
    model_api_key: str | None = None
    llm_max_tokens: int = 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
