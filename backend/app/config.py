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
    fred_api_key: str = Field(default="")   # free key: https://fred.stlouisfed.org/docs/api/api_key.html
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

    # Broker — paper trading first, flip to "live" after pre-live checklist
    # (see docs/trading.md SEC:RISK). Paper and live use *different* API keys
    # on Alpaca; rotating the mode without rotating the key returns 403.
    broker: str = Field(default="alpaca", description="alpaca (only supported provider for now)")
    broker_mode: str = Field(default="paper", description="paper | live")
    alpaca_api_key: str = Field(default="")
    alpaca_api_secret: str = Field(default="")
    alpaca_base_url: str = Field(default="", description="optional override; auto-resolved from broker_mode if blank")

    # Trade risk caps — enforced server-side at the API layer (see
    # services/trading/limits.py once Phase 2 lands). Frontend cannot bypass.
    trade_max_order_dollars: float = Field(default=2000.0)
    trade_max_position_dollars: float = Field(default=5000.0)
    trade_daily_loss_cap_dollars: float = Field(default=-200.0)
    trade_daily_order_count_cap: int = Field(default=50)
    # Auto-trade — off until Phase 3 sign-off, even then gated per signal type
    auto_trade_enabled: bool = Field(default=False)
    auto_trade_signal_types: str = Field(default="", description="comma-separated allowlist; empty = none")
    # Auto-trade subscriber poll interval (seconds). Short enough that scanner-
    # alert → broker submit stays sub-minute, long enough to avoid hammering DB.
    auto_trade_poll_seconds: int = Field(default=30)
    # Scanner halt — once today's signal count reaches this, dip + MCF scanners
    # stop firing for the day. Matches trade_daily_order_count_cap by default
    # so an auto-trade run that hits the cap also stops generating more signals.
    scanner_daily_signal_cap: int = Field(default=50)

    # Logging
    log_dir: str = Field(default="./local_debugging")

    # Cache TTLs — stock data (days)
    cache_ttl_earnings_fallback_days: int = Field(default=30)  # fallback when next_earnings_date unknown
    cache_ttl_fundamentals_days: int = Field(default=30)       # quarterly — P/E, margins, FCF
    cache_ttl_analyst_days: int = Field(default=1)             # price targets update weekly/sporadic
    cache_ttl_short_interest_days: int = Field(default=7)      # FINRA bi-weekly; 7d is safe
    cache_ttl_earnings_quality_days: int = Field(default=30)   # Piotroski/Beneish/Altman — quarterly
    # Cache TTLs — stock data (hours)
    cache_ttl_news_hours: float = Field(default=0.5)           # 30 min — stale news is misleading
    cache_ttl_congressional_hours: int = Field(default=24)     # sporadic STOCK Act filings
    # Cache TTLs — LLM results (hours)
    cache_ttl_llm_short_hours: float = Field(default=0.5)      # intraday: convergence, sentiment, risk/reward
    cache_ttl_llm_tier2_hours: float = Field(default=2.0)      # general tier2 fallback
    cache_ttl_llm_tier3_hours: int = Field(default=24)         # daily: price_forecast, bull/bear, cascade
    cache_ttl_llm_backtest_hours: int = Field(default=168)     # 7 days — historical data is stable
    cache_ttl_llm_personas_hours: int = Field(default=168)     # 7 days — investment thesis changes slowly

    class Config:
        env_file = (".env.shared", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
