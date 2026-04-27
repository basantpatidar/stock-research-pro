from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Default LLM provider (used when no task-specific override is set)
    model_type: str = Field(default="groq", description="LLM provider")
    model_name: str = Field(default="llama-3.3-70b-versatile")
    ollama_model: str = Field(default="llama3.2")
    # "free" applies conservative rate limits; "paid" removes them
    llm_tier: str = Field(default="free", description="free or paid")
    # yfinance requests per second — lower = safer against Yahoo 429s
    yf_requests_per_second: float = Field(default=2.0)

    # Per-task LLM overrides — empty string falls back to model_type / model_name
    # agent: LangGraph ReAct loop (speed matters — use a fast/cheap model)
    llm_agent_type: str = Field(default="")
    llm_agent_model: str = Field(default="")
    # tier2: click-to-expand analysis panels (moderate quality needed)
    llm_tier2_type: str = Field(default="")
    llm_tier2_model: str = Field(default="")
    # tier3: deep on-demand features — investor personas, bull/bear, earnings transcript
    llm_tier3_type: str = Field(default="")
    llm_tier3_model: str = Field(default="")

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
