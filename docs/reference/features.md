# docs/features.md — Execution modes, tiers, guard rails, usage tracking, background jobs
# Sections: grep -n "SEC:" docs/features.md

**Doc version:** 1.3 · **Last updated:** 2026-05-17

# SEC:EXEC_MODES        saver / normal / deep — what each does
# SEC:TIERS             T1/T2/T3 — when runs, LLM, tools
# SEC:TOKEN_ESTIMATES   Per-tool token costs
# SEC:GUARD_RAILS       Usage limits, enforcement, limit values
# SEC:USAGE_TRACKING    usage.json structure, read/write path
# SEC:BACKGROUND_JOBS   APScheduler jobs
# SEC:CONVERGENCE       Signal convergence score (0-100) logic
# SEC:ALERTS            Alert system (watchlist + screener)
# SEC:AUTO_PAPER_TRADE  Auto-paper-trade subscriber (Phase 3 validation harness)
# SEC:TELEGRAM          Telegram bot — multi-user, registration, commands, admin

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
get_news_impact, get_sentiment, get_convergence_score, get_price_forecast, get_risk_reward,
get_earnings_quality (0 tokens — pure math), get_options_intelligence (0 tokens — pure math)

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
| get_earnings_quality | 0 (pure math) |
| get_options_intelligence | 0 (pure math) |
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
| `_run_dip_scan` | 5 min | Checks session window AND scanner-halt cap; calls `scan_dip_opportunities`; broadcasts `dip_buy_alert` via WebSocket for any score ≥ 65 opportunity |
| `_run_mcf_scan` | 5 min | Same halt check; runs MCF Funnel; persists alerts directly with `signal_type="mcf_dip_buy"` |
| `_resolve_open_alerts` | 5 min | Fetches current price for all open `ScannerAlert` rows; marks `win` (target hit), `loss` (stop hit), or `expired` (EOD close) |
| `_run_auto_trade_subscriber` | `AUTO_TRADE_POLL_SECONDS` (default 30 s) | Phase 3. Self-skips when `AUTO_TRADE_ENABLED=false` OR empty allowlist OR outside market hours. Otherwise queries open `scanner_alerts` whose `signal_type ∈ AUTO_TRADE_SIGNAL_TYPES` that haven't yet produced a `BrokerOrder`, builds a bracket order from each alert's entry/stop/target, runs `check_order_caps`, persists the `BrokerOrder` (with `source="scanner_alert"` + `scanner_alert_id`), submits via the broker. Idempotent on `client_order_id="auto-{alert.id}"`. |
| `_run_eod_dump` | Cron — Mon-Fri 4:35 PM ET | Subprocesses `local_debugging/eod_dump.py` (located via `LOG_DIR`) so the daily report writes itself with no manual `docker compose exec`. Read-only — SELECTs scanner_alerts + broker_orders, writes `local_debugging/eod_signals/<date>.json` to the host bind mount. Runs after the 3:45 PM resolution pass so all alerts are closed. |

Both watchlist and screener jobs share the same `_yf_client.py` rate limiter. Dip + MCF scan jobs run 0 LLM — always safe in any exec mode. Intervals configurable via env vars.

**Scanner halt-for-day:** the dip + MCF scan jobs both check `should_halt_scanner(settings)` at the top of every tick. Once today's `scanner_alerts` count reaches `SCANNER_DAILY_SIGNAL_CAP` (default 50), both scanners skip remaining ticks for the rest of the trading day. Pairs naturally with `TRADE_DAILY_ORDER_COUNT_CAP` (same default 50) so a runaway auto-trade run also silences the source feeding it.

---

<!-- SEC:DIP_SCANNER -->
## Daily Target Trade Scanner

**Goal:** One intraday trade per day on broad-market ETFs, targeting 1% profit on configurable capital (default $1,000). Zero LLM tokens for scoring; ~500 tokens only when user clicks "What does this mean?" on a fired signal.

**Code:** `backend/app/tools/dip_scanner.py` (scoring), `backend/app/api/dip_scanner.py` (routes + persistence + dedup), `backend/app/services/scheduler.py` (5-min scan + outcome resolver), `backend/app/tools/regime.py` (market regime gate).

### ETF Tiers
```
Tier 1: SPY, QQQ      (default — broad market, highest liquidity)
Tier 2: XLK           (data-driven cull — IWM/DIA/XLF/XLV/TLT removed for sub-50% win rates)
```
Both tiers can be enabled simultaneously via `tiers: [1, 2]`. Background job uses Tier 1 only.

### Market Regime Gate (`classify_regime`)
Computed once per scan (60s cache), gates all four signal types. Inputs: SPY 20-EMA position, VIX 5-day change, range-vs-ATR.

| Regime | Effect on signals |
|---|---|
| `trend_up` | dip_buy requires `RSI < 30` (stricter — only deep oversold in uptrends) |
| `trend_down` | `dip_buy` blocked entirely (no catching falling knives) |
| `chop` / `mean_revert` | All signal types active with normal thresholds |

UI shows a regime badge; blocking banner appears when regime suppresses dip_buy.

### Signal Types

| Signal | Trigger | R:R | Time stop | Notes |
|---|---|---|---|---|
| `dip_buy` | Dip ≥ VIX-adjusted ATR multiple, RSI-5m oversold, declining RVOL, at S1/S2/VAL/VWAP | ATR-based, see below | 25 min | The original setup; mean reversion |
| `orb_breakout` | Price above ORB-15 high with RVOL ≥ 1.5× | 3:1 | 60 min | Trend trades; widest time window |
| `vwap_reclaim` | Price was below VWAP 2+ candles, closes back above, RVOL > 1.2× | 1.5:1 | 20 min | Reclaim fast or fail |
| `failed_breakdown` | Price broke a swing low then closed back above (trapped shorts) | 2.5:1 | 30 min | Asymmetric — trapped shorts cover hard |
| `vix_spike_prep` | VIX up >8% intraday AND SPY down 0.5–2% | — preparation alert, no entry — | — | Banner only |

`scan_dip_opportunities()` scores all candidates per ticker; `best` = highest score across types.
Best signal entry is refined to `min(last 3×1-min lows)` with -0.5% floor (`_refine_entry_1min` — only for dip_buy/vwap_reclaim/failed_breakdown).

### ATR-Based Stops & Targets
At signal generation time, computed from 5-min Wilder ATR-14 (`_get_atr_5m`, 30-min cache):
```
target = entry + max(1.0 × ATR, entry × 0.004)   capped at entry × 1.015 (+1.5%)
stop   = entry − max(0.5 × ATR, entry × 0.0025)  floored at entry × 0.975 (−2.5%)
```
Per-signal-type R multipliers (in scorer): dip_buy 2:1 baseline, ORB 3:1, VWAP 1.5:1, failed_breakdown 2.5:1.
Payload includes `atr_5m`, `atr_adjusted` (bool — fell back to fixed % if ATR unavailable).

### Session Windows

| Window | Hours (ET) | Score Δ | Notes |
|---|---|---|---|
| `morning_flush` | 9:40–10:30 AM | +5 | |
| `morning_trend` | 10:30 AM–12 PM | 0 | |
| `lunch_drift` | 12–2 PM | −5 **+ hard block**: score < 80 → skip | 0% backtest win rate without the block |
| `power_hour` | 2–4 PM | +10 | Extends to market close |
| `pre_market` | 4–9:30 AM | −10 | Extended hours warning |
| `after_hours` | 4–8 PM | −10 | Extended hours warning |
| `closed` | 8 PM–4 AM | skip | No signal |

### VIX → ATR Multiples (dip_buy only)

| VIX | Min dip (× ATR) | Max RSI | Min RVOL |
|---|---|---|---|
| < 18 | 0.4 | 42 | 0.8× |
| 18–25 | 0.7 | 38 | 1.2× |
| 25–35 | 1.1 | 33 | 1.5× |
| > 35 | skip | — | — |

RVOL must also be **declining** (last bar < bar −4) — sellers exhausting, not still in panic.

### Scoring
Base score 50. Fire threshold: **score ≥ 72** (raised from 65 on 2026-05-10 after analytics review). `lunch_drift` requires ≥ 80.

| Signal | Points | Notes |
|---|---|---|
| Price within 0.10×ATR of nearest support (S1/S2/VAL/VWAP) | +15 | ATR-scaled (was fixed 0.2%) |
| Price within 0.20×ATR of nearest support | +10 | |
| Price within 0.35×ATR of nearest support | +5 | |
| Price > 0.35×ATR from any support | −5 | |
| RSI < 30 | +15 | |
| RSI 30–35 | +12 | |
| RSI 35–max_rsi | +8 | |
| RVOL ≥ 1.5× declining | +10 | |
| RVOL 1.0–1.5× declining | +6 | |
| Price below intraday VWAP | +10 | |
| Price > 0.5% above VWAP | −5 | |
| Hammer candle (lower wick >65%, upper-third close, vol ≥ 1.5× avg) | +5 | Reduced from +15 — tiebreaker only |
| VIX 18–35, slope < −2% (vol crush) | +12 | Falling VIX = mean-reversion ideal |
| VIX 18–35, slope −2% to +2% (stable) | +5 | |
| VIX 18–35, slope > +2% (vol expanding) | −10 | Rising fear blocks most signals |
| Capitulation candle (extreme down move + extreme volume) | −15 | Don't catch the panic, wait for the bounce |
| 30-min trend aligned with signal | +5 / +5 / −10 | Aligned / neutral / counter-trend |
| CVD (cumulative volume delta) bullish | +8 / +5 / −5 | Strong bullish / mild bullish / bearish |
| Session delta | ±0 to ±10 | See session windows table |
| Confidence tier | label only | very_high (≥85), high (75–84), medium (72–74) |

Signals scoring 65–71 (passed pattern checks but below fire threshold) are logged to `local_debugging/near_miss_log.jsonl` via `_log_near_miss()` for EOD threshold-tuning analysis. Each entry is stamped with the bar's intraday timestamp (not wall-clock time of the scan) and deduped on `(date, ticker, window, time_et, score)` so repeated scans of the same candle — live + standalone backtest, or two backtest replays — don't inflate the log.

### Scanner Heartbeat
`services/scheduler.py:_run_dip_scan` appends one record per tick to `local_debugging/scanner_heartbeat.jsonl` (path overridable via `SCANNER_HEARTBEAT_LOG`). Fields: `ts_utc`, `ts_et`, `status` (`ok` / `error` / `skipped_closed`), `window`, `tickers`, `candidates` (count across all four signal types), `best_ticker`, `best_score`, `duration_ms`, `error`. Append-only; rotation is intentionally not implemented (file is gitignored debug data, low volume — ~78 ticks per trading day). The EOD report reads this to distinguish "scanner ran but found nothing" from "scanner did not run today" and surfaces the diagnostic as its own analysis prompt.

### Time Stop Enforcement
Scheduler resolver (`_resolve_open_alerts` in `services/scheduler.py`) fires before EOD close. Per-signal-type minutes from `TIME_STOP_MINUTES` dict (mirrors values dip_scanner attaches at signal creation):

```python
TIME_STOP_MINUTES = {
    "dip_buy":          25,
    "orb_breakout":     60,
    "vwap_reclaim":     20,
    "failed_breakdown": 30,
}
```

When `now_et - entry_time >= time_stop_minutes` and neither target nor stop hit: exit at current market price, set `resolved_by = "time_stop"`. Frees capital from dead-money trades that would otherwise drift to ~breakeven by EOD.

### Per-Ticker Dedup
`api/dip_scanner.py:_save_alert` checks for any prior live alert on the same ticker within `DEDUP_WINDOW_MINUTES = 15` and skips insertion if found. Suppresses correlated back-to-back fires (e.g., XLF dip_buy fired twice 12 min apart on 2026-05-08 — both lost).
**Backtest source is exempt** — replays need to record every resolved signal for accurate analytics.

### Forward 5-Min Direction (`five_min_direction`)
Resolver computes direction at entry+5min for every closed row: `"up"` (>+0.05%), `"down"` (<−0.05%), or `"flat"`. Helper `_compute_fmd()` tz-normalizes the yfinance 1-min index to ET before comparison and returns specific failure reasons (logged at debug level instead of swallowed).
Resolver also opportunistically backfills closed rows from the last 7 days where `five_min_direction IS NULL`. Used by analytics: "5-Min Accuracy" metric in ScannerPerformanceCard.

### Capital Sizing
`whole_shares = floor(capital / entry_price)`. Broker stop-loss requires whole shares.
`actual_profit = whole_shares × (target − entry)`. `actual_risk = whole_shares × (entry − stop)`.
If `whole_shares = 0`, card shows "Capital too low" warning.

### Signal Payload Fields
Every fired signal returns:
```
ticker, signal_type, side ("BUY"), score, confidence_tier,
entry_price, target_price, stop_price, entry_refined (1-min adjusted, dip-class only),
shares (whole number), expected_profit_dollar, max_risk_dollar, risk_reward_ratio,
session_window, session_window_label,
intraday_vwap, rsi_5m, rvol, vix, dip_pct,
atr_5m, atr_adjusted,
time_stop_minutes (per signal_type),
signals[], signal_hints{}, top_reasons[] (filtered for simple view),
invalidation: { price_close_below, vix_above, rvol_resurge_above }
```
`invalidation` = structural thesis controls (different from stop-loss P&L control).
`price_close_below` = nearest support × 0.998. `vix_above` = current VIX × 1.10.

### Whitelist Scaffold
`WHITELIST_CELLS` in `dip_scanner.py` — set of `(ticker, session)` tuples with historically positive EV.
`ENABLE_WHITELIST = False` by default. Enable once n ≥ 5 resolved trades per cell. Current best cells from backtest: QQQ (all sessions), SPY morning_trend / morning_flush.

### Scenario Guidance System
`frontend/src/data/scenarios.json` — 30 hardcoded plain-English situation descriptions.
Each entry: `{ type, headline, summary, action, risk_note }`.
Types: `buy`, `no_buy`, `prep`, `sell`, `hold`, `neutral`.
`scenario_key` is returned by the backend scan endpoint and looked up by `SituationSummary`.

Scenarios covered: `waiting`, `market_closed`, `no_buy_vix_extreme`, `no_buy_still_falling`,
`no_buy_insufficient_dip`, `no_buy_rsi_not_oversold`, `no_buy_score_too_low`,
`no_buy_lunch_drift`, `no_buy_weekly_target_hit`, `buy_dip_at_support`, `buy_orb_breakout`,
`buy_vwap_reclaim`, `buy_vix_spike_fade`, `prep_vix_spike`, `prep_power_hour`,
`sell_target_reached`, `sell_eod_approaching`, `hold_recovering`, `hold_near_target`, and more.

### Database Model
See `docs/reference/architecture.md` SEC:DB_MODELS for the full `ScannerAlert` schema (includes `signal_type`, `five_min_direction`, `resolved_by`, etc.).

### Historical Backfill
`POST /dip-scanner/backfill` replays scanner logic over the last N days (default 60) of 5-min yfinance data. Outcomes simulated: target hit within session = "win", stop hit = "loss", EOD close = "win"/"loss" by sign of (close − entry). Backfill is **destructive** for backtest rows — clears existing `source = "backtest"` rows before re-seeding so re-runs always reflect the latest scoring logic.

Backtest rows are gated on the same score floor as live: `score ≥ 72`, plus `≥ 80` in `lunch_drift`. The gate lives inside the backtest's `_append` closure so it applies uniformly to all four signal types — without it, ORB/VWAP/Failed-Breakdown paths (which compute scores starting at 65 and don't route through `_score_etf`) would persist alerts the live scanner would have rejected, polluting the 60-day win-rate baseline.

### AI Signal Analysis (LLM, ~500 tokens, opt-in)
`POST /dip-scanner/analyze` is the only LLM-touching scanner path. Click-triggered from "What does this mean?" button in pro view; result clears on each new scan. Pulls last 30 closed signals for `(ticker, signal_type)` to build a structured prompt with historical win rate / avg win / avg loss, then returns `{ verdict (FAVORABLE/MIXED/UNFAVORABLE), plain_english, key_risk, watch_for }`. Falls back to a rule-based response if LLM call fails. Blocked in saver mode.

---

<!-- SEC:AUTO_PAPER_TRADE -->
## Auto-Paper-Trade Subscriber (Phase 3)

**Goal:** unbiased measurement of scanner profitability. Every signal in the allowlist becomes a paper bracket order so the resulting P&L reflects the strategy, not human selection bias. **Paper-only by design** — see `docs/trading.md` SEC:GOALS for why live trading is intentionally absent from the roadmap.

**Code:** `backend/app/services/trading/auto_trade.py` (subscriber + scanner halt + alert→order conversion); `backend/app/api/broker.py` GET `/broker/auto-trade/status` (status endpoint); `frontend/src/components/trading/AutoTradePanel.tsx` (UI banner).

### How it fires
The subscriber is registered unconditionally in the scheduler (so flipping the env flag doesn't require a job-graph change). On every tick (default 30 s):
1. **Self-skip gates:** `AUTO_TRADE_ENABLED=false`, empty `AUTO_TRADE_SIGNAL_TYPES` allowlist, broker unavailable, or outside US market hours (9:30–16:00 ET Mon–Fri) → return immediately, log nothing.
2. **Query open alerts** with `signal_type ∈ allowlist`, entry_time ≥ today midnight ET, and no existing `BrokerOrder.scanner_alert_id` linkage — bounded to 20 per tick (leftovers picked up next poll).
3. **Per alert**, build a bracket `PlaceOrderRequest`: `qty = floor(alert.capital_used / alert.entry_price)`, limit at entry, stop at alert.stop_price, take-profit at alert.target_price, TIF day, `client_order_id="auto-{alert.id}"` (idempotent — same alert can never fire twice).
4. **Run `check_order_caps`** (the SAME risk gate manual orders go through — single source of truth).
5. **Persist `BrokerOrder`** with `source="scanner_alert"` + `scanner_alert_id`, submit to broker, update row with broker response.
6. **Daily cap reached** (`daily_order_count_cap_reached` from check_order_caps) → break out of the per-alert loop; remaining alerts wait for tomorrow.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `AUTO_TRADE_ENABLED` | `false` | Master kill switch. `true` alone does NOT fire — allowlist must also be non-empty. |
| `AUTO_TRADE_SIGNAL_TYPES` | (empty) | Comma-separated allowlist, e.g. `orb_breakout,failed_breakdown`. Empty = no fires regardless of flag. |
| `AUTO_TRADE_POLL_SECONDS` | `30` | Subscriber tick rate. |
| `TRADE_DAILY_ORDER_COUNT_CAP` | `50` | Hard cap on orders per day (manual + auto combined). 51st rejected with 422. |
| `SCANNER_DAILY_SIGNAL_CAP` | `50` | Once today's `scanner_alerts` reach this, dip + MCF scanners halt for the day. |

### Linking back to the source signal
`BrokerOrder.scanner_alert_id` is the foreign key. `eod_dump.py` joins through it to surface per-fill slippage (`filled_avg_price - alert.entry_price`), coverage gap (alerts that didn't produce orders — auto off, not in allowlist, or risk-cap rejected), and per-signal-type fill rate. See `local_debugging/eod_dump.py` `_build_trading_report`.

### Manual + auto coexist
Manual orders through `POST /broker/orders` keep working unchanged. The subscriber only adds *additional* order flow; it never displaces or rate-limits manual entries. Both paths share the same risk caps and `BrokerOrder` table. The `source` column (`"manual"` vs `"scanner_alert"`) distinguishes them.

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

<!-- SEC:TELEGRAM -->
## Telegram bot

**Sprint 1 (outbound) + Sprint 2 (inbound commands + multi-user) — both shipped.**

### Files
| File | Role |
|---|---|
| `backend/app/services/notifier.py` | Async Telegram client — broadcast to all active DB users |
| `backend/app/services/telegram_handler.py` | Long-poll loop + command router + registration |
| `backend/app/db/models.py` | `TelegramUser` model |
| `backend/migrations/versions/c3d4e5f6a7b8_create_telegram_users.py` | Migration |
| `backend/app/main.py` | `start_polling()` / `stop_polling()` in lifespan |

### Environment variables
| Var | Where | Default | Notes |
|---|---|---|---|
| `TELEGRAM_ENABLED` | `.env.shared` | `false` | Master switch — flip to `true` to activate |
| `TELEGRAM_POLL_INTERVAL` | `.env.shared` | `5` | Seconds between getUpdates polls |
| `TELEGRAM_BOT_TOKEN` | `.env` (secret) | — | From @BotFather |
| `TELEGRAM_CHAT_ID` | `.env` (secret) | — | Owner chat_id — auto-admin on first /start |
| `TELEGRAM_INVITE_CODE` | `.env` (secret) | — | Share privately; anyone with it can register |

### One-time setup
1. Telegram → @BotFather → `/newbot` → copy token → `TELEGRAM_BOT_TOKEN` in `.env`
2. Telegram → @userinfobot → copy `Id:` number → `TELEGRAM_CHAT_ID` in `.env`
3. Set a secret `TELEGRAM_INVITE_CODE` in `.env` (e.g. `srp-2026-abc`)
4. Set `TELEGRAM_ENABLED=true` in `.env.shared` and restart backend
5. Send `/start srp-2026-abc` to your bot — you're registered as admin

### Inviting other users
Share the bot username (`@stockresearchpro_bot`) + the invite code privately.
They send `/start <code>` → registered, get all broadcasts. You see them via `/users`.

### Multi-user model
`telegram_users` table stores all registered users. `notifier.py` queries active users
and sends to all. Owner's `TELEGRAM_CHAT_ID` auto-gets `is_admin=True` on registration.

### notifier.py public API
```python
send_text(text)                                              # raw HTML message
send_scanner_alert(alert: ScannerAlert)                      # MCF / dip signal card
send_watchlist_alert(ticker, signal, score, price, change_7d) # watchlist eval signal
send_daily_report(signals_today, wins, losses, open_count, near_misses)
send_pre_market_digest(vix, spy_bias, watchlist_count, top_tickers)
```
All functions are async. All return `bool` (ok/fail). Never raise — failures log at WARNING.
If `TELEGRAM_ENABLED=false` or token/chat_id are blank, all calls silently return `False`.

### Where notifications fire
| Event | Trigger point | Function called |
|---|---|---|
| MCF scanner alert | `scheduler.py _run_mcf_scan` after db.commit | `send_scanner_alert` |
| Watchlist strong signal | `alert_engine.py evaluate_watchlist` after db.add | `send_watchlist_alert` |
| EOD summary | `scheduler.py _run_eod_dump` after subprocess exits | `send_daily_report` |
| Pre-market brief | `scheduler.py _run_pre_market_digest` at 9:00 AM ET | `send_pre_market_digest` |

### Scheduled jobs (Telegram-related)
| Job | Time | What sends |
|---|---|---|
| `pre_market_digest` | Mon–Fri 9:00 AM ET | VIX + SPY bias + watchlist tickers |
| `eod_dump` (extended) | Mon–Fri 4:35 PM ET | EOD summary: signals, wins/losses, win rate |

### Message formats
**Scanner signal:**
```
🟢 MCF DIP BUY — NVDA   Score: 90
Entry $875.00 | Stop $868.00 | Target $884.00
R/R: 1:1.3 | Gate: STRICT ✓
```
Loose-gate alerts use 🟡 and show `Gate: LOOSE ⚠`.

**Watchlist signal:**
```
🟢 WATCHLIST — AAPL   Score: 74
Signal: Buy now
Price: $182.40 | 7d: ▼5.2%
```

**EOD summary:**
```
📊 EOD Summary — May 17
Signals fired: 3  (1 still open)
Wins: 1 | Losses: 1 | Win rate: 50%
Near misses: 0
```

**Pre-market brief:**
```
☀️ Pre-Market Brief
VIX: 14.3 | Market bias: Bullish ▲
Watchlist: 5 active tickers
Watching: AAPL, NVDA, TSLA, META, MSFT
```

Frontend: `AlertToast` component + Zustand `alerts[]`. Persistent connection in `App.tsx` survives page navigation.
