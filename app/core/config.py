"""Application configuration."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "SmartCart AI Backend"
    app_version: str = "1.0.0"
    debug: bool = False

    # Security
    api_key_header: str = "X-API-Key"
    api_keys: List[str] = []
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # LLM
    openai_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "openai"  # "openai" or "groq"
    openai_model: str = "gpt-4o-mini"
    groq_model: str = "llama3-8b-8192"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300  # 5 minutes

    # Queue
    queue_name: str = "smartcart_jobs"

    # Data
    mock_data_enabled: bool = True  # Use mock data when DB/scrapers unavailable

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
