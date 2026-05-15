# Daily Target Trade Scanner — Sprint Plan
# Created: 2026-05-08  Branch: feature/daily-target-scanner

---

## What we are building

A **Daily Target Trade Scanner** feature that monitors a curated list of broad-market ETFs
throughout the trading day and alerts the user when a high-probability intraday dip-buy
opportunity arises. The user's goal is one clean trade per day targeting $10–$200 profit
(configurable capital, default $1,000) by buying a dip and selling the recovery within
the same session.

The feature has three sub-systems:
1. **Scanner engine** — runs every 5 min during market hours, scores each ETF, fires an
   alert when score ≥ 65
2. **Analytics tracker** — records every alert fired (live and backtest), checks price
   outcomes automatically, builds a win/loss track record
3. **Performance dashboard** — shows win rate, expected value per trade, cumulative P&L
   chart, breakdown by ETF and session window

---

## User story

> "I want the app to tell me once per day: 'Now is a good time to buy QQQ — here is why,
> here is your entry, target, and stop, and here is how often setups like this have worked.'
> I do not want the app making LLM calls while it runs in the background all day."

---

## Architecture

### Two operating modes

| Mode | How it works |
|------|--------------|
| **Background (passive)** | APScheduler job every 5 min, 9:40 AM–3:15 PM ET. Fires WebSocket toast when score ≥ 65. No user interaction needed. |
| **Manual (active)** | "Scan Now" button on the DipScannerCard. Returns instant result. |

### Cache-first data fetching

The scanner calls `get_stock_cache(db, ticker, "price")` before fetching fresh data.
If a Tier 1 price fetch already happened within the last 15 min (from user searching the
same ETF), that data is reused at zero API cost.
Cache service: `backend/app/services/data_cache.py` — `get_stock_cache()` / `set_stock_cache()`.

### Zero LLM in background

The scanner's scoring logic is pure Python computation — no LLM calls ever for
background scanning. The only optional LLM call is the "Explain this setup" button
(user-triggered, ~200 tokens, disabled in saver mode).

---

## ETF whitelist (tiered)

### Tier 1 — Default, always scanned

| Ticker | Tracks | Avg daily volume | Why safe |
|--------|--------|-----------------|----------|
| SPY | S&P 500 | ~80M shares | Most liquid instrument on Earth |
| QQQ | Nasdaq 100 | ~40M shares | Tracks 100 largest tech companies |
| IWM | Russell 2000 | ~25M shares | Broad small-cap index |
| DIA | Dow Jones | ~5M shares | Blue-chip, slow and predictable |

### Tier 2 — Optional, user enables

| Ticker | Tracks | Caveat |
|--------|--------|--------|
| XLK | Tech sector | Follows QQQ closely |
| XLF | Financials | Rate-sensitive |
| XLV | Healthcare | Defensive, low drama |
| GLD | Gold | Safe haven, uncorrelated |

### Hard-excluded (never scanned)
- Leveraged: TQQQ, SQQQ, UPRO, SPXU, SPXL
- Inverse: SH, PSQ, DOG
- Crypto: BITO, IBIT
- Speculative thematic: ARKK, ARKW

---

## Signal scoring formula

Starts at 50 (neutral), applies signed deltas. Alert fires at score ≥ 65.

```
score = 50

# Support proximity (how close is price to a known support level)
if price within 0.2% of S1/S2/VWAP/VAL:   score += 15
elif price within 0.4% of S1/S2/VWAP/VAL: score += 10
elif price within 0.7%:                     score += 5
else:                                        score -= 5

# Intraday RSI (computed from 5-min candle closes — no extra API call)
if rsi_5m < 30:   score += 15
elif rsi_5m < 35: score += 12
elif rsi_5m < 42: score += 8
elif rsi_5m > 60: score -= 10

# RVOL — elevated but declining = exhaustion signal
if rvol > 1.5 and rvol_declining:  score += 10
elif rvol > 1.0 and rvol_declining: score += 6
elif rvol_still_climbing:           score -= 15   # do NOT catch falling knife

# Price vs intraday VWAP (computed from 5-min candles — no extra API call)
if price < intraday_vwap:           score += 10
elif price > intraday_vwap * 1.005: score -= 5

# Candle pattern on last 5-min bar
if hammer_candle:                   score += 15   # (close-low)/(high-low) > 0.6
elif bullish_engulfing:             score += 12

# VIX context (daily VIX close)
if 20 <= vix <= 35:  score += 10   # elevated = better mean reversion opportunity
elif vix < 14:       score += 2    # calm = small bounce expected
elif vix > 35:       score -= 10   # extreme = skip, dips extend for days

# Session window
if 14:00 <= time <= 15:15:           score += 10   # Power Hour — best window
elif 9:40 <= time <= 10:30:          score += 5    # Morning Flush
elif 12:00 <= time <= 13:30:         score -= 5    # Lunch Drift — weakest
```

### Intraday VWAP computation (from existing data, 0 extra calls)
```python
vwap = sum(c["close"] * c["volume"] for c in candles) / sum(c["volume"] for c in candles)
```

### Intraday RSI-14 computation (from existing data, 0 extra calls)
Use pandas or manual rolling calculation on the "close" series from `intraday_history`.

### Hammer candle detection (from existing data, 0 extra calls)
```python
candle_range = high - low
lower_wick = close - low
upper_wick = high - close
is_hammer = (lower_wick / candle_range > 0.6) and (upper_wick < lower_wick * 0.3)
```

---

## VIX as entry modifier (not a blocker)

| VIX range | Market state | Entry requires |
|-----------|-------------|----------------|
| < 18 | Calm | Dip ≥ 0.3%, RSI < 42 |
| 18–25 | Moderate vol | Dip ≥ 0.6%, RSI < 38, RVOL > 1.2× |
| 25–35 | High vol | Dip ≥ 1.0%, RSI < 33, RVOL > 1.5× — **better mean reversion** |
| > 35 | Extreme crash | Skip — dips extend for days, not hours |

VIX 20–35 days are the BEST opportunities, not days to avoid.

---

## Session windows

Each alert is labeled with the session window it fired in:

| Window | Hours (ET) | Character |
|--------|-----------|-----------|
| Morning Flush | 9:40–10:30 AM | Biggest dips, highest volatility, wider stops needed |
| Morning Trend | 10:30 AM–12 PM | Direction set, mean reversion less reliable |
| Lunch Drift | 12–2 PM | Low volume, slow moves — small targets only |
| Power Hour | 2–3:15 PM | Best R:R — institutional order flow resumes |

---

## Alert payload (WebSocket broadcast)

```json
{
  "type": "dip_buy_alert",
  "ticker": "QQQ",
  "entry_price": 442.50,
  "target_price": 446.93,
  "stop_price": 440.28,
  "expected_profit_dollar": 10.35,
  "max_risk_dollar": 4.43,
  "risk_reward_ratio": 2.3,
  "capital_used": 1000,
  "score": 78,
  "session_window": "power_hour",
  "signals": ["Below VWAP", "Near S1 (442.10)", "RSI 36", "RVOL 1.4x declining", "Hammer candle"],
  "vix": 19.4,
  "title": "QQQ Dip Buy — Entry Zone",
  "body": "QQQ near S1 support, RSI oversold on 5-min, sellers showing exhaustion",
  "timestamp": "2026-05-08T14:22:00"
}
```

---

## Educational hints (hardcoded, 0 tokens, always shown)

Each signal in the card has an inline [?] tooltip:

| Signal | Hint |
|--------|------|
| Below VWAP | "Price is below today's volume-weighted average — institutions typically buy back above this level, making recovery likely" |
| Near S1 pivot | "S1 is yesterday's support projected into today — price often bounces here because traders expect it to" |
| RSI < 35 (5-min) | "Short-term sellers may be exhausted — price often snaps back from these oversold levels" |
| RVOL declining | "Volume surged then pulled back — a classic sign the selling wave is ending" |
| Hammer candle | "Long lower wick = buyers pushed back hard after the dip — the market rejected lower prices in real time" |
| Power Hour | "2–3:15 PM is when institutions close positions — volume and direction tend to be more decisive" |
| VIX 20–35 | "Elevated volatility means bigger swings both ways — entry criteria tightened, but recovery bounce is larger" |

**Optional LLM "Explain this setup" button** (~200 tokens):
- Disabled in saver mode
- Generates a plain-English paragraph about why this specific setup looks like an opportunity
- Uses existing Tier 2 call pattern

---

## Capital input

- localStorage key: `dts_capital` (separate from PositionSizer's `ps_account_size`)
- Default: `$1,000`
- User can modify any time — all P&L math recalculates live
- Persists across sessions

---

## Analytics & outcome tracking

### ScannerAlert DB model (new table)

```python
class ScannerAlert(Base):
    __tablename__ = "scanner_alerts"

    id            = Column(UUID, primary_key=True, default=uuid4)
    ticker        = Column(String, nullable=False)
    entry_price   = Column(Float, nullable=False)
    target_price  = Column(Float, nullable=False)
    stop_price    = Column(Float, nullable=False)
    entry_time    = Column(DateTime(timezone=True), nullable=False)
    score         = Column(Integer)
    signals       = Column(JSON)                    # list of signal strings
    session_window= Column(String)                  # power_hour / morning_flush / etc
    vix_at_entry  = Column(Float)
    capital_used  = Column(Float, default=1000.0)

    # Outcome (filled by background tracker)
    source        = Column(String, default="live")  # "live" or "backtest"
    status        = Column(String, default="open")  # open / win / loss / expired
    outcome_price = Column(Float, nullable=True)
    outcome_time  = Column(DateTime(timezone=True), nullable=True)
    actual_pnl_pct= Column(Float, nullable=True)
    actual_pnl_dollar = Column(Float, nullable=True)
    resolved_by   = Column(String, nullable=True)   # target_hit / stop_hit / eod_close
```

### Outcome tracking (added to existing 5-min APScheduler job)

Every 5 min, for each alert with status="open":
```
Fetch current price for ticker
If price >= target_price  → status="win",  resolved_by="target_hit"
If price <= stop_price    → status="loss", resolved_by="stop_hit"
If time >= 15:45 ET       → resolve at current price, resolved_by="eod_close"
                            win if current > entry, loss if current < entry
```

### Historical backfill (run once at setup)

- `POST /dip-scanner/backfill` — one-time endpoint
- Fetches 60 days of 5-min data for each Tier 1 ETF (yfinance allows this for free)
- Replays the scanner logic day-by-day, bar-by-bar
- Records would-have alerts with `source="backtest"`
- Immediately populates analytics with ~60 days of signal history
- Run once; never re-runs (checks if backtest records already exist)

### Analytics API response

`GET /dip-scanner/analytics`

```json
{
  "total_signals": 847,
  "wins": 601,
  "losses": 246,
  "win_rate_pct": 71.0,
  "avg_win_pct": 0.91,
  "avg_loss_pct": -0.48,
  "expected_value_pct": 0.50,
  "expected_value_dollar": 5.00,
  "current_streak": { "type": "win", "count": 4 },
  "data_note": "Includes 60-day backtest + live signals",
  "by_ticker": {
    "SPY": { "signals": 312, "win_rate_pct": 74.0, "ev_dollar": 5.80 },
    "QQQ": { "signals": 298, "win_rate_pct": 72.0, "ev_dollar": 5.40 },
    "IWM": { "signals": 237, "win_rate_pct": 64.0, "ev_dollar": 3.90 }
  },
  "by_window": {
    "power_hour":    { "signals": 210, "win_rate_pct": 80.0 },
    "morning_flush": { "signals": 198, "win_rate_pct": 68.0 },
    "morning_trend": { "signals": 241, "win_rate_pct": 66.0 },
    "lunch_drift":   { "signals": 198, "win_rate_pct": 57.0 }
  },
  "recent_alerts": [
    {
      "ticker": "QQQ", "entry_time": "2026-05-08T14:22:00",
      "actual_pnl_pct": 0.94, "actual_pnl_dollar": 9.40,
      "status": "win", "resolved_by": "target_hit",
      "session_window": "power_hour", "source": "live"
    }
  ]
}
```

---

## Frontend UI

### DipScannerCard.tsx (new component — Dashboard page)

```
┌─────────────────────────────────────────────────────┐
│  Daily Target Trade              [Scan Now]          │
│  Capital: [ $1,000 ]   Tier: [●Tier 1  ○Tier 1+2]  │
│                                                      │
│  ● QQQ  Score: 78/100  ▲ Entry zone                 │
│    Entry $442.50 → Target $446.93 → Stop $440.28   │
│    Profit: +$10.35  |  Risk: -$4.43  |  R:R: 2.3:1 │
│    Window: Power Hour (2–3:15 PM)                   │
│                                                      │
│    Signals:  Below VWAP [?]  ·  Near S1 [?]        │
│              RSI 36 [?]  ·  RVOL 1.4x↓ [?]         │
│              Hammer candle [?]                      │
│                                                      │
│    [Explain this setup]  (uses ~200 tokens)         │
└─────────────────────────────────────────────────────┘
```

### ScannerPerformanceCard.tsx (new component — Dashboard page)

```
┌─────────────────────────────────────────────────────────┐
│  Scanner Performance            ● Backtest  ● Live      │
│                                                         │
│   71%          +$5.00          847 signals              │
│  Win Rate    Avg EV/trade       evaluated               │
│  601W / 246L                                            │
│                                                         │
│  [Cumulative P&L line chart — 60 days populated]       │
│                                                         │
│  By ETF        Signals  Win Rate  Avg EV               │
│  SPY             312      74%     +$5.80                │
│  QQQ             298      72%     +$5.40                │
│  IWM             237      64%     +$3.90                │
│                                                         │
│  By Session    Win Rate                                 │
│  Power Hour      80%  ████████                         │
│  Morning Flush   68%  ██████▌                          │
│  Lunch Drift     57%  █████▋                           │
│                                                         │
│  Recent                                                 │
│  ✓ QQQ  May 8  2:22 PM  +0.94%  +$9.40  [LIVE]       │
│  ✓ SPY  May 7  2:11 PM  +0.81%  +$8.10  [LIVE]       │
│  ✗ IWM  Apr 18 11:15AM  −0.50%  −$5.00  [BACKTEST]   │
└─────────────────────────────────────────────────────────┘
```

### AlertToast.tsx update

Add gold/amber styling for `dip_buy_alert` type:
```typescript
case "dip_buy_alert":
  borderColor = "border-yellow-400"
  icon = "📈"
  break
```

---

## Files to create / modify

| File | Action | What |
|------|--------|------|
| `backend/app/tools/dip_scanner.py` | **CREATE** | Scanner logic: intraday VWAP/RSI, candle detection, VIX-adjusted scoring, backfill function |
| `backend/app/api/dip_scanner.py` | **CREATE** | POST /dip-scanner/scan, GET /dip-scanner/analytics, POST /dip-scanner/backfill, GET /dip-scanner/config |
| `backend/app/db/models.py` | **EDIT** | Add ScannerAlert model |
| `backend/app/services/scheduler.py` | **EDIT** | Add 5-min scan job + outcome tracking job (market hours only) |
| `backend/app/main.py` | **EDIT** | Register dip_scanner router |
| `frontend/src/components/DipScannerCard.tsx` | **CREATE** | Scanner UI: capital input, score, signals, hints, session window, explain button |
| `frontend/src/components/ScannerPerformanceCard.tsx` | **CREATE** | Analytics: win rate, EV, cumulative chart, ETF/window breakdown, recent alerts |
| `frontend/src/pages/DashboardPage.tsx` | **EDIT** | Add DipScannerCard + ScannerPerformanceCard sections |
| `frontend/src/components/shared/AlertToast.tsx` | **EDIT** | Add gold styling for dip_buy_alert type |
| Alembic migration | **CREATE** | scanner_alerts table |

Total: 4 new files, 6 edits.

---

## Saver mode compatibility

The dip scanner background job is 0 LLM by design — pure Python computation.
It runs safely all day with no token cost regardless of exec_mode.

The "Explain this setup" button must check exec_mode before firing:
- saver mode → button disabled, show "Enable Normal mode for LLM explanations"
- normal / deep → button active

The backend Tier 2/3 endpoints do NOT enforce exec_mode server-side (they trust
the frontend to gate calls). The dip scanner should enforce this on its own
"explain" call within `DipScannerCard.tsx` using the Zustand `execMode` state.

The APScheduler background jobs run independent of exec_mode — this is by design
for the scanner (0 LLM = safe) but worth noting for existing watchlist/screener
jobs that may trigger LLM tools.

---

## Branch and PR plan

Branch: `feature/daily-target-scanner`
PR into: `main`

Commit order:
1. DB model + migration (scanner_alerts table)
2. dip_scanner.py tool (core logic)
3. dip_scanner.py API (endpoints)
4. scheduler.py jobs (scan + outcome tracker)
5. main.py router registration
6. Frontend components (DipScannerCard, ScannerPerformanceCard)
7. DashboardPage integration + AlertToast update

---

## Open questions / decisions already made

| Question | Decision |
|----------|----------|
| Capital default | $1,000 (user confirmed) |
| localStorage key | `dts_capital` (separate from `ps_account_size`) |
| VIX treatment | Modifier, not blocker — higher VIX = tighter criteria, not skip |
| Morning gate | 9:40 AM only (not 9:45) — user confirmed morning dips are valid |
| Alert threshold | Score ≥ 65 |
| Backfill data | 60 days of 5-min yfinance data (free, available) |
| Backtest label | Show "BACKTEST" vs "LIVE" label in recent alerts — transparency |
| Min sample for win rate | Show "Gathering data" until 30+ signals — avoid misleading 100% from 2 trades |
| Outcome resolution at EOD | 3:45 PM ET — compare final price vs entry price |
