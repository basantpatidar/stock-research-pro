# Stock Research Pro — Claude Code Memory File

> This file is the single source of truth for Claude Code when working on this project.
> Update this file whenever architecture, decisions, or conventions change.

---

## Project identity

**Name:** Stock Research Pro
**Purpose:** AI-powered stock research platform for day trading and long-term investment decisions
**Status:** V1 complete, V2 in progress (token optimization + new features)
**GitHub:** Add your repo URL here
**Owner:** Basant (Senior Full-Stack Engineer, NJ/NY area)

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.12 |
| Backend framework | FastAPI + uvicorn |
| Agent orchestration | LangGraph (ReAct pattern) |
| Background jobs | APScheduler |
| Frontend | React 18 + TypeScript + Vite |
| Charts | Recharts |
| State management | Zustand |
| HTTP client | Axios |
| Primary database | PostgreSQL (async via asyncpg + SQLAlchemy) |
| Cache | Redis |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Testing (backend) | pytest + pytest-asyncio + httpx |
| Migrations | Alembic |

---

## LLM provider architecture

**Key design:** Provider-agnostic. Swap LLM by changing one `.env` variable — zero code changes.

**Factory:** `backend/app/llm/factory.py` → `get_llm(settings)` returns a `BaseChatModel`

| `MODEL_TYPE` | Provider | Notes |
|---|---|---|
| `groq` | Groq (free tier) | Default — `llama-3.3-70b-versatile` |
| `ollama` | Local Ollama (free) | Best for dev — no API key |
| `gemini` | Google Gemini | Free tier available |
| `claude` | Anthropic Claude | Paid — highest quality |
| `openai` | OpenAI | Paid |
| `openrouter` | OpenRouter | Free models available |
| `cerebras` | Cerebras | Free tier — OpenAI-compatible |

`get_llm_with_fallback()` tries configured provider → Groq → Cerebras → Ollama automatically.

---

## Project structure

```
stock-research-pro/
├── backend/
│   └── app/
│       ├── agent/
│       │   ├── graph.py        # LangGraph StateGraph — wires all 20 tools
│       │   ├── state.py        # AgentState schema (ticker, mode, messages)
│       │   └── prompts.py      # System prompts: day_trade / long_term / both
│       ├── tools/              # 20 tools — one file each
│       │   ├── price.py        # yfinance — current price, OHLCV, history
│       │   ├── technicals.py   # RSI, MACD, Bollinger, VWAP, 50d/200d MA
│       │   ├── news.py         # NewsAPI — headlines + sentiment
│       │   ├── sentiment.py    # Reddit PRAW + StockTwits
│       │   ├── core_tools.py   # analyst, earnings, fundamentals, options,
│       │   │                   # insider, institutional, short_interest
│       │   ├── geopolitical.py # GDELT + NewsAPI — world events
│       │   ├── remaining_tools.py # macro, sector, cascade, forecast,
│       │   │                      # risk_reward, screener, convergence, trends
│       │   └── [re-exports]    # analyst.py, earnings.py etc. re-export from core_tools
│       ├── api/
│       │   ├── research.py     # POST /research/, GET /research/stream (SSE)
│       │   ├── watchlist.py    # CRUD /watchlist/
│       │   ├── screener.py     # POST /screener/run, /screener/presets
│       │   ├── alerts.py       # WebSocket /alerts/ws
│       │   └── macro.py        # GET /macro/all, /macro/sectors, /macro/geopolitical
│       ├── services/
│       │   ├── alert_engine.py # Background: evaluates watchlist signals
│       │   └── scheduler.py    # APScheduler: watchlist every 5min, screener every 15min
│       ├── db/
│       │   ├── models.py       # WatchlistItem, ScreenerPreset, AlertHistory, ResearchCache
│       │   └── database.py     # Async SQLAlchemy engine + get_db() dependency
│       ├── llm/
│       │   └── factory.py      # Provider-agnostic get_llm() + get_llm_with_fallback()
│       ├── config.py           # Pydantic settings — reads from .env
│       ├── auth.py             # API key middleware — swap for JWT by replacing this file
│       └── main.py             # FastAPI app — mounts all routers, lifespan startup
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── ResearchPage.tsx    # Single stock research dashboard
│       │   ├── WatchlistPage.tsx   # Live signals table + alert feed
│       │   ├── ScreenerPage.tsx    # Filter builder + results + presets
│       │   └── MacroPage.tsx       # Sector heatmap + geo events + macro
│       ├── components/
│       │   ├── research/           # PriceChart, SignalScore, NewsPanel, StreamPanel
│       │   ├── watchlist/          # (inline in WatchlistPage currently)
│       │   ├── screener/           # (inline in ScreenerPage currently)
│       │   ├── macro/              # (inline in MacroPage currently)
│       │   └── shared/             # ModeToggle, SignalTag, AlertToast
│       ├── hooks/
│       │   ├── useSSE.ts           # SSE agent reasoning stream consumer
│       │   ├── useWebSocket.ts     # Persistent WS — auto-reconnect, ping/pong
│       │   ├── useWatchlist.ts     # CRUD + API sync
│       │   └── useScreener.ts      # Filter state + run + presets
│       ├── services/
│       │   └── api.ts              # Axios client — X-API-Key header
│       ├── store.ts                # Zustand — mode, watchlist, alerts, SSE, WS
│       ├── types/index.ts          # All TypeScript interfaces
│       └── App.tsx                 # Router — 4 pages + persistent WebSocket
├── .env.example                    # All env vars documented
├── docker-compose.yml              # backend + frontend + postgres + redis
├── Makefile                        # make up / test / lint / migrate etc.
├── CONTRIBUTING.md
└── README.md
```

---

## Database models

```python
WatchlistItem     # ticker, last_signal, last_score, last_price, last_evaluated
ScreenerPreset    # name, filters (JSON), auto_monitor, last_run
AlertHistory      # ticker, alert_type, title, body, score, triggered_at, source
ResearchCache     # ticker, mode, result (JSON), cached_at, expires_at
```

Migration command: `make migration MSG="description"` then `make migrate`

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/research/` | Full agent run, returns JSON |
| GET | `/research/stream` | SSE stream of agent reasoning |
| GET | `/watchlist/` | All active watchlist items |
| POST | `/watchlist/` | Add ticker |
| DELETE | `/watchlist/{ticker}` | Remove ticker (soft delete) |
| GET | `/watchlist/signals` | Only items with active buy/sell signals |
| POST | `/screener/run` | Run screener with filters |
| GET/POST | `/screener/presets` | List / save screener presets |
| POST | `/screener/presets/{id}/run` | Run saved preset |
| PATCH | `/screener/presets/{id}/toggle-monitor` | Enable/disable auto-monitor |
| WS | `/alerts/ws` | Live alert push (pass api_key as query param) |
| GET | `/alerts/history` | Recent alert history |
| PATCH | `/alerts/history/{id}/dismiss` | Dismiss alert |
| GET | `/macro/all` | Macro + sectors + geo events in one call |
| GET | `/macro/environment` | VIX, S&P, oil, yields, risk status |
| GET | `/macro/sectors` | Sector heatmap 5d |
| GET | `/macro/geopolitical` | Active geopolitical events |
| GET | `/health` | Health check + provider info |

---

## The 20 agent tools

All tools use `@tool` decorator from `langchain_core.tools`.
**Critical rule: tools NEVER raise exceptions — always return `{"error": "..."}` on failure.**

| Tool | Source | What it returns |
|---|---|---|
| `get_price` | yfinance | Current price, OHLCV, 7d change, history |
| `get_technicals` | yfinance | RSI, MACD, Bollinger, VWAP, 50d/200d MA |
| `get_news_impact` | NewsAPI | Headlines + sentiment breakdown |
| `get_sentiment` | StockTwits + Reddit | Bullish/bearish % + sample posts |
| `get_analyst_consensus` | yfinance | Buy/hold/sell %, price target, rating changes |
| `get_earnings` | yfinance | Beat/miss history, next date, beat rate |
| `get_fundamentals` | yfinance | P/E, PEG, margins, debt/equity, FCF |
| `get_options_signals` | yfinance | Put/call ratio, IV, unusual activity |
| `get_insider_activity` | yfinance | SEC Form 4 trades, buy/sell signal |
| `get_institutional_changes` | yfinance | 13F top holders |
| `get_short_interest` | yfinance | Short float %, days-to-cover, squeeze potential |
| `get_geopolitical_events` | NewsAPI | Active events by severity + impacted sectors |
| `get_macro_environment` | yfinance | VIX, S&P, oil, yields, gold, USD |
| `get_sector_heatmap` | yfinance | 11 sector ETFs 5d performance |
| `get_cascade_impact` | (LLM reasoning) | Event → stock impact causal chain |
| `get_price_forecast` | yfinance + LLM | Days/weeks/quarter directional outlook |
| `get_risk_reward` | yfinance | Entry/target/stop, R/R ratio, trade quality |
| `run_screener` | yfinance | Filters: market cap, volume, drop %, sector |
| `get_convergence_score` | (all signals) | 0–100 score aggregating all signals |
| `get_trends` | pytrends | Google Trends interest spike detection |

### Adding a new tool (3 steps)
1. Create `backend/app/tools/my_tool.py` with `@tool` decorator
2. Import in `backend/app/agent/graph.py` → add to `ALL_TOOLS` list
3. Write test in `tests/tools/test_tools.py`

---

## Authentication

**Current:** API key middleware in `auth.py`
- Pass as header: `X-API-Key: your-key`
- Dev mode: missing key is allowed (bypassed)
- Set in `.env`: `API_KEY=your-secret-key`

**To upgrade to JWT:**
1. Replace body of `verify_api_key()` in `auth.py` with JWT decode
2. Update `Security()` dependency imports if needed
3. Nothing else changes — all routes use `Depends(verify_api_key)`

---

## Real-time communication

**SSE** (`/research/stream`) — agent reasoning steps stream to frontend
- Used for: watching agent think step by step
- Frontend: `useSSE.ts` hook, `EventSource` API
- Each event: `{type: "tool_call" | "tool_result" | "reasoning" | "done" | "error"}`

**WebSocket** (`/alerts/ws`) — live push for watchlist/screener alerts
- Persistent connection mounted in `App.tsx` — survives page navigation
- Auto-reconnect every 5s on disconnect
- Ping/pong keepalive every 20s
- Frontend: `useWebSocket.ts` hook
- Alert types: `watchlist_alert`, `screener_alert`

---

## Background jobs (APScheduler)

| Job | Interval | What it does |
|---|---|---|
| `evaluate_watchlist` | Every 5 min | Checks all watchlist tickers, fires alerts for strong signals |
| `run_screener_background` | Every 15 min | Runs all auto-monitor presets, fires alerts on matches |

Both jobs broadcast via WebSocket when they fire an alert.

---

## Data sources

| Source | What | Cost | Key env var |
|---|---|---|---|
| yfinance | Prices, technicals, options, fundamentals | Free (unofficial Yahoo) | None |
| NewsAPI | Headlines, geopolitical news | Free (100/day dev) | `NEWSAPI_KEY` |
| Reddit PRAW | WSB, r/stocks sentiment | Free | `REDDIT_CLIENT_ID/SECRET` |
| StockTwits | Trader sentiment, self-tagged | Free (no auth needed) | None |
| SEC EDGAR | 10-K, 10-Q, Form 4, 13F | Free | None |
| GDELT | Global geopolitical events | Free | None |
| Google Trends | Retail attention spikes | Free (pytrends) | None |

---

## Trade mode vs exec mode

**Trade mode** (day_trade / long_term / both) — changes agent system prompt and which signals are prioritized in the analysis.

**Exec mode** (V2 only — see V2 section below) — controls token usage:
- `saver`: zero LLM calls, rule-based only
- `normal`: Tier 1 auto + Tier 2 on click + Tier 3 on demand
- `deep`: everything runs automatically

---

## Signal convergence score

A 0–100 score that aggregates all signals. Higher = stronger buy conviction.

| Score | Label |
|---|---|
| ≥75 | Strong buy — high conviction |
| 60–74 | Buy — good setup |
| 50–59 | Weak buy — wait for better entry |
| 40–49 | Neutral — insufficient signal |
| <40 | Avoid — bearish signals dominant |

Inputs: RSI, MACD, analyst consensus, sentiment, insider activity, options flow, macro environment, news sentiment. Each weighted differently. Score clamped 0–100.

---

## Screener filters

```python
min_market_cap_b: float = 100.0   # minimum market cap in billions
min_volume: int = 1_000_000       # minimum daily volume
min_price_drop_pct: float = 10.0  # minimum 7-day decline to qualify
sector: str = "all"               # sector filter
max_pe: float = 0.0               # 0 = no PE filter
```

Screener runs against a hardcoded list of ~30 large-cap tickers currently. To expand, add tickers to `large_cap_tickers` in `remaining_tools.py`.

---

## Environment variables

```bash
# LLM
MODEL_TYPE=groq
MODEL_NAME=llama-3.3-70b-versatile
OLLAMA_MODEL=llama3.2
GROQ_API_KEY=
CEREBRAS_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Data
NEWSAPI_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=StockResearchPro/1.0

# App
API_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stockresearch
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development

# Background jobs
SCREENER_INTERVAL_MINUTES=15
WATCHLIST_ALERT_INTERVAL_MINUTES=5
```

---

## Common commands

```bash
make up           # Docker — start everything
make backend      # Local — FastAPI on :8000
make frontend     # Local — Vite on :5173
make test         # Run all 45 tests
make test-tools   # Tool unit tests only
make test-api     # API integration tests only
make lint         # ruff check
make fmt          # black format
make typecheck    # tsc --noEmit
make migrate      # Apply pending migrations
make migration MSG="add_table"  # Generate migration
make health       # curl /health
make clean        # Remove cache/artifacts
```

---

## Testing conventions

- All tests in `backend/tests/`
- Tool tests: `tests/tools/test_tools.py` — mock yfinance with `mock_yfinance` fixture
- API tests: `tests/api/test_api.py` — use SQLite in-memory via `client` fixture
- LLM tests: `tests/tools/test_llm_factory.py` — mock LangChain classes
- **Never hit real APIs in tests** — always mock yfinance, NewsAPI, LLM providers
- Tools must return `{"error": "..."}` not raise — test this explicitly
- Run with: `PYTHONPATH=. python -m pytest tests/ -v`

---

## Known decisions and why

| Decision | Reason |
|---|---|
| One tool per file | Each tool independently testable, readable on GitHub, replaceable |
| Tools return error dicts never raise | Agent loop survives tool failures gracefully |
| SSE for agent stream, WS for alerts | SSE = unidirectional (agent reasoning), WS = bidirectional (live alerts need server push) |
| Redis cache 15/30 min | yfinance rate limits + avoid hitting APIs on every search |
| APScheduler async | Integrates with FastAPI lifespan, no separate process needed |
| Soft delete on watchlist | Preserve history, easy re-activation |
| Zustand over Redux | Lighter, no boilerplate, sufficient for this app's state complexity |
| Recharts over D3 | Easier React integration, sufficient for price charts |

---

## V2 additions (token optimization + new features)

> V2 files exist in the codebase but ResearchPage v2 is the active version.
> Update this section as V2 stabilizes.

### New files in V2
```
backend/app/tools/token_config.py       # Tier definitions + token estimates
backend/app/tools/saver_mode.py         # Zero-LLM rule-based replacements
backend/app/tools/new/
    investor_personas.py                # Buffett/Graham/Burry/Lynch/Wood
    bull_bear.py                        # Bull vs Bear structured debate
    congressional.py                    # STOCK Act congressional trades
    backtester.py                       # RSI/MACD/Golden cross backtest
    earnings_transcript.py              # Earnings call AI analysis
    paper_trade.py                      # Paper trade journal + AI coaching
backend/app/services/research_orchestrator.py  # Tiered execution + caching
backend/app/api/research_v2.py          # /v2/research/tier1, tier2, tier3

frontend/src/components/shared/
    ExecModeBar.tsx                     # Saver/Normal/Deep toggle + token counter
    ExpandablePanel.tsx                 # Click-to-expand wrapper with tier badge
frontend/src/components/research/
    InvestorPersonasPanel.tsx           # Persona perspective cards
    Tier3Panels.tsx                     # BullBear, Backtester, Congressional
frontend/src/services/researchV2.ts    # Tiered API calls
```

### V2 execution tiers

| Tier | When | LLM | Token cost |
|---|---|---|---|
| 1 | Every search, parallel | No | 0 |
| 2 | User clicks "Analyze" | Yes (or rule-based in saver) | ~400–900 |
| 3 | User clicks deep feature | Yes | ~1k–6k |

### V2 new API routes (prefix `/v2`)
- `POST /v2/research/tier1` — parallel data fetch, no LLM
- `POST /v2/research/tier2` — LLM reasoning on single tool
- `POST /v2/research/tier3` — deep on-demand tool
- `GET /v2/research/tier3/estimate?tool=X` — token estimate before running

---

## Portfolio context

This project is part of Basant's GitHub portfolio alongside:
1. Event-Driven Order Processing (Java 21, Spring Boot 3, Kafka)
2. **Stock Research Pro** ← this project
3. FinAgent: Financial Research (Python, LangGraph, Claude, FastAPI)
4. FinDash: Financial Dashboard (React 18, TypeScript)
5. RAG Document Q&A (Python, LangChain, ChromaDB)
6. ML Transaction Categorizer (scikit-learn, FastAPI)
7. Async Portfolio Risk Engine (Python, asyncio, NumPy)
8. Search UI with Relevance Tuning (React, Fuse.js)
9. Rate-Limited API Gateway (Java 21, Spring Boot 3, Redis)
10. Code Review Agent (Python, Claude, GitHub Actions)

**Narrative:** Stock Research Pro demonstrates the most complete integration of skills across the portfolio — LangGraph agents (from FinAgent), React real-time UI (from FinDash), async Python (from Portfolio Risk Engine), Redis caching (from Rate-Limited Gateway), and background jobs pattern.

---

## Outstanding items / next steps

- [ ] Update this file after V2 stabilizes
- [ ] Add StockTwits API key to `.env.example` (currently no auth needed but rate-limited)
- [ ] Expand screener `large_cap_tickers` list beyond 30 tickers
- [ ] Add `get_congressional_trades` to the LangGraph `ALL_TOOLS` list in `graph.py`
- [ ] Add V2 new tools to `graph.py` `ALL_TOOLS` for deep mode agent use
- [ ] Email notification provider (SendGrid/SES) — `notifier.py` already stubbed
- [ ] Full JWT auth upgrade — `auth.py` is ready to swap
- [ ] Paper trade journal persistence in PostgreSQL (currently stateless per call)
- [ ] Portfolio risk page (multi-stock exposure analysis)
- [ ] Crypto correlation tracker (BTC/ETH vs tech stocks)
- [ ] Dark pool FINRA data integration
