from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    app_name: str = "medical-qa"

    database_url: str = "postgresql+asyncpg://medical:medical@localhost:5432/medical_qa"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_min: int = 60 * 24 * 7

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "medical_chunks"
    embedding_dim: int = 384
    rag_top_k: int = 5

    # LLM (Step: real LLM integration)
    llm_provider: str = "stub"  # stub | openai_compat | volcengine
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_sec: int = 60
    llm_max_tokens: int = 800
    llm_temperature: float = 0.2

    # Embeddings (Step: real embedding integration)
    embedding_provider: str = "stub"  # stub | openai_compat | volcengine
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_timeout_sec: int = 30
    embedding_batch_size: int = 32
    embedding_normalize: bool = True

    cors_allow_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
