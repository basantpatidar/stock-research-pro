**Doc version:** 1.0 · **Last updated:** 2026-05-18

# Stock Research Pro — Active TODO

Tracks only work NOT yet built. Completed sprints live in `local_debugging/push_plan.md`
(Historical PR reference) and `CLAUDE.md` (Recent Changes). Each item ships as its own
branch + PR — one sprint per PR.

---

## Recently Confirmed Done (cleared this session)

The following items appeared in the old outstanding list but are already shipped:

- ✅ V2 new tools wired into `graph.py` ALL_TOOLS (investor_personas, bull_bear, congressional, backtester, transcript, paper_trade)
- ✅ `pytrends` in `requirements.txt`
- ✅ Portfolio risk page / PortfolioRiskPanel (Phase 3 sprint)
- ✅ Frontend live usage pills in top nav (Phase 3 sprint)
- ✅ Screener universe expanded 30 → 142 tickers (`universe.py`)
- ✅ Paper trade journal persistence — superseded by broker integration (TRADE-1/2/3)

---

## Active Sprint Queue

Ordered by recommended build sequence. High-risk scanner changes ship Sunday night
(paper positions flat). Each = own branch + PR.

| # | Sprint | Branch | Risk | Notes |
|---|---|---|---|---|
| 1 | **Sentiment Divergence Signal** — new tool that detects when price momentum diverges from social/options sentiment. Research panel only — NOT in `AUTO_TRADE_SIGNAL_TYPES`. | `feat/sentiment-divergence` | Low | New tool, no existing logic touched |
| 2 | **WAIT / READY / ENTER NOW three-state CTA** (Opus #15) — scanner card shows actionable state based on score + regime + time-of-day rather than a flat alert. | `feat/scanner-cta-state` | Low | Frontend display state only |
| 3 | **ATR-normalised thresholds** (Opus #1) — replace fixed % entry thresholds with ATR multiples so volatile and low-vol tickers are treated consistently. | `feat/scanner-atr-thresholds` | High | Changes signal firing logic — build during market hours, verify signals fire before push |
| 4 | **Market regime gate** (Opus #2) — block `dip_buy` signals when overall market is in a downtrend (`SPY` slope + IWM breadth). | `feat/scanner-regime-gate` | High | Changes signal filtering — ship after #3 stabilises |
| 5 | **ATR-based dynamic stops/targets** (Opus #11) — replace fixed ATR multipliers with per-signal-type calibrated values from backtest win rate data. | `feat/scanner-atr-stops` | Medium | Changes exit behaviour — ship when paper positions are flat (Sunday night) |

---

## Feature Backlog

### Architecture / Auth

- [ ] **Full JWT auth** — replace API key in `auth.py` with JWT. File is already structured for a drop-in swap (`verify_api_key()` body only). No other files change.
- [ ] **Email alerts** — `notifier.py` is stubbed for SendGrid/SES. Wire `send_email()` into `alert_engine.py` alongside Telegram. Env: `SENDGRID_API_KEY` + `ALERT_EMAIL`.

### Day Trading — Research

- [ ] **Multi-Timeframe Confluence Score** (Sprint 5) — RSI/MACD/VWAP across 5m/15m/1h/daily simultaneously. New `technicals_mtf.py` tool + `MultiTimeframePanel.tsx` Tier 2 panel. 0 tokens.
- [ ] **RVOL Signal** (Sprint 5) — time-normalised relative volume (current vol ÷ same-time-of-day 10d avg). Add to `price.py` or `technicals.py`. 0 tokens.
- [ ] **GARCH Volatility Forecast** (Sprint 15) — expected daily range next 1–5 days via GARCH(1,1). New `volatility_forecast.py`. Dep: `pip install arch`. 0 tokens.
- [ ] **Momentum Regime Classifier** (Sprint 15) — HMM to label trending vs mean-reverting regime on recent price action. New `regime.py`. Dep: `pip install hmmlearn scikit-learn`. 0 tokens.

### Long-Term Investing — Research

- [ ] **DCF + Intrinsic Value Calculator** (Sprint 6) — auto-DCF from yfinance FCF, revenue CAGR, adjustable discount rate. Bear/base/bull scenarios + Graham Number + PEG fair value. New `valuation.py` + `ValuationPanel.tsx` Tier 2. 0 tokens.
- [ ] **Peer Comparable Valuation** (Sprint 6) — 5 sector peers from yfinance, P/E / P/S / EV/EBITDA / P/FCF / PEG table, premium/discount vs peer median. Add to `valuation.py`. 0 tokens.
- [ ] **SEC EDGAR 8-Year Fundamentals** (Sprint 10) — XBRL from `data.sec.gov` (free, no key). Revenue, net income, operating margin, FCF, debt/equity trend charts. New `edgar_fundamentals.py` + `EDGARFundamentalsPanel.tsx`. 0 tokens.

### Data / Intelligence

- [ ] **Crypto correlation tracker** — BTC/ETH price correlation vs tech/growth stocks. Surface when crypto risk-off is dragging the sector.
- [ ] **Dark pool FINRA data** — FINRA ATS off-exchange volume data. Surface when dark pool activity diverges significantly from lit volume.

---

## Parked / Blocked

| Item | Blocker |
|---|---|
| Opus #27 — WHITELIST_CELLS auto-entry | Needs n ≥ 50 resolved paper trades per cell; accumulating via auto-paper-trade. Re-evaluate after 2–3 weeks of live paper trading. |
| Opus #26 — 1-min granularity for entry timing | 6+ h fundamental data-pipeline change. Own sprint, later. |
| Live broker trading | Code path exists (`BROKER_MODE=live`) but not planned. Explicit user decision required. Never proactively scheduled. |
