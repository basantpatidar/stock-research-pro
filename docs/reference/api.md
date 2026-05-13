# docs/api.md — All HTTP endpoints, request/response shapes, auth
# Sections: grep -n "SEC:" docs/api.md
# SEC:AUTH          API key pattern
# SEC:V1_ROUTES     Original research, watchlist, screener, alerts, macro
# SEC:V2_ROUTES     Tiered research routes (tier1/tier2/tier3/estimate)
# SEC:MCF_ROUTES    Market Context First (MCF) scanner
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

<!-- SEC:DIP_SCANNER_ROUTES -->
## Dip Scanner Routes (prefix `/dip-scanner`)

### Manual scan
`POST /dip-scanner/scan`
```json
Request:  { "tiers": [1], "capital": 1000.0, "vix": null }
Response: {
  "opportunities": [...],                 // dip-buy setups, score >= 72
  "orb_opportunities": [...],             // ORB breakout setups
  "vwap_opportunities": [...],            // VWAP reclaim setups
  "failed_breakdown_opportunities": [...],// trapped-shorts setups
  "best": <Opportunity | null>,           // highest-score across all types (entry-refined for dip-class)
  "vix_spike_prep": <VixSpikePrep | null>,
  "regime": { "regime": "chop|trend_up|trend_down|mean_revert", "reason": "..." },
  "scenario_key": "buy_dip_at_support",
  "tickers_scanned": 2,
  "session_window": "power_hour",
  "vix": 18.4,
  "timestamp": "2026-05-08T14:32:00Z",
  "capital": 1000.0
}
```
Each `Opportunity` carries the full payload documented in features.md SEC:DIP_SCANNER (including `signal_type`, `confidence_tier`, `atr_5m`, `time_stop_minutes`, `entry_refined`, `top_reasons`, `invalidation`).

Zero LLM tokens. Persists all opportunities as `ScannerAlert` rows via `_save_alert`, which enforces a 15-min per-ticker dedup gate (live source only — see features.md).

### Configuration reference
`GET /dip-scanner/config`
```json
Response: { "etf_tiers": {1: ["SPY","QQQ"], 2: ["XLK"]},
            "session_windows": {...}, "default_capital": 1000,
            "score_threshold": 65,    // legacy: actual fire threshold is 72; 65-71 logged as near-miss
            "trading_hours_et": {"regular_open":"9:40 AM","regular_close":"4:00 PM",
                                  "pre_market":"4:00 AM","after_hours_close":"8:00 PM"} }
```
Note: `score_threshold` field is the historical near-miss boundary, not the fire threshold (72). See `_log_near_miss()` in `dip_scanner.py`.

### Analytics (win/loss history)
`GET /dip-scanner/analytics`
```json
Response: {
  "total_signals", "wins", "losses", "win_rate_pct",
  "avg_win_pct", "avg_loss_pct",
  "expected_value_pct", "expected_value_dollar",
  "current_streak": { "type": "win", "count": 3 },
  "data_sources": ["live","backtest"],
  "live_signals": 12, "backtest_signals": 240,
  "by_ticker":             { "SPY": { "signals", "wins", "losses", "win_rate_pct", "avg_pnl_pct" } },
  "by_window":             { "power_hour": { "signals", "wins", "losses", "win_rate_pct", "label" } },
  "by_signal_type":        { "dip_buy": { "signals", "wins", "losses", "win_rate_pct", "avg_pnl_pct" } },
  "by_signal_type_summary":{ "dip_buy": { "win_rate", "ev_dollar" } },
  "by_score_band":         { "72-79": {...}, "80-89": {...}, "90+": {...} },
  "five_min_accuracy":     { "up_correct_pct", "flat_pct", "down_correct_pct" },
  "recent_alerts": [...],         // last 20 resolved alerts
  "cumulative_pnl": [...]         // chronological series for chart
}
```
Only returns resolved (win/loss) alerts — open alerts excluded.

### Similar past setups (reference cases)
`GET /dip-scanner/similar?ticker=QQQ&session=morning_trend&signal_type=dip_buy&limit=4`
```json
Response: {
  "ticker": "QQQ", "session": "morning_trend", "signal_type": "dip_buy",
  "setups": [
    { "entry_time", "entry_price", "outcome_price", "status",
      "actual_pnl_pct", "actual_pnl_dollar", "score", "resolved_by" }
  ]
}
```
Returns up to `limit` closed signals (status != "open") matching the cell, newest first. Powers the "Similar past setups" mini-cards on each scanner card.

### Ticker history
`GET /dip-scanner/ticker-history/{ticker}?limit=30`
```json
Response: {
  "ticker": "QQQ", "count": 12,
  "signals": [
    { "id", "signal_type", "side": "BUY", "entry_time", "session_window",
      "score", "entry_price", "target_price", "stop_price",
      "status", "outcome_price", "actual_pnl_pct", "actual_pnl_dollar",
      "resolved_by", "five_min_direction" }
  ]
}
```
All past `scanner_alerts` for one ticker, newest first. Powers the `TickerHistoryModal` (click ticker name in scanner card).

### AI signal analysis (~500 LLM tokens)
`POST /dip-scanner/analyze`
```json
Request:  {
  "ticker", "signal_type", "score", "confidence_tier?",
  "session_window_label", "entry_price", "target_price", "stop_price",
  "risk_reward_ratio", "atr_5m?", "rsi_5m", "rvol", "vix", "dip_pct",
  "signals[]", "top_reasons?[]"
}
Response: {
  "ticker", "verdict": "FAVORABLE|MIXED|UNFAVORABLE",
  "plain_english": "...",
  "key_risk":      "...",
  "watch_for":     "...",
  "history_count": 12,
  "win_rate_pct":  66.7,
  "tokens_used":   500   // 0 if LLM failed and rule-based fallback fired
}
```
Click-triggered ("What does this mean?" in pro view). Pulls last 30 closed signals for `(ticker, signal_type)` to ground the prompt with historical win rate / avg win / avg loss. Result clears on next scan. Blocked in saver mode.

### Intraday chart data
`GET /dip-scanner/chart/{ticker}` — 1-day 5-min OHLC bars (with pre/after-market) for the scanner card chart.
```json
Response: { "ticker": "QQQ", "bars": [{ "time", "open", "high", "low", "close" }] }
```

### Weekly P&L
`GET /dip-scanner/weekly`
```json
Response: {
  "week_start": "2026-05-05",
  "total_pnl_dollar": 87.50,
  "wins": 3, "losses": 1, "trade_count": 4,
  "by_day": { "Mon": 45.00, "Tue": -12.50, "Wed": 55.00 },
  "best_day": "Wed", "worst_day": "Tue"
}
```
Filters `source == "live"` only. Resets each Monday (ISO week).

### Historical backfill (run once or after scoring changes)
`POST /dip-scanner/backfill`
```json
Request:  { "tiers": [1], "days": 60 }
Response: { "status": "started", "tickers": [...], "days": 60, "message": "..." }
```
Runs in background via `BackgroundTasks`. **Destructive**: clears all existing `source == "backtest"` rows before replaying scanner logic — so re-runs always reflect the latest scoring rules. Replays over the last N days of 5-min yfinance data; outcomes simulated by walking forward bars (target_hit / stop_hit / eod_close).

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

Message types: `connected`, `heartbeat`, `pong`, `watchlist_alert`, `screener_alert`, `dip_buy_alert`

`dip_buy_alert` payload: `{ ticker, signal_type, score, entry_price, target_price, stop_price, session_window_label, scenario_key }`
