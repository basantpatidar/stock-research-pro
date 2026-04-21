from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # LLM provider
    model_type: str = Field(default="groq", description="LLM provider")
    model_name: str = Field(default="llama-3.3-70b-versatile")
    ollama_model: str = Field(default="llama3.2")

    # LLM API keys
    groq_api_key: str = Field(default="")
    cerebras_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")

    # Data sources
    newsapi_key: str = Field(default="")
    reddit_client_id: str = Field(default="")
    reddit_client_secret: str = Field(default="")
    reddit_user_agent: str = Field(default="StockResearchPro/1.0")

    # App
    api_key: str = Field(default="dev-secret-key-change-in-production")
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/stockresearch")
    redis_url: str = Field(default="redis://localhost:6379")
    environment: str = Field(default="development")

    # Background jobs
    screener_interval_minutes: int = Field(default=15)
    watchlist_alert_interval_minutes: int = Field(default=5)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
