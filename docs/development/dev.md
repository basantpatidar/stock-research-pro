# docs/dev.md — Commands, env vars, testing conventions, adding features
# Sections: grep -n "SEC:" docs/dev.md

**Doc version:** 1.2 · **Last updated:** 2026-05-16

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

# EOD signal dump — runs INSIDE the backend container (Docker-only laptop has
# no host Python). Output lands in local_debugging/eod_signals/ on the host.
# Normally automated by the eod_dump scheduler job (Mon-Fri 4:35 PM ET);
# run manually only to re-generate or backfill a specific day.
docker compose exec backend python local_debugging/eod_dump.py                  # today
docker compose exec backend python local_debugging/eod_dump.py --date 2026-05-13 # specific day
```

Run tests manually: `PYTHONPATH=. python -m pytest tests/ -v`

---

<!-- SEC:ENV_VARS -->
## Environment Variables

Config is split across two files so tuning knobs propagate via `git pull` without exposing secrets:

| File | Tracked? | Contains |
|---|---|---|
| `.env.shared` | **Yes — committed** | Shared tuning: `MODEL_TYPE`, all `CACHE_TTL_*`, `TRADE_*`, `AUTO_TRADE_*`, `SCANNER_*`, `BROKER`, `BROKER_MODE`, `ENVIRONMENT`, usage limits, etc. Edit here, commit, `git pull` on the other machine. |
| `.env` | No — gitignored | Secrets + machine-specific: all `*_API_KEY`, `ALPACA_API_KEY/SECRET`, `API_KEY`, `DATABASE_URL`, `REDIS_URL` (local non-Docker). Set once per machine. |
| `docker-compose.yml` `environment:` | Yes | Container-specific overrides: `DATABASE_URL`/`REDIS_URL` with service names, `LOG_DIR=/app/local_debugging`, `TZ`, `SCANNER_HEARTBEAT_LOG`, `NEAR_MISS_LOG`. |

**New machine setup:** copy `.env.example` → `.env` and fill in your credentials. `.env.shared` arrives via `git pull`.

**Edit discipline:** edit `.env.shared` on one machine, commit immediately, then pull on the other. Editing without committing before a pull risks a merge conflict.

### .env.shared (committed — shared tuning knobs)

```bash
# LLM provider (change MODEL_TYPE to swap — zero code changes)
MODEL_TYPE=groq                  # groq|ollama|gemini|claude|openai|openrouter|cerebras
MODEL_NAME=llama-3.3-70b-versatile
OLLAMA_MODEL=llama3.2
LLM_TIER=free                    # "free" adds RPM caps; "paid" removes them

# Per-task LLM overrides (empty = uses MODEL_TYPE)
LLM_AGENT_TYPE=    LLM_AGENT_MODEL=      # LangGraph ReAct loop
LLM_TIER2_TYPE=    LLM_TIER2_MODEL=      # T2 analysis panels
LLM_TIER3_TYPE=    LLM_TIER3_MODEL=      # T3 deep tools

YF_REQUESTS_PER_SECOND=2.0       # lower = safer vs Yahoo 429s in Docker
REDDIT_USER_AGENT=StockResearchPro/1.0
ENVIRONMENT=development
USAGE_FILE=./data/usage.json
SCREENER_INTERVAL_MINUTES=15
WATCHLIST_ALERT_INTERVAL_MINUTES=5

BROKER=alpaca
BROKER_MODE=paper

TRADE_MAX_ORDER_DOLLARS=2000
TRADE_MAX_POSITION_DOLLARS=5000
TRADE_DAILY_LOSS_CAP_DOLLARS=-200
TRADE_DAILY_ORDER_COUNT_CAP=50   # 51st rejected with 422

AUTO_TRADE_ENABLED=false
AUTO_TRADE_SIGNAL_TYPES=         # comma-separated allowlist; empty = nothing fires
AUTO_TRADE_POLL_SECONDS=30

SCANNER_DAILY_SIGNAL_CAP=50      # dip + MCF scanners halt after this many alerts/day
SCANNER_SCORE_THRESHOLD=72       # >= this to fire; set 70 to admit near-miss band (65-71)

TOKEN_DAILY_LIMIT=50000
TOKEN_WEEKLY_LIMIT=200000
TOKEN_MONTHLY_LIMIT=500000
API_CALLS_DAILY_LIMIT=500

CACHE_TTL_EARNINGS_FALLBACK_DAYS=30
CACHE_TTL_FUNDAMENTALS_DAYS=30
CACHE_TTL_ANALYST_DAYS=1
CACHE_TTL_SHORT_INTEREST_DAYS=7
CACHE_TTL_EARNINGS_QUALITY_DAYS=30
CACHE_TTL_NEWS_HOURS=0.5
CACHE_TTL_CONGRESSIONAL_HOURS=24
CACHE_TTL_LLM_SHORT_HOURS=0.5
CACHE_TTL_LLM_TIER2_HOURS=2.0
CACHE_TTL_LLM_TIER3_HOURS=24
CACHE_TTL_LLM_BACKTEST_HOURS=168
CACHE_TTL_LLM_PERSONAS_HOURS=168
```

### .env (gitignored — secrets + machine-specific)

```bash
# LLM keys (only the one matching MODEL_TYPE in .env.shared is required)
GROQ_API_KEY=
CEREBRAS_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

NEWSAPI_KEY=
FRED_API_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

API_KEY=dev-secret-key-change-in-production
# Local non-Docker runs only (Docker Compose overrides with service names)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stockresearch
REDIS_URL=redis://localhost:6379

ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_BASE_URL=                 # blank — alpaca-py auto-resolves from BROKER_MODE
```

**Inline comment trap (Docker Compose):** the `env_file` parser does NOT strip inline `# ...` comments — `KEY=val   # note` is loaded as the literal value `val   # note`. Always put comments on their own line **above** the variable. This bit us on 2026-05-14 when `ALPACA_BASE_URL=   # optional override` silently loaded the comment as the URL.

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
- [ ] Update `docs/reference/tools.md` SEC:V1_TOOLS or SEC:V2_TOOLS
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New API endpoint
- [ ] Add route to appropriate file in `backend/app/api/`
- [ ] Register router in `main.py`
- [ ] Add to `docs/reference/api.md` under the correct SEC:
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New frontend page
- [ ] Create `frontend/src/pages/MyPage.tsx`
- [ ] Add route in `App.tsx`
- [ ] Add nav link in nav component
- [ ] Update `docs/reference/frontend.md` SEC:PAGES
- [ ] Add entry to `CLAUDE.md` Recent Changes

### New guard rail limit
- [ ] Add to `backend/app/services/usage/limits.py` ONLY
- [ ] Add env var to `.env.example`
- [ ] Update `docs/reference/features.md` SEC:GUARD_RAILS table
- [ ] Update `docs/development/dev.md` SEC:ENV_VARS

### Database change
- [ ] Update `backend/app/db/models.py`
- [ ] Run `make migration MSG="description"` then `make migrate`
- [ ] Update `docs/reference/architecture.md` SEC:DB_MODELS
