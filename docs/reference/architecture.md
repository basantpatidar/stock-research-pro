# docs/architecture.md — Tech stack, LLM factory, decisions, cache, DB, directory map
# Sections: grep -n "SEC:" docs/architecture.md
# SEC:STACK        Tech stack table
# SEC:DIR_MAP      Project directory (key files only)
# SEC:LLM_FACTORY  Provider-agnostic LLM setup
# SEC:DECISIONS    Key architectural decisions + rationale
# SEC:TOKEN_FLOW   Full request lifecycle — where tokens are saved at each stage
# SEC:CACHE        Per-tool cache TTL strategy (Redis vs DB, data-driven TTLs)
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
    signal.py       # Shared SignalResult, Verdict, composite_verdict() used by quality/options tools
    price.py        technicals.py  news.py  sentiment.py
    core_tools.py   # analyst, earnings, fundamentals, options, insider, institutional, short_interest
    remaining_tools.py  # macro, sector, cascade, forecast, risk_reward, screener, convergence, trends
    earnings_quality.py    # Tier 2: Piotroski, Beneish, Altman, Accruals — 0 LLM tokens
    options_intelligence.py # Tier 2: GEX, max pain, IV analysis, skew, term structure — 0 LLM tokens
    fred_macro.py          # FRED API: credit spreads, yield curves, real yields, M2, cross-asset
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
    research/     PriceChart (+ volume profile overlay)  SignalScore  NewsPanel  StreamPanel
                  EarningsHistoryPanel  EarningsQualityPanel  OptionsIntelligencePanel
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

<!-- SEC:TOKEN_FLOW -->
## Full Request Lifecycle — Where Tokens Are Saved

Every user search triggers this flow. Token savings happen at three independent gates.

```
User searches ticker
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  GATE 1 — Execution Mode check (frontend, 0 cost)   │
│  saver → all LLM calls skipped entirely (0 tokens)  │
│  normal → T2/T3 only run if user clicks panel        │
│  deep  → T2 auto-runs; T3 still click-to-run        │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  GATE 2 — StockDataCache (DB) check per tool        │
│  Tier 1 data tools checked against StockDataCache.  │
│  If fresh hit → return stored JSON, skip API call.  │
│  TTL varies per tool (see SEC:CACHE).               │
│  Earnings data: fresh for whole quarter (30 days).  │
│  Saves: yfinance API calls + processing time.       │
└─────────────────────────────────────────────────────┘
        │ miss → fetch from yfinance/FRED/NewsAPI
        ▼
┌─────────────────────────────────────────────────────┐
│  GATE 3 — ResearchCache (DB) check per tool+ticker  │
│  LLM tools (T2/T3) checked before invoking LLM.    │
│  If fresh hit → return stored result, 0 LLM tokens. │
│  TTL varies per tool (see SEC:CACHE).               │
│  Earnings transcript: fresh until next earnings.    │
│  Investor personas: fresh for 7 days.               │
│  Saves: LLM tokens (most expensive gate).           │
└─────────────────────────────────────────────────────┘
        │ miss → invoke LLM tool
        ▼
┌─────────────────────────────────────────────────────┐
│  GATE 4 — Guard rails (usage/guards.py)             │
│  check_token_limit() → HTTP 429 if daily limit hit  │
│  check_api_call_limit() → HTTP 429 if calls limit   │
│  Saver mode bypasses all guards (by design).        │
└─────────────────────────────────────────────────────┘
        │
        ▼
   LLM executes → result stored in ResearchCache
   Usage tracked in usage.json
   X-Usage-* headers on every response
```

**Where token savings accumulate:**
- Same ticker searched twice in same day → Gate 2 + Gate 3 both hit → 0 API calls, 0 LLM tokens
- Earnings transcript runs once per quarter → Gate 3 returns cached result for 90 days
- Saver mode → Gate 1 blocks everything → 0 tokens regardless of cache state

---

<!-- SEC:CACHE -->
## Cache Strategy — Per-Tool TTLs

**Design principle:** TTL = how long that data stays meaningfully accurate, not a fixed global value.
Mismatching TTL to data freshness wastes API calls (too short) or serves stale data (too long).

**Storage decision (current implementation):**
- **PostgreSQL (StockDataCache / ResearchCache)** — all caching uses DB for durability. Survives server restarts.
- **Redis (future)** — planned for real-time/intraday data (< 1 day TTL) to reduce DB load. Not yet wired up.

Per-tool TTLs are configured in `backend/app/config.py` as individual `CACHE_TTL_*` env vars.
Per-tool routing is in `backend/app/services/data_cache.py` — `_stock_data_ttl_days()` and `_llm_ttl_hours()`.

### Non-LLM Tool Data (StockDataCache)

| Tool | Changes how often | TTL | Storage | Config field |
|---|---|---|---|---|
| `get_news_impact` | Hourly | 30 min | DB | `CACHE_TTL_NEWS_HOURS=0.5` |
| `get_congressional_trades` | As filed (sporadic) | 24 hours | DB | `CACHE_TTL_CONGRESSIONAL_HOURS=24` |
| `get_analyst_consensus` | Weekly/sporadic | 1 day | DB | `CACHE_TTL_ANALYST_DAYS=1` |
| `get_short_interest` | Bi-weekly (FINRA) | 7 days | DB | `CACHE_TTL_SHORT_INTEREST_DAYS=7` |
| `get_fundamentals` (P/E, margins, FCF) | Quarterly | 30 days | DB | `CACHE_TTL_FUNDAMENTALS_DAYS=30` |
| `get_earnings` history + EPS | Quarterly | Until `next_earnings_date` | DB | — (dynamic) |
| `get_price`, `get_technicals`, `get_macro_environment`, `get_sector_heatmap` | Intraday | Not cached — always fresh | — | — |

### LLM Tool Data (ResearchCache)

| Tool | TTL | Storage | Config field |
|---|---|---|---|
| `get_convergence_score` | 30 min | DB | `CACHE_TTL_LLM_SHORT_HOURS=0.5` |
| `get_risk_reward` | 30 min | DB | `CACHE_TTL_LLM_SHORT_HOURS=0.5` |
| `get_sentiment` | 30 min | DB | `CACHE_TTL_LLM_SHORT_HOURS=0.5` |
| `get_options_intelligence` | 30 min | DB | `CACHE_TTL_LLM_SHORT_HOURS=0.5` |
| `analyze_paper_trade` | 1 hour | DB | hardcoded 1.0h |
| `get_news_impact` | 2 hours | DB | `CACHE_TTL_LLM_TIER2_HOURS=2.0` |
| `get_price_forecast` | 24 hours | DB | `CACHE_TTL_LLM_TIER3_HOURS=24` |
| `get_cascade_impact` | 24 hours | DB | `CACHE_TTL_LLM_TIER3_HOURS=24` |
| `bull_bear_debate` | 24 hours | DB | `CACHE_TTL_LLM_TIER3_HOURS=24` |
| `get_earnings_quality` | 30 days | DB | `CACHE_TTL_EARNINGS_QUALITY_DAYS=30` |
| `investor_personas` | 7 days | DB | `CACHE_TTL_LLM_PERSONAS_HOURS=168` |
| `run_backtest` | 7 days | DB | `CACHE_TTL_LLM_BACKTEST_HOURS=168` |
| `analyze_earnings_transcript` | Until `next_earnings_date` | DB | dynamic via `earnings_expiry()` |

### Implementation Files
- `backend/app/config.py` — all `CACHE_TTL_*` fields; overridable via `.env`
- `backend/app/services/data_cache.py` — `_llm_ttl_hours()` and `_stock_data_ttl_days()` routing; `set_llm_cache(expires_at=)` for dynamic TTL
- `backend/app/api/research_v2.py` — tier3 endpoint uses `earnings_expiry(result)` for `analyze_earnings_transcript`

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

ResearchCache     # ticker, tool (mode), result (JSON), cached_at, expires_at
                  # Stores: LLM Tier 2/3 results with per-tool TTL
                  # Key: (ticker, tool) — one row per ticker+tool combination
                  # expires_at: set dynamically from CACHE_TTL_PER_TOOL[tool]
                  # Special case: analyze_earnings_transcript → expires_at = next_earnings_date

StockDataCache    # ticker, tool, result (JSON), cached_at, expires_at
                  # Stores: non-LLM Tier 1 data with per-tool TTL
                  # Key: (ticker, tool) — one row per ticker+tool combination
                  # Redis-first: short TTL tools (< 1 day) checked in Redis before DB
                  # DB fallback: long TTL tools (≥ 1 day) stored only in DB

ScannerAlert      # Daily Target Trade Scanner — every fired signal + its outcome
                  # id (UUID PK), ticker, signal_type, side, session_window
                  # entry_price, target_price, stop_price, entry_time (timestamptz)
                  # score, signals (JSONB), vix_at_entry, capital_used
                  # source ("live" | "backtest")
                  # status ("open" | "win" | "loss" | "expired")
                  # outcome_price, outcome_time, actual_pnl_pct, actual_pnl_dollar
                  # resolved_by ("target_hit" | "stop_hit" | "time_stop" | "eod_close")
                  # five_min_direction ("up" | "down" | "flat" | NULL — direction at entry+5min)
                  # See docs/reference/features.md SEC:DIP_SCANNER for full lifecycle and gates.
```

**Planned additions (not yet built):**
```python
# No new models needed for caching — StockDataCache and ResearchCache
# cover all tools once per-tool TTL is implemented (PRE-1 sprint).
```

Migration: `make migration MSG="description"` then `make migrate`
