# Stock Research Pro — Feature Roadmap
# Navigation: grep -n "SEC:" plan.md → read with offset+limit
# SEC:DECISIONS      Locked-in architectural decisions (read this first)
# SEC:CACHING        Per-data TTL strategy (LLM + non-LLM)
# SEC:UI_PAGES       Page layout and where features live
# SEC:STATUS         What is already built
# SEC:PRIORITY       Recommended sprint order (day trading first)
# SEC:DAY_TRADING    Day trading feature backlog
# SEC:LONG_TERM      Long-term investing feature backlog
# SEC:BOTH           Features serving both audiences
# SEC:ALGO           Algorithmic / ML approaches
# SEC:DATA_SOURCES   Free data sources available to tap
# SEC:PARKED         Features parked (waiting on Reddit API access)
# SEC:PAID_LATER     Features needing paid APIs — defer

---

<!-- SEC:DECISIONS -->
## Locked-In Architectural Decisions
*Agreed 2026-05-02. Do not re-discuss — implement as specified.*

| # | Decision | Detail |
|---|---|---|
| 1 | **Day trading prioritized over long-term** | All day-trading features built first. Long-term block starts at sprint 16. |
| 2 | **New Dashboard page** | Add `/dashboard` as the day trader morning starting point: market pulse, pre-market movers from watchlist, economic calendar. Separate from ResearchPage. |
| 3 | **Mode-aware ResearchPage** | Switching Day Trade / Long Term / Both changes which panels are shown and their order. Day Trade hides DCF/Dividend/Moat; Long Term hides ORB/MTF/Pre-trade score. Fix this before new features land. |
| 4 | **Per-data TTL caching** | Every tool gets its own TTL matching how often that data actually changes. See SEC:CACHING. Applies to ALL tool calls, not just LLM. |
| 5 | **DB-backed cache for slow-changing data** | Quarterly/weekly data stored in StockDataCache DB table (survives restarts). Redis-only for real-time data (price, technicals). |
| 6 | **Reddit features parked** | Any feature requiring Reddit PRAW is parked until API access is confirmed. See SEC:PARKED. |
| 7 | **API setup instructions in code** | Every optional API key gets a comment in `.env.example` with the exact URL to get it and step-by-step. Also documented in `docs/dev.md` SEC:ENV_VARS. |
| 8 | **One branch + PR per sprint** | Branch naming: `feat/sprint-N-short-description`. Always merge before starting next sprint. |
| 9 | **plan.md auto-updated** | After every sprint completes, update SEC:STATUS (mark built) and SEC:PRIORITY (mark done). Claude does this without being asked. |

---

<!-- SEC:CACHING -->
## Per-Data TTL Caching Strategy

**Rule:** TTL = how long the data stays meaningfully accurate. Not a fixed global value.
**Storage:** Redis for real-time (< 1 day). StockDataCache DB table for anything ≥ 1 day (survives restarts).

### Non-LLM Tool Data

| Tool | Data changes | TTL | Storage |
|---|---|---|---|
| `get_price` (OHLCV, intraday) | Real-time | 15 min | Redis |
| `get_technicals` (RSI, MACD, VWAP) | Each candle | 15 min | Redis |
| `get_analyst_consensus` | Weekly/sporadic | 24 hours | DB |
| `get_earnings` (history + next date) | Quarterly | Until `next_earnings_date` | DB |
| `get_fundamentals` (P/E, margins, FCF) | Quarterly | 30 days | DB |
| `get_short_interest` | Bi-weekly (FINRA) | 7 days | DB |
| `get_congressional_trades` | As filed (sporadic) | 24 hours | DB |
| `get_insider_activity` | As filed (sporadic) | 24 hours | DB |
| `get_institutional_changes` (13F) | Quarterly | 30 days | DB |
| `get_sector_heatmap` | Daily | 1 hour | Redis |
| `get_macro_environment` | Daily | 1 hour | Redis |
| `get_fred_macro` | Weekly/monthly | 24 hours | DB |
| `get_options_intelligence` | Intraday | 30 min | Redis |
| `get_earnings_quality` (Piotroski etc.) | Quarterly | 30 days | DB |
| Volume profile (in `get_price`) | Daily | 6 hours | Redis |
| `get_news_impact` | Hourly | 30 min | Redis |

### LLM Tool Data

| Tool | TTL | Logic |
|---|---|---|
| `get_convergence_score` | 30 min | Changes with price |
| `get_price_forecast` | 24 hours | Daily reassessment enough |
| `get_risk_reward` | 30 min | Changes with price |
| `get_sentiment` | 30 min | Changes with price/news |
| `investor_personas` | 7 days | Thesis changes slowly |
| `bull_bear_debate` | 24 hours | Can shift on news |
| `analyze_earnings_transcript` | Until `next_earnings_date` | Transcript is static per quarter |
| `run_backtest` | 7 days | Historical data stable |
| `analyze_paper_trade` | 1 hour | Active trades need fresh data |
| `get_cascade_impact` | 24 hours | Event chain evolves slowly |

### Implementation
- `backend/app/services/usage/limits.py` → add `CACHE_TTL_PER_TOOL: dict` mapping tool name → seconds
- `data_cache.py` → use tool name to look up TTL instead of one global value
- For `get_earnings`: set `expires_at = next_earnings_date` from T1 response when available
- For `analyze_earnings_transcript`: same — expires at next earnings date

---

<!-- SEC:UI_PAGES -->
## Page Layout — Where Features Live

### Current pages
`/` Research | `/watchlist` Watchlist | `/screener` Screener | `/macro` Macro | `/usage` Usage

### New page: `/dashboard` — Day Trading Dashboard
The day trader's morning starting point. Opens to this page by default when mode = day_trade.

**Section 1 — Market Pulse (T1, auto-loads)**
- Fear & Greed gauge (Alternative.me, no key)
- VIX level + trend
- S&P 500 trend (above/below 50MA)
- Market breadth: % of S&P 500 stocks above 50MA / 200MA
- Sector leaders/laggards (top 3 up, top 3 down from existing heatmap)
- Macro regime label (from FRED data already fetched)

**Section 2 — Pre-Market Movers (from watchlist)**
- Tickers from watchlist gapping >2% pre-market
- Shows: ticker, gap %, gap type, RVOL, float tier, catalyst tag
- "No movers" state when market not pre-market or nothing gapping

**Section 3 — Economic Calendar (next 7 days)**
- Fed meetings, CPI, NFP from FRED release calendar
- Any watchlist ticker's next earnings date
- High/Medium/Low impact tags

### Updated: ResearchPage — Mode-Aware Panels

**Day Trade mode shows:**
- T1: Price chart (1d default, ORB lines, RVOL badge), Pre-trade scorecard, MTF confluence, Technicals, Short interest + squeeze score, Options Intelligence
- T2: Float/Squeeze detail, Volatility Forecast, Risk/Reward, News, Sentiment
- T3: Backtester, Bull/Bear, Paper Trade
- Hidden: DCF, Peer comps, Dividend health, Moat, EDGAR fundamentals

**Long Term mode shows:**
- T1: Price chart (3M default), Analyst consensus, Earnings history, Fundamentals, Earnings Quality, Congressional
- T2: Valuation (DCF + Graham + Peer comps), EDGAR 8-year trends, Convergence score, News, Sentiment
- T3: Investor Personas, Earnings Transcript, CANSLIM, Dividend health, Moat
- Hidden: ORB levels, MTF confluence, Pre-trade scorecard, RVOL, Float/Squeeze

**Both mode:** All panels shown, day trading panels first.

### Updated: WatchlistPage
- Add heatmap toggle (grid view vs table view)
- Pre-market movers banner at top (same data as Dashboard, condensed)

### Updated: MacroPage
- Existing: sector heatmap, geo events, FRED dashboard
- Add: Fear & Greed gauge, Market breadth section

### No changes: ScreenerPage, UsagePage

---

<!-- SEC:STATUS -->
## What Is Already Built

| Feature | Tier | Tokens | Notes |
|---|---|---|---|
| Price + OHLCV + volume ratio | T1 | 0 | yfinance |
| Volume Profile (VPOC/VAH/VAL) | T1 | 0 | On price chart, multi-day only |
| True 1d intraday chart (5-min + pre/post) | T1 | 0 | yfinance |
| RSI, MACD, Bollinger, VWAP, 50/200 MA | T1 | 0 | yfinance |
| Analyst consensus + price target | T1 | 0 | yfinance |
| Earnings history (beat/miss, EPS est vs actual, revenue) | T1 | 0 | yfinance |
| Fundamentals (P/E, margins, debt/equity, FCF) | T1 | 0 | yfinance |
| Short interest + squeeze potential | T1 | 0 | yfinance |
| Congressional trades (STOCK Act) | T1 | 0 | yfinance |
| Macro environment (VIX, S&P, oil, yields) | T1 | 0 | yfinance |
| Sector heatmap (11 sectors, 5d) | T1 | 0 | yfinance |
| FRED Dashboard (credit spreads, yield curves, M2) | T1 | 0 | FRED API |
| Earnings Quality (Piotroski, Beneish, Altman, Accruals) | T2 | 0 | Pure math |
| Options Intelligence (GEX, max pain, IV, skew, term structure) | T2 | 0 | Pure math |
| News + sentiment analysis | T2 | ~600 | NewsAPI + LLM |
| Reddit/StockTwits sentiment | T2 | ~500 | PRAW + LLM |
| Signal convergence score (0–100) | T2 | ~700 | All signals |
| Price forecast | T2 | ~800 | LLM |
| Risk/reward ratio | T2 | ~500 | yfinance |
| Investor personas (Buffett/Graham/Burry/Lynch/Wood) | T3 | ~5000 | LLM |
| Bull vs Bear debate + judge verdict | T3 | ~6000 | LLM |
| Earnings transcript analysis | T3 | ~4000 | LLM |
| Backtester (RSI/MACD/Golden cross) | T3 | 0 | Pure pandas |
| Paper trade journal + AI coaching | T3 | ~800 | LLM |

---

<!-- SEC:PRIORITY -->
## Recommended Sprint Order
*Day trading prioritized. ✅ = done. 🔴 = parked (Reddit). Last updated: 2026-05-02.*

### Pre-requisite (do first, unlocks everything)
| Sprint | Feature | Audience | Notes |
|---|---|---|---|
| **PRE-1** ✅ | Per-tool TTL caching (non-LLM + LLM) | Infra | See SEC:CACHING. Do before new data tools. |
| **PRE-2** ✅ | Mode-aware ResearchPage (show/hide panels by mode) | Infra | Fix before new panels land. |

### Day Trading Block
| Sprint | Feature(s) | Audience | Complexity | Tokens |
|---|---|---|---|---|
| **5** ✅ | MTF confluence score + RVOL signal | Day trader | Low | 0 |
| **6 (Sprint 7)** ✅ | S/R levels + Pivot Points + ORB levels | Day trader | Medium | 0 |
| **7 (Sprint 6)** ✅ | Pre-trade checklist scorecard | Both | Low | 0 |
| **8** ✅ | Position sizing calculator | Both | Low | 0 |
| **9** | Pre-market gap scanner + Float/squeeze score | Day trader | Medium | 0 |
| **10** | GARCH volatility forecast + Regime classifier | Day trader | High | 0 |
| **11** | Dashboard page (market pulse + movers + calendar) | Day trader | Medium | 0 |

### Both Audiences Block
| Sprint | Feature(s) | Audience | Complexity | Tokens |
|---|---|---|---|---|
| **12** | Economic calendar (FRED) + Fear/Greed index | Both | Low | 0 |
| **13** | IBD RS Rating + Seasonality analysis | Both | Low | 0 |
| **14** | Smart money composite score | Both | Low | 0 |
| **15** | Market breadth dashboard | Both | Medium | 0 |
| **16** | Watchlist heatmap + Price target trend | Both | Low | 0 |

### Long-Term Block
| Sprint | Feature(s) | Audience | Complexity | Tokens |
|---|---|---|---|---|
| **17** | DCF + Graham Number + Peer comps | Long-term | Medium | 0 |
| **18** | SEC EDGAR 8-year fundamentals | Long-term | Medium | 0 |
| **19** | CANSLIM score + Minervini VCP detector | Long-term | Medium | 0 |
| **20** | Dividend health score + Moat score | Long-term | Low | 0 |
| **21** | 10-K risk factor change tracker | Long-term | Medium | ~2000 |
| **22** | Institutional guru portfolio tracker (13F) | Long-term | Medium | 0 |

---

<!-- SEC:DAY_TRADING -->
## Day Trading Feature Backlog

**Sprint 5 — Multi-Timeframe Confluence Score** (0 tokens)
Score RSI/MACD/VWAP alignment across 5m, 15m, 1h, and daily simultaneously using yfinance multi-interval pulls. Output 0–100 score with per-timeframe breakdown. A stock bullish on all 4 timeframes = high conviction setup. Currently the app only analyzes one timeframe.
- Backend: new `technicals_mtf.py` tool, pulls 4 intervals in one call
- Frontend: new Tier 2 panel `MultiTimeframePanel.tsx`

**Sprint 5 — RVOL (Relative Volume) Signal** (0 tokens)
RVOL = current volume / average volume for same time-of-day. RVOL > 2 by 10am is the most reliable day trading filter. Currently app shows raw volume; this adds time-normalized RVOL with a signal (LOW/NORMAL/HIGH/EXTREME).
- Backend: add to `price.py` or `technicals.py`, needs intraday + 10-day average
- Sources: bullishbears.com, Finviz, r/Daytrading discussions

**Sprint 7 — Support/Resistance + Pivot Points** ✅ (0 tokens)
Auto-calculate daily/weekly/monthly pivot points (Classic: P=(H+L+C)/3, R1/R2/S1/S2) and key historical S/R levels from price swing highs/lows. Plot as horizontal reference lines on the price chart alongside existing VPOC/VAH/VAL.
- Backend: add to `price.py` response — `pivots` dict, `support_resistance` list
- Frontend: additional `ReferenceLine` entries in `PriceChart.tsx`

**Sprint 7 — Opening Range Breakout (ORB) Levels** ✅ (0 tokens)
Pull first 15-min and 30-min candle from 5-min intraday data. Output ORB high/low, whether current price is above/below, and breakout confirmation (volume + close). Highest win-rate day trading setup — Warrior Trading, Humbled Trader standard.
- Backend: add to `price.py` intraday processing, returns `orb_15` and `orb_30` dicts
- Frontend: ORB levels as reference lines on 1d chart only

**Sprint 11 — Pre-Market Gap Scanner** (0 tokens)
For the user's watchlist, surface all tickers gapping >2% pre-market with: gap %, gap type (earnings/news/sector/no-catalyst), RVOL, float classification. Day traders call this the "morning watchlist" — their #1 daily workflow.
- Backend: new `gap_scanner.py` tool, runs against watchlist tickers
- Frontend: new card on WatchlistPage showing pre-market movers
- Sources: warriortrading.com, centerpointsecurities.com

**Sprint 11 — Float + Short Squeeze Score** (0 tokens)
Combine float size (yfinance `floatShares`), short float %, days-to-cover, recent volume surge, and catalyst present → Squeeze Probability Score (0–100) with tier label: Low Float Momentum / Short Squeeze Setup / Overextended / No Setup.
- Backend: add to `short_interest.py` or new `squeeze.py`
- Frontend: add to existing Short Interest panel or new card

**Sprint 6 — Pre-Trade Checklist Scorecard** ✅ (0 tokens)
Automate the day trader's pre-trade checklist: trend direction (daily), catalyst present, RVOL >1.5, float tier, sector momentum, above/below VWAP, RSI not extreme. Output: score X/10 with PROCEED/CAUTION/AVOID verdict. Makes the app the decision gate before order entry.
- Backend: new `pretrade_score.py` — aggregates existing T1 data, no new API calls
- Frontend: prominent card in ResearchPage T1 section

**Sprint 15 — GARCH Volatility Forecast** (0 tokens)
Predict expected daily price range for next 1–5 days using GARCH(1,1) model. More useful than direction prediction — helps set stop losses and size options positions. `arch` library is free.
- Backend: new `volatility_forecast.py`, uses `arch` package
- Dep: `pip install arch`

**Sprint 15 — Momentum Regime Classifier** (0 tokens)
Classify whether stock is in trending vs mean-reverting regime using Hidden Markov Model on recent price action. Different strategies apply to each regime. `hmmlearn` is free.
- Backend: add to `technicals.py` or new `regime.py`
- Dep: `pip install hmmlearn scikit-learn`
- Sources: r/algotrading, curistat futures regime approach

---

<!-- SEC:LONG_TERM -->
## Long-Term Investing Feature Backlog

**Sprint 6 — DCF + Intrinsic Value Calculator** (0 tokens)
Auto-build DCF from yfinance FCF history, revenue CAGR, and adjustable discount rate. Bear/base/bull scenarios with implied price. Add Graham Number (√(22.5 × EPS × Book Value)) and PEG fair value alongside. Three independent valuation signals in one panel. Koyfin/TIKR charge for this.
- Backend: new `valuation.py` tool — pure math on existing yfinance data
- Frontend: new Tier 2 `ValuationPanel.tsx` with scenario table and fair value comparison

**Sprint 6 — Peer Comparable Valuation** (0 tokens)
Auto-fetch 5 sector peers from yfinance. Compare P/E, P/S, EV/EBITDA, P/FCF, PEG in a table. Color-code premium/discount vs peer median. Simply Wall St and Koyfin charge for this.
- Backend: add to `valuation.py` or new `peer_comps.py`
- Frontend: table in `ValuationPanel.tsx`

**Sprint 10 — SEC EDGAR 8-Year Fundamentals** (0 tokens)
Pull XBRL-formatted financial statements from `data.sec.gov` (no API key, 10 req/sec free). Show 8 years of revenue, net income, operating margin, FCF, debt/equity as mini trend charts. More complete than yfinance's 4 quarters.
- Backend: new `edgar_fundamentals.py` — REST calls to `data.sec.gov/api/xbrl/companyfacts/`
- Frontend: new Tier 2 `EDGARFundamentalsPanel.tsx` with sparkline charts
- Sources: sec.gov/edgar/developer, medium EDGAR XBRL Python guide

**Sprint 16 — CANSLIM Composite Score** (0 tokens)
Implement William O'Neil's full framework: Current quarterly earnings growth, Annual earnings growth, New high, Supply (float), Leader (RS rating), Institutional sponsorship, Market direction. Output score per criterion and overall verdict.
- Backend: new `canslim.py` tool — combines existing + new ratio calculations
- Sources: github.com/ssshah86/CAN-SLIM-screener

**Sprint 16 — Minervini VCP (Volatility Contraction Pattern) Detector** (0 tokens)
Mark Minervini's trend template: stock above 150/200 SMA, 52-week low ≥30% from current price, price within 25% of 52-week high, RS rating >70, declining volatility in recent weeks. Pure OHLCV computation.
- Backend: add to `technicals.py` or new `patterns.py`
- Sources: github.com/xang1234/stock-screener Minervini implementation

**Sprint 17 — Dividend Health Score** (0 tokens)
Payout ratio, dividend growth CAGR (3/5/10yr), consecutive growth years, FCF coverage ratio, sustainability verdict (SAFE/WATCH/DANGER). Computable from yfinance dividend history and financials.
- Backend: new `dividend.py` tool
- Frontend: new Tier 2 panel, only renders for dividend-paying stocks

**Sprint 17 — Economic Moat Score** (0 tokens)
Proxy score from: ROE >15% consistently over 5 years, gross margin trend, ROIC vs WACC spread, revenue growth consistency, competitive advantage indicators. Morningstar charges $200/yr for moat ratings.
- Backend: new `moat.py` tool — needs multi-year data from EDGAR or yfinance
- Sources: Morningstar methodology, Charlie Munger checklist

**Sprint 18 — 10-K Risk Factor Change Tracker** (~2000 LLM tokens)
Pull Risk Factors section from latest and prior-year 10-K via SEC EDGAR full-text search (`efts.sec.gov`). LLM diff: "What new risks were added? What risks were removed?" Genuinely novel — not offered anywhere free.
- Backend: new `edgar_risk_factors.py` — EDGAR full-text search + LLM diff
- Frontend: Tier 3 panel (expensive, click-to-run)
- Free endpoint: `efts.sec.gov/hits.json?q="risk+factors"&dateRange=custom&...`

**Sprint 20 — Institutional Guru Portfolio Tracker** (0 tokens)
Which "guru" investors (Buffett/Berkshire, Ackman, Einhorn etc.) hold the stock via SEC 13F filings. Show entry price range, holding duration, % of their portfolio. TIKR charges for this — EDGAR 13F is free.
- Backend: new `guru_tracker.py` — parses 13F-HR from `data.sec.gov`
- Frontend: Tier 2 panel with guru cards

---

<!-- SEC:BOTH -->
## Features Serving Both Audiences

**Sprint 8 — Position Sizing Calculator** ✅ (0 tokens, frontend only)
User inputs account size once (saved to localStorage). Given entry + stop loss, calculate: max shares, dollar risk, % of portfolio, position value. Output: "Risk $487 (0.97% of $50k) → 127 shares max." Makes the app the final step before order entry.
- Frontend only: new `PositionSizer.tsx` component in ResearchPage sidebar
- No backend needed — pure client-side math

**Sprint 9 — Seasonality Analysis** (0 tokens)
Pull 10 years of monthly returns from yfinance. Show: "January: avg +3.2%, positive 7/10 years." Monthly heatmap grid. Both traders (timing entries) and investors (timing additions) use this.
- Backend: new `seasonality.py` tool
- Frontend: new Tier 2 `SeasonalityPanel.tsx` with monthly grid

**Sprint 9 — IBD RS Rating** (0 tokens)
0–99 percentile relative strength vs S&P 500: 52-week price performance with most-recent-quarter weighted 2x. IBD charges subscription for this. Open-source formula implemented by github.com/skyte/relative-strength.
- Backend: add to `technicals.py` — needs SPY history for comparison
- Frontend: add RS badge to price header alongside RSI

**Sprint 12 — Economic Calendar** (0 tokens)
Upcoming high-impact events in next 14 days: Fed meetings and CPI/NFP release dates from FRED calendar (free via existing FRED_API_KEY) + the ticker's next earnings date (already in T1). Tag High/Medium/Low impact. "3 high-impact events before your target entry" warning.
- Backend: new `economic_calendar.py` using FRED release schedule API
- Frontend: calendar card in ResearchPage T1 section

**Sprint 12 — Fear & Greed Index** (0 tokens)
Alternative.me provides CNN Fear & Greed composite (0–100) as a free JSON endpoint — no key required. Single line addition to the macro environment panel. Extreme Fear (<20) = historical buy zone.
- Backend: add to `macro.py` — one HTTP call to `api.alternative.me/fng/`
- Frontend: add Fear/Greed gauge to existing macro panel

**Sprint 13 — Smart Money Composite Score** (0 tokens)
Synthesize three signals already in T1: insider buy/sell balance, institutional 13F net change direction, congressional trade direction. Single Smart Money Score (ACCUMULATING/NEUTRAL/DISTRIBUTING). Currently three separate panels with no synthesis.
- Backend: add to `convergence.py` or new `smart_money.py` — uses existing T1 data
- Frontend: add to T1 section as a verdict badge

**Sprint 14 — Market Breadth Dashboard** (0 tokens)
% of S&P 500 stocks above 50-day MA, % above 200-day MA, advance/decline ratio, new 52-week highs vs lows. Computable from yfinance by pulling major index component data. IBD and StockBee charge for this.
- Backend: new `market_breadth.py` — pulls ~50 representative stocks across sectors as proxy
- Frontend: new section on MacroPage
- Sources: github.com/xang1234/stock-screener StockBee-style breadth

**Sprint 19 — Watchlist Heatmap** (0 tokens)
Color grid of all watchlist tickers by % change today. Green/red intensity = magnitude. High visual impact, instant portfolio health overview. Similar to Finviz sector heatmap but for the user's personal watchlist.
- Frontend only: new heatmap view on WatchlistPage (toggle between heatmap and table)

**Sprint 19 — Price Target Trend** (0 tokens)
Show analyst price target history — not just current consensus but the trend: are analysts raising or cutting targets over the last 6 months? 3 consecutive raises = far more bullish than a single stale target. All from yfinance analyst data.
- Backend: add to `analyst.py` — process historical target changes
- Frontend: add trend sparkline to existing analyst panel

**Sprint 25 — News Catalyst Quality Scorer** (0 tokens)
Classify news type beyond sentiment: earnings beat/miss, FDA approval, contract win, analyst upgrade, insider buy, product launch, legal risk, macro headwind. Weight by category. Output: "Catalyst Strength: HIGH — positive earnings surprise + analyst upgrade."
- Backend: rule-based classifier in `news.py` using headline keyword matching
- Frontend: add catalyst badge to news panel items

**Sprint 26 — Sentiment Divergence Signal** (0 tokens)
When price makes new highs but Reddit/StockTwits sentiment is falling (or vice versa), flag as a divergence signal. Historically precedes reversals. Combines existing sentiment data with price momentum.
- Backend: add divergence check to `sentiment.py` or `convergence.py`

---

<!-- SEC:ALGO -->
## Algorithmic / Novel Approaches

| Approach | Complexity | Library | Notes |
|---|---|---|---|
| GARCH(1,1) volatility forecast | Medium | `arch` (free) | Predict daily range, not direction — actually useful |
| Hidden Markov Model regime classifier | Medium | `hmmlearn` (free) | Trending vs mean-reverting — tells trader which strategy |
| IBD RS Rating percentile | Low | None (pure pandas) | github.com/skyte/relative-strength for formula |
| Minervini VCP detector | Low | None | Pure OHLCV rules |
| CANSLIM scoring | Medium | None | Pure ratio rules + RS rating |
| Statistical correlation scan (OmniOracle style) | High | `scipy` (free) | Scan 500+ FRED series for non-trivial correlations with stock price |
| Chart pattern similarity search | High | `numpy` | Pre-computed embeddings of 24M+ patterns — no ML training |
| Order book imbalance proxy | Medium | None | Approximate buy/sell pressure from tick-direction analysis on 5-min candles |

---

<!-- SEC:DATA_SOURCES -->
## Free Data Sources Available to Tap

| Source | Data | Key needed | Rate limit | Priority |
|---|---|---|---|---|
| **yfinance** | OHLCV, options, fundamentals, analyst, earnings | No | Shared 2/s (app rate limiter) | Already in use |
| **FRED API** | Credit spreads, yield curves, M2, CPI, all macro | Yes (free, instant) | No practical limit | Already in use |
| **NewsAPI** | Headlines, sentiment | Yes (free tier) | 100/day dev | Already in use |
| **Reddit PRAW** | WSB/stocks/investing sentiment | Yes (free) | 60/min | Already in use |
| **StockTwits** | Retail sentiment | No | Public API | Already in use |
| **SEC EDGAR `data.sec.gov`** | XBRL financials 8+ years, 13F, Form 4 | No (User-Agent header only) | 10 req/sec | **HIGH — Sprint 10** |
| **SEC EDGAR `efts.sec.gov`** | Full-text search across all filings | No | Generous | **HIGH — Sprint 18** |
| **Alternative.me** | Fear & Greed Index (0–100) | No | Free forever | **LOW — Sprint 12** |
| **FRED release calendar** | Upcoming CPI/NFP/Fed meeting dates | Already have key | No limit | **MEDIUM — Sprint 12** |
| **BLS API** | Employment, CPI, PPI historical | No (free tier) | 25 req/day | Medium |
| **Wikipedia Pageviews API** | Company search interest (alt sentiment) | No | Free | Low |
| **Polymarket API** | Prediction market odds (Fed cuts, recession) | No | Free | Low |
| **pytrends** | Google Trends spikes (already in stack) | No | Soft limits | Already wired |

**Finnhub free tier** (requires free API key): government contracts, FDA calendar, earnings call metadata, ESG scores, supply chain data, lobbying records, insider sentiment (MSPR), earnings surprise history — 60 calls/min free. Worth adding `FINNHUB_API_KEY` to `.env` as optional.

---

<!-- SEC:PARKED -->
## Parked Features — Waiting on Reddit API Access

These features are designed and ready but require Reddit PRAW credentials.
Resume once `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` are confirmed working.

| Feature | What it needs | Where it goes |
|---|---|---|
| Sentiment divergence signal | Reddit PRAW sentiment feed | `sentiment.py` + `convergence.py` |
| Pre-market gap catalyst tagger | Reddit WSB scan for ticker mentions | `gap_scanner.py` |
| Reddit sentiment trend chart | PRAW historical mention volume | T2 Sentiment panel |

Current workaround: sentiment tool falls back to StockTwits only when Reddit creds are missing.

---

<!-- SEC:PAID_LATER -->
## Paid API Features — Defer

These require paid subscriptions. Noted here so we don't accidentally implement then hit a paywall.

| Feature | Blocker | Cost | Notes |
|---|---|---|---|
| Real Level 2 order book | No free source | $50–200/mo | Polygon.io, Alpaca premium |
| Real-time options flow (unusual activity alerts) | No free source | $50–200/mo | Unusual Whales, FlowAlgo |
| Dark pool / FINRA prints | Partial free | $100+/mo | Some FINRA data is public but delayed |
| Earnings call transcripts (full text) | Paywalled | $50+/mo | Seeking Alpha, Motley Fool |
| Social media sentiment at scale | Rate-limited | $50+/mo | Twitter/X API v2 |
| Analyst report full text | Paywalled | $200+/mo | Refinitiv, Bloomberg |
| Alternative data (credit card spend, web traffic) | Expensive | $500+/mo | Second Measure, SimilarWeb |

---

*Last updated: 2026-05-02. Decisions locked. Next: PRE-1 (per-tool caching) → PRE-2 (mode-aware UI) → Sprint 5. Use SEC: anchors to navigate — never read the full file.*
