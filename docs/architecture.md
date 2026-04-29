# docs/architecture.md — Tech stack, LLM factory, decisions, cache, DB, directory map
# Sections: grep -n "SEC:" docs/architecture.md
# SEC:STACK        Tech stack table
# SEC:DIR_MAP      Project directory (key files only)
# SEC:LLM_FACTORY  Provider-agnostic LLM setup
# SEC:DECISIONS    Key architectural decisions + rationale
# SEC:CACHE        Redis cache strategy per tier
# SEC:DB_MODELS    SQLAlchemy models

---

<!-- SEC:STACK -->
## Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.12 |
| Backend framework | FastAPI + uvicorn |
| Agent orchestration | LangGraph (ReAct pattern) |
| Background jobs | APScheduler (in-process, FastAPI lifespan) |
| Frontend | React 18 + TypeScript + Vite |
| Charts | Recharts |
| State management | Zustand |
| HTTP client | Axios (`timeout: 30000`, `X-API-Key` header) |
| Primary database | PostgreSQL (async via asyncpg + SQLAlchemy 2) |
| Cache | Redis |
| Usage tracking | JSON file (`data/usage.json`) |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Testing | pytest + pytest-asyncio + httpx |
| Migrations | Alembic |

---

<!-- SEC:DIR_MAP -->
## Project Directory (key files)

```
backend/app/
  agent/
    graph.py        # LangGraph StateGraph — wires ALL_TOOLS list
    state.py        # AgentState: ticker, mode, messages
    prompts.py      # System prompts: day_trade / long_term / both
  tools/
    _yf_client.py   # Thread-safe rate-limited yf.Ticker() — ALL tools use this
    price.py        technicals.py  news.py  sentiment.py
    core_tools.py   # analyst, earnings, fundamentals, options, insider, institutional, short_interest
    remaining_tools.py  # macro, sector, cascade, forecast, risk_reward, screener, convergence, trends
    new/            # V2 tools: investor_personas, bull_bear, congressional, backtester,
                    #           earnings_transcript, paper_trade
  api/
    research.py     # POST /research/  GET /research/stream (SSE V1)
    research_v2.py  # /v2/research/tier1|tier2|tier3 + estimate
    usage.py        # /usage/today + /usage/history
    watchlist.py  screener.py  alerts.py  macro.py
  services/
    alert_engine.py          # Evaluates watchlist signals
    scheduler.py             # APScheduler: watchlist 5 min, screener 15 min
    usage/
      limits.py   # ALL threshold values — edit here only
      tracker.py  # Reads/writes data/usage.json (async, thread-safe)
      guards.py   # check_token_limit(), check_api_call_limit()
  llm/factory.py  # get_llm(settings) → BaseChatModel; get_llm_with_fallback()
  config.py       # Pydantic settings — reads .env
  auth.py         # X-API-Key middleware; swap for JWT by replacing verify_api_key()
  main.py         # FastAPI app — mounts all routers, lifespan startup

frontend/src/
  pages/          ResearchPage  WatchlistPage  ScreenerPage  MacroPage  UsagePage
  components/
    research/     PriceChart  SignalScore  NewsPanel  StreamPanel
                  InvestorPersonasPanel  Tier3Panels
    shared/       ModeToggle  ExecModeBar  ExpandablePanel  SignalTag  AlertToast
  hooks/          useSSE  useWebSocket  useWatchlist  useScreener
  services/       api.ts (Axios)  researchV2.ts (tiered calls)
  store.ts        # Zustand
  types/index.ts  # All TypeScript interfaces
```

---

<!-- SEC:LLM_FACTORY -->
## LLM Factory

File: `backend/app/llm/factory.py`
Entry point: `get_llm(settings)` → returns `BaseChatModel`
Fallback chain: `get_llm_with_fallback()` → configured provider → Groq → Cerebras → Ollama

| `MODEL_TYPE` env value | Provider | Notes |
|---|---|---|
| `groq` | Groq | Default — `llama-3.3-70b-versatile` |
| `ollama` | Local Ollama | Best for dev, no API key |
| `gemini` | Google Gemini | Free tier |
| `claude` | Anthropic Claude | Highest quality, paid |
| `openai` | OpenAI | Paid |
| `openrouter` | OpenRouter | Free models available |
| `cerebras` | Cerebras | Free tier, OpenAI-compatible |

Per-task overrides (optional, empty = falls back to MODEL_TYPE):
- `LLM_AGENT_TYPE` / `LLM_AGENT_MODEL` — LangGraph ReAct loop
- `LLM_TIER2_TYPE` / `LLM_TIER2_MODEL` — click-to-expand panels
- `LLM_TIER3_TYPE` / `LLM_TIER3_MODEL` — deep on-demand tools

Rate limiting: `LLM_TIER=free` activates conservative RPM caps per provider via `InMemoryRateLimiter`. `LLM_TIER=paid` disables all caps.

---

<!-- SEC:DECISIONS -->
## Key Architectural Decisions

| Decision | Rationale |
|---|---|
| One tool per file | Independently testable, readable, replaceable |
| Tools return `{"error":"..."}`, never raise | Agent loop survives tool failures gracefully |
| `_yf_client.py` shared wrapper | Serializes all Yahoo Finance requests through one global thread-safe rate limiter; prevents 429s |
| Three execution tiers | Prevents accidental token exhaustion |
| Saver mode rule-based | Zero LLM cost for quick checks |
| JSON file for usage tracking | Simple, portable, readable without DB |
| Redis cache per tier | Prevents re-fetching same data within TTL |
| SSE for stream, WS for alerts | SSE = unidirectional agent reasoning; WS = bidirectional live alerts |
| Usage headers on every response | Frontend shows live usage without polling |
| Soft delete on watchlist | Preserves history, allows re-activation |
| `asyncio.to_thread` for all tool calls | Tools are sync (blocking I/O); to_thread keeps FastAPI async loop free |
| `asyncio.wait_for` on tier2/tier3 | Prevents yfinance / LLM hangs from blocking indefinitely (25 s tier2, 90 s tier3) |

---

<!-- SEC:CACHE -->
## Redis Cache Strategy

| Data | TTL |
|---|---|
| Tier 1 (price, technicals, data) | 15 min |
| Tier 2 LLM results | 30 min |
| Tier 3 deep results | 4 hr |
| Backtester results | 24 hr |
| Congressional trades | 2 hr |

Cache hits cost 0 tokens. Cache hits are tracked in `usage.json`.

---

<!-- SEC:DB_MODELS -->
## Database Models

File: `backend/app/db/models.py`

```python
WatchlistItem     # ticker, company_name, last_signal, last_score, last_price,
                  # last_evaluated, added_at, notes, is_active (soft delete)

ScreenerPreset    # name, filters (JSON), auto_monitor, last_run, created_at

AlertHistory      # ticker, alert_type, title, body, score,
                  # triggered_at, source ("watchlist"|"screener"), dismissed

ResearchCache     # ticker, mode, result (JSON), cached_at, expires_at
```

Migration: `make migration MSG="description"` then `make migrate`
