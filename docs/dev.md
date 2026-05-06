# docs/dev.md — Commands, env vars, testing conventions, adding features
# Sections: grep -n "SEC:" docs/dev.md
# SEC:COMMANDS      make / docker commands
# SEC:ENV_VARS      All environment variables with defaults
# SEC:TESTING       Testing conventions and patterns
# SEC:ADD_FEATURE   Checklist for adding a new feature

---

<!-- SEC:COMMANDS -->
## Common Commands

```bash
# Docker (recommended)
make up           # Start everything (backend + frontend + postgres + redis)
make down         # Stop all containers
make logs         # Follow all container logs

# Local dev
make backend      # FastAPI on :8000 (hot reload)
make frontend     # Vite on :5173 (hot reload)

# Quality
make test         # All 45 tests (pytest)
make test-tools   # Tool unit tests only
make test-api     # API integration tests only
make lint         # ruff check
make fmt          # black format
make typecheck    # tsc --noEmit

# Database
make migrate          # Apply pending Alembic migrations
make migration MSG="add_table"  # Generate new migration

# Utilities
make health       # curl /health
make clean        # Remove __pycache__, .pytest_cache, dist
```

Run tests manually: `PYTHONPATH=. python -m pytest tests/ -v`

---

<!-- SEC:ENV_VARS -->
## Environment Variables

Copy `.env.example` → `.env`. All vars have defaults shown below.

```bash
# LLM Provider (change MODEL_TYPE to swap provider — zero code changes)
MODEL_TYPE=groq                          # groq|ollama|gemini|claude|openai|openrouter|cerebras
MODEL_NAME=llama-3.3-70b-versatile
OLLAMA_MODEL=llama3.2

# Per-task LLM overrides (empty = uses MODEL_TYPE)
LLM_AGENT_TYPE=    LLM_AGENT_MODEL=      # LangGraph ReAct loop
LLM_TIER2_TYPE=    LLM_TIER2_MODEL=      # T2 analysis panels
LLM_TIER3_TYPE=    LLM_TIER3_MODEL=      # T3 deep tools

# LLM tier: "free" adds RPM caps per provider; "paid" disables all caps
LLM_TIER=free

# LLM API keys
GROQ_API_KEY=
CEREBRAS_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Data sources
NEWSAPI_KEY=                             # newsapi.org — free 100 req/day dev tier
FRED_API_KEY=                            # fred.stlouisfed.org — free; enables /macro/fred credit/rates dashboard
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=StockResearchPro/1.0

# App
API_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stockresearch
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development

# yfinance rate limiting (lower = safer vs Yahoo 429s in Docker)
YF_REQUESTS_PER_SECOND=2

# Background jobs
SCREENER_INTERVAL_MINUTES=15
WATCHLIST_ALERT_INTERVAL_MINUTES=5

# Cache TTL overrides (seconds; defaults shown)
CACHE_TTL_TIER1=900          # 15 min — price, technicals, tier1 data
CACHE_TTL_TIER2=1800         # 30 min — LLM analysis panels
CACHE_TTL_TIER3=14400        # 4 hr   — deep tools
CACHE_TTL_BACKTEST=86400     # 24 hr  — backtester results
CACHE_TTL_CONGRESSIONAL=7200 # 2 hr   — congressional trades

# Usage guard rails
USAGE_FILE=./data/usage.json
TOKEN_DAILY_LIMIT=50000
TOKEN_WEEKLY_LIMIT=200000
TOKEN_MONTHLY_LIMIT=500000
TOKEN_PER_SEARCH_LIMIT=20000
API_CALLS_DAILY_LIMIT=500
API_CALLS_PER_MINUTE_LIMIT=30
TICKERS_DAILY_LIMIT=50
TICKERS_PER_HOUR_LIMIT=10
```

---

<!-- SEC:TESTING -->
## Testing Conventions

All tests in `backend/tests/`.

| Test file | What it tests |
|---|---|
| `tests/tools/test_tools.py` | All 20+ tools; mock yfinance via `mock_yfinance` fixture |
| `tests/api/test_api.py` | API endpoints; SQLite in-memory via `client` fixture |
| `tests/tools/test_llm_factory.py` | LLM factory; mocks LangChain classes |

**Rules:**
- Never hit real APIs in tests — always mock yfinance, NewsAPI, LLM providers
- Every tool must have a test for the `{"error": "..."}` return path (no raise)
- `mock_yfinance` fixture is in `conftest.py`
- Use `pytest.mark.asyncio` for async endpoint tests

**Fixture pattern:**
```python
def test_get_price_success(mock_yfinance):
    result = get_price.invoke({"ticker": "AAPL"})
    assert "current_price" in result

def test_get_price_error(mock_yfinance_error):
    result = get_price.invoke({"ticker": "INVALID"})
    assert "error" in result
    # Must NOT raise
```

---

<!-- SEC:ADD_FEATURE -->
## Adding a New Feature — Checklist

### New tool
- [ ] Create `backend/app/tools/my_tool.py` with `@tool` decorator
- [ ] Never raise — always `return {"error": "..."}`
- [ ] Use `get_ticker()` from `_yf_client.py`, never `yf.Ticker()` directly
- [ ] Add to `backend/app/agent/graph.py` `ALL_TOOLS`
- [ ] If T2: add to `_TIER2_TOOLS` + `_TOKEN_ESTIMATES` in `research_v2.py`
- [ ] If T3: add to `_TIER3_TOOLS` + `_TOKEN_ESTIMATES` in `research_v2.py`
- [ ] Write test in `tests/tools/test_tools.py`
- [ ] Update `docs/tools.md` SEC:V1_TOOLS or SEC:V2_TOOLS
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New API endpoint
- [ ] Add route to appropriate file in `backend/app/api/`
- [ ] Register router in `main.py`
- [ ] Add to `docs/api.md` under the correct SEC:
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New frontend page
- [ ] Create `frontend/src/pages/MyPage.tsx`
- [ ] Add route in `App.tsx`
- [ ] Add nav link in nav component
- [ ] Update `docs/frontend.md` SEC:PAGES
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New guard rail limit
- [ ] Add to `backend/app/services/usage/limits.py` ONLY
- [ ] Add env var to `.env.example`
- [ ] Update `docs/features.md` SEC:GUARD_RAILS table
- [ ] Update `docs/dev.md` SEC:ENV_VARS

### Database change
- [ ] Update `backend/app/db/models.py`
- [ ] Run `make migration MSG="description"` then `make migrate`
- [ ] Update `docs/architecture.md` SEC:DB_MODELS
