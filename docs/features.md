# docs/features.md — Execution modes, tiers, guard rails, usage tracking, background jobs
# Sections: grep -n "SEC:" docs/features.md
# SEC:EXEC_MODES        saver / normal / deep — what each does
# SEC:TIERS             T1/T2/T3 — when runs, LLM, tools
# SEC:TOKEN_ESTIMATES   Per-tool token costs
# SEC:GUARD_RAILS       Usage limits, enforcement, limit values
# SEC:USAGE_TRACKING    usage.json structure, read/write path
# SEC:BACKGROUND_JOBS   APScheduler jobs
# SEC:CONVERGENCE       Signal convergence score (0-100) logic
# SEC:ALERTS            Alert system (watchlist + screener)

---

<!-- SEC:EXEC_MODES -->
## Execution Modes

Set in frontend via `ExecModeBar`. Stored in Zustand `execMode`. Passed as `exec_mode` in requests.

| Mode | T1 | T2 | T3 | Token cost |
|---|---|---|---|---|
| `saver` | Auto (data only) | Rule-based, 0 tokens; T2 buttons disabled | Disabled | 0 |
| `normal` | Auto | Click to expand → loads on demand | Click to run | ~500–2,500 /session |
| `deep` | Auto | Auto-expanded AND auto-loaded on mount | Still click-to-run | ~5,000–18,000 /session |

**Saver mode bypasses ALL token limits** — by design. Do not add guards for it.

In `deep` mode, T2 panels start pre-opened and fire `onExpand` immediately (via `useEffect` in `ExpandablePanel`), triggering the tier2 API calls automatically.

---

<!-- SEC:TIERS -->
## Feature Tiers

| Tier | Triggered by | LLM? | Backend endpoint | Timeout |
|---|---|---|---|---|
| 1 | Every search, auto | No | `POST /v2/research/tier1` | 30 s (Axios) |
| 2 | User click (or deep auto) | Some tools yes | `POST /v2/research/tier2` | 25 s server-side |
| 3 | User click only | Yes | `POST /v2/research/tier3` | 90 s server-side |

**Tier 1 tools** (called sequentially in one thread, 0 LLM tokens):
get_price, get_technicals, get_analyst_consensus, get_earnings, get_fundamentals,
get_short_interest, get_congressional_trades, get_macro_environment, get_sector_heatmap

**Tier 2 tools** (one per panel click):
get_news_impact, get_sentiment, get_convergence_score, get_price_forecast, get_risk_reward

**Tier 3 tools** (deep, expensive):
investor_personas, bull_bear_debate, run_backtest, analyze_earnings_transcript,
analyze_paper_trade, get_congressional_trades (deep variant)

---

<!-- SEC:TOKEN_ESTIMATES -->
## Token Consumption Estimates

| Tool | Est. tokens |
|---|---|
| get_news_impact | 600 |
| get_sentiment | 500 |
| get_convergence_score | 700 |
| get_price_forecast | 800 |
| get_risk_reward | 500 |
| investor_personas | 5,000 |
| bull_bear_debate | 6,000 |
| run_backtest | 0 (pure pandas) |
| analyze_earnings_transcript | 4,000 |
| analyze_paper_trade | 800 |
| get_congressional_trades | 0 |

Typical session costs:
- No panels opened: 0
- Opens news + convergence + forecast: ~2,100
- All T2 panels open: ~3,600
- Investor personas (T3): ~5,000
- Full everything: ~15,000–18,000
- Cache hit (any tier): 0

---

<!-- SEC:GUARD_RAILS -->
## Guard Rails System

Files: `backend/app/services/usage/`
- `limits.py` — ALL threshold values; **edit here only, not in config.py**
- `tracker.py` — async read/write of `data/usage.json`; thread-safe
- `guards.py` — `check_token_limit()`, `check_api_call_limit()` — called before LLM/API calls; raise HTTP 429 if exceeded

Default limits (overridable via env vars):

| Limit | Default | Env var |
|---|---|---|
| Tokens / day | 50,000 | `TOKEN_DAILY_LIMIT` |
| Tokens / week | 200,000 | `TOKEN_WEEKLY_LIMIT` |
| Tokens / month | 500,000 | `TOKEN_MONTHLY_LIMIT` |
| Tokens / search | 20,000 | `TOKEN_PER_SEARCH_LIMIT` |
| API calls / day | 500 | `API_CALLS_DAILY_LIMIT` |
| API calls / minute | 30 | `API_CALLS_PER_MINUTE_LIMIT` |
| Unique tickers / day | 50 | `TICKERS_DAILY_LIMIT` |
| Same ticker / hour | 10 | `TICKERS_PER_HOUR_LIMIT` |

Usage headers added to every response: `X-Usage-Tokens-Today`, `X-Usage-Tokens-Pct`, `X-Usage-Warning`

---

<!-- SEC:USAGE_TRACKING -->
## Usage Tracking

File: `data/usage.json` (path overridable via `USAGE_FILE` env var)
Created automatically on first LLM call. Zero-filled if missing (usage API returns 0s).

```json
{
  "daily":   { "2025-04-27": { "tokens": 2300, "api_calls": 14, "tickers": ["AAPL","META"] } },
  "weekly":  { "2025-W17": { "tokens": 8100, "api_calls": 55 } },
  "monthly": { "2025-04": { "tokens": 21000, "api_calls": 210 } },
  "all_time": { "tokens": 80000, "api_calls": 900 }
}
```

Read by `/usage/today` and `/usage/history` endpoints.
Cache hits are tracked here and cost 0 tokens.

---

<!-- SEC:BACKGROUND_JOBS -->
## Background Jobs (APScheduler)

Configured in `backend/app/services/scheduler.py`, started in FastAPI lifespan.

| Job | Interval | Behavior |
|---|---|---|
| `evaluate_watchlist` | 5 min | Runs all active watchlist tickers through tools; fires WebSocket alert if strong signal |
| `run_screener_background` | 15 min | Runs all `auto_monitor=True` screener presets; fires WebSocket alert on matches |

Both jobs share the same `_yf_client.py` rate limiter. Heavy watchlist evaluation can slow tier2 tool calls if they run concurrently (same lock). Intervals are configurable via `WATCHLIST_ALERT_INTERVAL_MINUTES` and `SCREENER_INTERVAL_MINUTES` env vars.

---

<!-- SEC:CONVERGENCE -->
## Signal Convergence Score

Tool: `get_convergence_score` in `remaining_tools.py`
Range: 0–100 (clamped). Higher = stronger buy conviction.

| Score | Label |
|---|---|
| ≥ 75 | Strong buy — high conviction |
| 60–74 | Buy — good setup |
| 50–59 | Weak buy — wait for better entry |
| 40–49 | Neutral — insufficient signal |
| < 40 | Avoid — bearish signals dominant |

Inputs weighted: RSI, MACD, analyst consensus, sentiment, insider activity,
options flow, macro environment, news sentiment. All optional — defaults to 0/empty.

---

<!-- SEC:ALERTS -->
## Alert System

**Trigger paths:**
1. Background scheduler → `alert_engine.py` → evaluates watchlist/screener → broadcasts via WebSocket
2. Any alert → saved to `AlertHistory` DB table

**WebSocket message shape (watchlist):**
```json
{ "type": "watchlist_alert", "ticker", "signal", "score", "price",
  "change_7d", "title", "body", "timestamp" }
```

**WebSocket message shape (screener):**
```json
{ "type": "screener_alert", "ticker", "preset", "title", "body",
  "stock": {ScreenerResult}, "timestamp" }
```

Frontend: `AlertToast` component + Zustand `alerts[]`. Persistent connection in `App.tsx` survives page navigation.
