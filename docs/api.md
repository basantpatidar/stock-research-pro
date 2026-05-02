# docs/api.md — All HTTP endpoints, request/response shapes, auth
# Sections: grep -n "SEC:" docs/api.md
# SEC:AUTH          API key pattern
# SEC:V1_ROUTES     Original research, watchlist, screener, alerts, macro
# SEC:V2_ROUTES     Tiered research routes (tier1/tier2/tier3/estimate)
# SEC:USAGE_ROUTES  Usage tracking routes
# SEC:REALTIME      SSE stream + WebSocket

---

<!-- SEC:AUTH -->
## Auth

Header: `X-API-Key: <value>` (set via `API_KEY` env var, default `dev-secret-key-change-in-production`)
Dev mode: missing key is allowed (bypassed).
Upgrade path: replace body of `verify_api_key()` in `auth.py` — all routes use `Depends(verify_api_key)`.

---

<!-- SEC:V1_ROUTES -->
## V1 Routes

### Research
| Method | Path | Description |
|---|---|---|
| POST | `/research/` | Full LangGraph agent run → JSON result |
| GET | `/research/data` | Direct tool fetch (no LLM) — price, technicals, analyst, earnings, news |
| GET | `/research/stream` | SSE agent reasoning stream |

`POST /research/` body:
```json
{ "ticker": "AAPL", "mode": "day_trade|long_term|both", "depth": "quick|deep", "question": "" }
```

`GET /research/stream` query params: `ticker`, `mode`, `depth`, `api_key`

### Watchlist
| Method | Path | Description |
|---|---|---|
| GET | `/watchlist/` | All active items |
| POST | `/watchlist/` | Add ticker `{"ticker":"AAPL"}` |
| DELETE | `/watchlist/{ticker}` | Soft-delete |
| GET | `/watchlist/signals` | Items with active buy/sell signal only |

### Screener
| Method | Path | Description |
|---|---|---|
| POST | `/screener/run` | Run with filters (see below) |
| GET/POST | `/screener/presets` | List / save presets |
| POST | `/screener/presets/{id}/run` | Run saved preset |
| PATCH | `/screener/presets/{id}/toggle-monitor` | Toggle auto-monitor |

Screener filter body:
```json
{ "min_market_cap_b": 100, "min_volume": 1000000, "min_price_drop_pct": 10.0, "sector": "all", "max_pe": 0 }
```

### Alerts
| Method | Path | Description |
|---|---|---|
| WS | `/alerts/ws?api_key=...` | Live alert push (persistent, auto-reconnect) |
| GET | `/alerts/history` | Recent alert history |
| PATCH | `/alerts/history/{id}/dismiss` | Dismiss alert |

### Macro
| Method | Path |
|---|---|
| GET | `/macro/all` — macro + sectors + geopolitical + FRED in one call |
| GET | `/macro/environment` — VIX, S&P, oil, yields, gold, USD |
| GET | `/macro/sectors` — 11 sector ETFs 5d performance |
| GET | `/macro/geopolitical` — active geopolitical events |
| GET | `/macro/fred` — FRED credit spreads, yield curves, real yields, M2, cross-asset (requires `FRED_API_KEY`) |

### Health
`GET /health` → `{status, provider, model, environment}`

---

<!-- SEC:V2_ROUTES -->
## V2 Routes (prefix `/v2/research`)

### Tier 1 — always runs, no LLM
`POST /v2/research/tier1`
```json
Request:  { "ticker": "META", "mode": "both", "exec_mode": "normal" }
Response: { "ticker", "price", "technicals", "analyst", "earnings",
            "fundamentals", "short_interest", "congressional",
            "macro", "sectors", "cached": false, "exec_mode" }
```
Tools called (sequential, single thread): get_price, get_technicals, get_analyst_consensus,
get_earnings, get_fundamentals, get_short_interest, get_congressional_trades,
get_macro_environment, get_sector_heatmap.

### Tier 2 — user-triggered, click to expand
`POST /v2/research/tier2`
```json
Request:  { "ticker", "tool": "get_news_impact", "mode", "exec_mode", "params": {} }
Response: { "ticker", "tool", "result": <tool output>, "tokens_used", "cached", "exec_mode" }
```
Valid `tool` values: `get_news_impact`, `get_sentiment`, `get_convergence_score`,
`get_price_forecast`, `get_risk_reward`

Timeout: 25 s (returns HTTP 504 if exceeded).

Note: pass `params.company_name` when calling `get_news_impact` to skip the
internal yfinance lookup and prevent slow/hanging requests.

### Tier 3 — deep on-demand
`POST /v2/research/tier3`
```json
Request:  { "ticker", "tool": "investor_personas", "mode", "params": {} }
Response: { "ticker", "tool", "result", "tokens_used", "cached" }
```
Valid `tool` values: `investor_personas`, `bull_bear_debate`, `run_backtest`,
`analyze_earnings_transcript`, `analyze_paper_trade`, `get_congressional_trades`

Timeout: 90 s (returns HTTP 504 if exceeded).

### Token estimate
`GET /v2/research/tier3/estimate?tool=investor_personas&ticker=AAPL`
```json
Response: { "tool", "estimated_tokens": 5000, "estimated_cost_usd": 0.003, "cached": false }
```

---

<!-- SEC:USAGE_ROUTES -->
## Usage Routes

`GET /usage/today`
```json
Response: { "tokens_today", "tokens_today_pct", "api_calls_today",
            "tickers_today": ["AAPL","META"], "warning": null }
```

`GET /usage/history`
```json
Response: {
  "daily": [{ "date": "2025-04-27", "tokens": 2300, "api_calls": 14 }],
  "limits": { "token_daily_limit", "token_weekly_limit",
               "token_monthly_limit", "api_calls_daily_limit" }
}
```
Returns last 30 days. Returns zeros if `data/usage.json` does not exist yet.

---

<!-- SEC:REALTIME -->
## Real-time Communication

### SSE — agent reasoning stream
Endpoint: `GET /research/stream` or `GET /v2/research/stream`
Client: `useSSE.ts` hook, browser `EventSource` API

Event shape:
```json
{ "type": "start"|"tool_call"|"tool_result"|"reasoning"|"done"|"error", ... }
```

### WebSocket — live alerts
Endpoint: `WS /alerts/ws?api_key=...`
Client: `useWebSocket.ts` hook — persistent connection mounted in `App.tsx`.
Auto-reconnect every 5 s on disconnect. Ping/pong keepalive every 20 s.

Message types: `connected`, `heartbeat`, `pong`, `watchlist_alert`, `screener_alert`
