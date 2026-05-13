# Stock Research Pro — LLM Navigation Index
# Read this file first (~100 lines). Then grep docs/ for specifics.
# Workflow: grep -n "SEC:" docs/<file>.md → pick a line → read from there.

---

## Project Identity
Name: Stock Research Pro
Purpose: AI-powered stock research — day trading + long-term investment signals
Stack: FastAPI + LangGraph (ReAct) + React 18 + TypeScript + Vite + PostgreSQL + Redis
Status: V2 complete
Owner: Basant (Senior Full-Stack Engineer, NJ/NY)

---

## Navigation Map

| Topic | File | Grep anchor |
|---|---|---|
| Tech stack + LLM providers | docs/architecture.md | `SEC:STACK` |
| LLM factory / provider swap | docs/architecture.md | `SEC:LLM_FACTORY` |
| Key architectural decisions | docs/architecture.md | `SEC:DECISIONS` |
| Full request lifecycle + token saving gates | docs/architecture.md | `SEC:TOKEN_FLOW` |
| Per-tool cache TTLs (Redis vs DB) | docs/architecture.md | `SEC:CACHE` |
| Database models | docs/architecture.md | `SEC:DB_MODELS` |
| Project directory map | docs/architecture.md | `SEC:DIR_MAP` |
| Feature roadmap + sprint order | plan.md | `SEC:PRIORITY` |
| Locked architectural decisions | plan.md | `SEC:DECISIONS` |
| UI page layout | plan.md | `SEC:UI_PAGES` |
| V1 API routes | docs/api.md | `SEC:V1_ROUTES` |
| V2 tiered routes | docs/api.md | `SEC:V2_ROUTES` |
| Dip scanner routes (scan, weekly, analytics, backfill) | docs/api.md | `SEC:DIP_SCANNER_ROUTES` |
| Usage / guard-rail routes | docs/api.md | `SEC:USAGE_ROUTES` |
| Auth pattern | docs/api.md | `SEC:AUTH` |
| V1 tool catalog (20 tools) | docs/tools.md | `SEC:V1_TOOLS` |
| V2 new tools (6 tools) | docs/tools.md | `SEC:V2_TOOLS` |
| Tool conventions + add guide | docs/tools.md | `SEC:TOOL_CONVENTIONS` |
| Frontend pages | docs/frontend.md | `SEC:PAGES` |
| Key components | docs/frontend.md | `SEC:COMPONENTS` |
| Zustand store shape | docs/frontend.md | `SEC:STORE` |
| Execution modes (saver/normal/deep) | docs/features.md | `SEC:EXEC_MODES` |
| Feature tiers (T1/T2/T3) | docs/features.md | `SEC:TIERS` |
| Token consumption estimates | docs/features.md | `SEC:TOKEN_ESTIMATES` |
| Guard rails system | docs/features.md | `SEC:GUARD_RAILS` |
| Usage tracking (usage.json) | docs/features.md | `SEC:USAGE_TRACKING` |
| Background jobs (APScheduler) | docs/features.md | `SEC:BACKGROUND_JOBS` |
| Daily Target Trade Scanner (signals, scoring, scenarios, backfill) | docs/features.md | `SEC:DIP_SCANNER` |
| Signal convergence score | docs/features.md | `SEC:CONVERGENCE` |
| Dev commands (make up etc.) | docs/dev.md | `SEC:COMMANDS` |
| Environment variables | docs/dev.md | `SEC:ENV_VARS` |
| Testing conventions | docs/dev.md | `SEC:TESTING` |
| Adding a new feature checklist | docs/dev.md | `SEC:ADD_FEATURE` |

---

## Critical Rules (apply to every change)

1. **Tools never raise** — always `return {"error": "..."}` on failure, never `raise`
2. **One tool per file** — `backend/app/tools/<name>.py`, import in `graph.py` ALL_TOOLS
3. **LLM swap = one env change** — change `MODEL_TYPE` in `.env`, zero code changes
4. **Saver mode bypasses all token limits** — by design, do not add guards for it
5. **Every change** → update the relevant `docs/` file + add a line to Recent Changes below
6. **Guard rail limits** live only in `backend/app/services/usage/limits.py` — edit nowhere else
7. **Reading docs** → NEVER read a full `docs/*.md` file. Use the nav map above to find the right file, `grep -n "SEC:ANCHOR" docs/file.md` to get the line, then `Read` with `offset`+`limit` for that section only. Full reads waste ~2k tokens per file.

---

## Recent Changes

| Date | Change |
|---|---|
| 2026-05-11 | Scanner reliability batch: eod_dump.py converts entry_time to ET in SELECT (fixes time_et display bug — DB always stored correct timestamptz, only the dump was rendering UTC) and now honors DATABASE_URL env var; backend container TZ=America/New_York for ET-stamped logs/APScheduler/naive datetimes (DB stays timestamptz); resolver gains _compute_fmd() with tz-normalized index + diagnostic logging + 7-day backfill of null five_min_direction across closed rows; 15-min per-ticker dedup in api/dip_scanner.py:_save_alert (suppresses correlated back-to-back live alerts; backtest exempt); time_stop enforcement in resolver per signal_type (dip_buy 25 / orb_breakout 60 / vwap_reclaim 20 / failed_breakdown 30 min) — frees capital from dead-money trades that drift to ~breakeven by EOD |
| 2026-05-08 | Market Intelligence Layer (branch `feature/market-intelligence-layer`): ORB breakout + VWAP reclaim + VIX spike prep detectors in dip_scanner.py; GET /dip-scanner/weekly endpoint; 30-scenario scenarios.json; SituationSummary + WeeklyTargetBar components; DipScannerCard wired with scenario guidance, signal-type badges, VIX spike banner; DashboardPage adds WeeklyTargetBar above scanner grid |
| 2026-05-08 | Daily Target Trade Scanner (branch `feature/daily-target-scanner`): ScannerAlert DB model + migration; dip_scanner.py tool (VWAP/RSI scoring, VIX-adjusted thresholds, 60-day backfill); /dip-scanner/scan + analytics + backfill + config endpoints; DipScannerCard + ScannerPerformanceCard; 5-min background scan + outcome resolver scheduler jobs; dip_buy_alert WebSocket type |
| 2026-05-03 | Sprint 25: News Catalyst Quality Scorer — _classify_catalyst()/_catalyst_strength() in news.py (12 categories, HIGH/MEDIUM/LOW strength); catalyst_type+catalyst_strength fields on NewsItem; NewsPanel.tsx shows catalyst badge + strength pill |
| 2026-05-03 | Sprint 22: Institutional Guru Portfolio Tracker — guru_tracker.py (13F-HR via EDGAR for 8 gurus: Berkshire/Pershing/Appaloosa/etc.); GuruHoldingsPanel in Tier3Panels.tsx (verdict badge + holding cards) |
| 2026-05-03 | Sprint 21: 10-K Risk Factor Change Tracker — edgar_risk_factors.py (EDGAR 10-K Item 1A diff, ~2000 LLM tokens); RiskFactorPanel in Tier3Panels.tsx (trajectory badge + new/removed/changed risks); Tier 3, long_term mode |
| 2026-05-03 | Sprint 20: Dividend Health + Economic Moat Score — dividend.py (payout/FCF/growth/streak checks → SAFE/WATCH/DANGER); moat.py (ROE/margin/ROIC/growth/net-margin → WIDE/NARROW/NONE); FundamentalsQualityPanels.tsx |
| 2026-05-03 | Sprint 19: CANSLIM Score + Minervini VCP — canslim.py (7 O'Neil criteria → STRONG SETUP/MODERATE/DOES NOT QUALIFY); patterns.py (5 Stage 2 VCP criteria → A+/B/C/F grade); CanslimPanel.tsx + VCPPanel.tsx |
| 2026-05-03 | Sprint 18: SEC EDGAR 8-Year Fundamentals — edgar_fundamentals.py (CIK lookup + XBRL companyfacts: revenue/NI/OI/FCF/debt 8yr); EDGARFundamentalsPanel.tsx (inline SVG sparklines per metric) |
| 2026-05-03 | Sprint 17: DCF + Graham Number + Peer Comps — valuation.py (DCF bear/base/bull, Graham sqrt(22.5*EPS*BVPS), peer P/E/PS/EV/EBITDA via _SECTOR_PEERS); ValuationPanel.tsx |
| 2026-05-03 | Sprint 16: Watchlist Heatmap + Analyst Price Target Trend — HeatmapView in WatchlistPage.tsx (▦ toggle, score-colored grid); core_tools.py get_analyst_consensus() adds target_low/high/trend + upgrade/downgrade momentum 90d windows |
| 2026-05-03 | Sprint 15: Market Breadth Dashboard — market_breadth.py (66-stock S&P proxy, % above 50d/200d, A/D ratio, 52w H/L); GET /macro/breadth + included in /macro/all; breadth section in MacroPage.tsx |
| 2026-05-03 | Sprint 14: GARCH Volatility Forecast + HMM Regime Classifier — volatility_forecast.py (GARCH(1,1) via arch lib, 5-day range forecast, fallback rolling std); regime.py (2-state HMM via hmmlearn, fallback heuristic); VolatilityPanel.tsx + RegimePanel.tsx; arch+hmmlearn+scikit-learn added to requirements.txt |
| 2026-05-03 | Sprint 11: Market Dashboard page — DashboardPage.tsx (market pulse cards, top gainers/losers, sector rotation grid, upcoming catalysts); /dashboard route added to App.tsx + nav |
| 2026-05-02 | Sprint 13: Smart Money Composite Score — smart_money.py (congressional + analyst momentum + squeeze positioning → ACCUMULATING/NEUTRAL/DISTRIBUTING); wired into tier1 response; verdict badge with signal breakdown in ResearchPage (both modes) |
| 2026-05-02 | Sprint 12: Fear & Greed Index — fear_greed.py (Alternative.me free API, 7-day history, arc gauge); Economic Calendar — economic_calendar.py (FRED releases for CPI/NFP/FOMC/GDP/PCE, 14-day ahead); /macro/all now includes both; MacroPage shows gauge + calendar above sector heatmap |
| 2026-05-02 | Sprint 10: Pre-Market Gap Scanner — gap_scanner.py scan_gaps() + POST /gap-scanner/ endpoint; GapScannerCard.tsx on WatchlistPage; float_class/_squeeze_score() helpers in core_tools.py; get_short_interest() returns float_class, vol_ratio, squeeze_score, squeeze_tier; Short Interest panel shows all 4 new fields |
| 2026-05-02 | Sprint 9: Seasonality — seasonality.py (10y monthly returns, win rate, best/worst month); SeasonalityPanel.tsx (4×3 heatmap grid, heat colors, NOW badge on current month); IBD RS Rating added to technicals.py (SPY-relative weighted 52-wk perf → 1–99, TechPill in ResearchPage) |
| 2026-05-02 | Sprint 8: Position Sizer — PositionSizer.tsx (account+risk% persisted to localStorage, entry pre-fills from current price, stop defaults -3%, computes shares/risk$/position%/R:R); ExpandablePanel in day_trade T1 section |
| 2026-05-02 | Sprint 6: Pre-Trade Checklist Scorecard — pretrade_score.py (10 criteria, 0 tokens, pure T1 aggregation); wired into tier1 API response; PreTradeScorecard.tsx shows PROCEED/CAUTION/AVOID verdict + score/10 + checklist grid in day_trade mode |
| 2026-05-02 | Sprint 7: Classic pivot points (P/R1/R2/S1/S2) + swing S/R levels in price.py; ORB-15/ORB-30 with breakout confirmation in price.py; PriceChart shows pivots on 1d, S/R on multi-day, ORB on 1d only |
| 2026-05-02 | Sprint 5: RVOL signal in price.py (time-normalized, EXTREME/HIGH/NORMAL/LOW badge, day trade only) + MTF Confluence tool (technicals_mtf.py) + MultiTimeframePanel.tsx |
| 2026-05-02 | PRE-2: Mode-aware ResearchPage — Day Trade hides analyst/earnings/fundamentals/LT-T3, Long Term hides options/short-interest/DT-T3; show() helper filters TIER2_PANELS/TIER3_PANELS arrays; price chart defaults 1d vs 3M |
| 2026-05-02 | PRE-1: Per-tool TTL caching — fixed TTLs in config.py, updated _llm_ttl_hours() in data_cache.py, dynamic expiry for analyze_earnings_transcript |
| 2026-05-02 | Document full request lifecycle (SEC:TOKEN_FLOW) + per-tool TTL cache strategy in architecture.md |
| 2026-05-02 | Lock architectural decisions in plan.md — day trading priority, Dashboard page, caching rules |
| 2026-05-02 | Show expected EPS estimate in earnings card collapsed header (EarningsHistoryPanel) |
| 2026-05-02 | Add volume profile overlay to PriceChart — VPOC (amber), VAH (green), VAL (red) on multi-day charts |
| 2026-05-02 | Add FRED Macro Dashboard — credit spreads, yield curves, real yields, M2, cross-asset via `fred_macro.py` + `GET /macro/fred` |
| 2026-05-02 | Add Options Intelligence panel (Tier 2, 0 tokens) — GEX, max pain, IV analysis, skew, term structure |
| 2026-05-02 | Add Earnings Quality panel (Tier 2, 0 tokens) — Piotroski, Beneish, Altman, Accruals |
| 2026-05-02 | Add `signal.py` — shared SignalResult + composite_verdict() used across quality and options tools |
| 2026-05-02 | Persist mode, exec_mode, lastTicker in localStorage via zustand/middleware persist |
| 2026-05-02 | True 1d intraday chart: 5-min candles + pre/after-market data |
| 2026-05-02 | Structured logging to `local_debugging/app.log` with request timing and cache visibility |
| 2026-05-02 | LLM cache for Tier 2/3 results; configurable CACHE_TTL_* env vars |
| 2026-05-02 | StockDataCache DB model + data_cache service for Tier 1 yfinance caching |
| 2026-05-02 | EarningsHistoryPanel: newest-first, relative labels, beat streak dots, expanded detail cards |
| 2025-04-27 | Fix SSE stream: unwrap LangGraph node output before reading messages |
| 2025-04-27 | Create `api/research_v2.py` + `api/usage.py` — were missing, caused 404s |
| 2025-04-27 | Fix news panel hang: pass `company_name` from tier1 to skip yfinance lookup |
| 2025-04-27 | Add `asyncio.wait_for` timeout (25 s tier2, 90 s tier3) against infinite hangs |
| 2025-04-27 | Fix `ExpandablePanel`: fire `onExpand` on mount when panel starts auto-expanded |
| 2025-04-27 | Resolve merge conflict in `research.py` — kept thread+queue SSE pattern |
