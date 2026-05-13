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
| Tech stack + LLM providers | docs/reference/architecture.md | `SEC:STACK` |
| LLM factory / provider swap | docs/reference/architecture.md | `SEC:LLM_FACTORY` |
| Key architectural decisions | docs/reference/architecture.md | `SEC:DECISIONS` |
| Full request lifecycle + token saving gates | docs/reference/architecture.md | `SEC:TOKEN_FLOW` |
| Per-tool cache TTLs (Redis vs DB) | docs/reference/architecture.md | `SEC:CACHE` |
| Database models | docs/reference/architecture.md | `SEC:DB_MODELS` |
| Project directory map | docs/reference/architecture.md | `SEC:DIR_MAP` |
| Feature roadmap + sprint order | plan.md | `SEC:PRIORITY` |
| Locked architectural decisions | plan.md | `SEC:DECISIONS` |
| UI page layout | plan.md | `SEC:UI_PAGES` |
| V1 API routes | docs/reference/api.md | `SEC:V1_ROUTES` |
| V2 tiered routes | docs/reference/api.md | `SEC:V2_ROUTES` |
| Dip scanner routes (scan, weekly, analytics, backfill) | docs/reference/api.md | `SEC:DIP_SCANNER_ROUTES` |
| Usage / guard-rail routes | docs/reference/api.md | `SEC:USAGE_ROUTES` |
| Auth pattern | docs/reference/api.md | `SEC:AUTH` |
| V1 tool catalog (20 tools) | docs/reference/tools.md | `SEC:V1_TOOLS` |
| V2 new tools (6 tools) | docs/reference/tools.md | `SEC:V2_TOOLS` |
| Tool conventions + add guide | docs/reference/tools.md | `SEC:TOOL_CONVENTIONS` |
| Frontend pages | docs/reference/frontend.md | `SEC:PAGES` |
| Key components | docs/reference/frontend.md | `SEC:COMPONENTS` |
| Zustand store shape | docs/reference/frontend.md | `SEC:STORE` |
| Execution modes (saver/normal/deep) | docs/reference/features.md | `SEC:EXEC_MODES` |
| Feature tiers (T1/T2/T3) | docs/reference/features.md | `SEC:TIERS` |
| Token consumption estimates | docs/reference/features.md | `SEC:TOKEN_ESTIMATES` |
| Guard rails system | docs/reference/features.md | `SEC:GUARD_RAILS` |
| Usage tracking (usage.json) | docs/reference/features.md | `SEC:USAGE_TRACKING` |
| Background jobs (APScheduler) | docs/reference/features.md | `SEC:BACKGROUND_JOBS` |
| Daily Target Trade Scanner (signals, scoring, scenarios, backfill) | docs/reference/features.md | `SEC:DIP_SCANNER` |
| Signal convergence score | docs/reference/features.md | `SEC:CONVERGENCE` |
| Dev commands (make up etc.) | docs/development/dev.md | `SEC:COMMANDS` |
| Environment variables | docs/development/dev.md | `SEC:ENV_VARS` |
| Testing conventions | docs/development/dev.md | `SEC:TESTING` |
| Adding a new feature checklist | docs/development/dev.md | `SEC:ADD_FEATURE` |
| Deployment strategy | docs/development/deployment_strategy.md | `SEC:DEPLOY` |
| Operating rules (docs discipline, git workflow, code conventions, TZ) | docs/rules.md | `SEC:DOCS` / `SEC:GIT` / `SEC:CODE` / `SEC:TIMEZONE` |
| Known doc debt (stale sections, missing entries) | docs/rules.md | `SEC:DOC_DEBT` |
| Scanner improvement backlog (Opus review, 30 ideas, priority ranked) | local_debugging/opus_scanner_ideas.md | read directly — no anchor needed |
| Scanner sprint notes + signal type design | local_debugging/dip-scanner-sprint.md | read directly |
| Uncommitted changes staging log (commit tomorrow) | local_debugging/plus_plan.md | read directly |

---

## Critical Rules (apply to every change)

1. **Tools never raise** — always `return {"error": "..."}` on failure, never `raise`
2. **One tool per file** — `backend/app/tools/<name>.py`, import in `graph.py` ALL_TOOLS
3. **LLM swap = one env change** — change `MODEL_TYPE` in `.env`, zero code changes
4. **Saver mode bypasses all token limits** — by design, do not add guards for it
5. **Every change** → update the relevant `docs/` file + add a line to Recent Changes below
6. **Guard rail limits** live only in `backend/app/services/usage/limits.py` — edit nowhere else
7. **Reading docs** → NEVER read a full `docs/*.md` file. Use the nav map above to find the right file, `grep -n "SEC:ANCHOR" docs/file.md` to get the line, then `Read` with `offset`+`limit` for that section only. Full reads waste ~2k tokens per file.
8. **All other operating rules** live in `docs/rules.md` — branching, commits, PR cadence, no AI attribution, TZ convention, etc. Read it before any non-trivial change. Add new rules there as they emerge.

---

## Recent Changes

| Date | Change |
|---|---|
| 2026-05-12 | New Market Context First (MCF) Funnel Scanner added alongside Dip Scanner. Separate `/mcf` dashboard. Uses 3-layer checking logic with SPY/QQQ/IWM/DIA to predict entries with ~1% targets. DB caching implemented to avoid `yfinance` rate limits. |
| 2026-05-12 | Docs sweep: rewrote SEC:DIP_SCANNER (features.md) for current scanner reality — 4 signal types (incl. failed_breakdown), ATR-based stops/targets, regime gate, time stop, dedup, fmd backfill, near-miss logging, AI signal analysis; SEC:DIP_SCANNER_ROUTES (api.md) adds /similar /ticker-history /analyze /chart routes; SEC:DB_MODELS (architecture.md) adds full ScannerAlert schema with signal_type + five_min_direction + resolved_by; new docs/rules.md codifies operating rules (docs discipline, git workflow, code conventions, TZ) + tracks known doc debt; CLAUDE.md gains Critical Rule #8 referencing rules.md |
| 2026-05-11 | Scanner reliability batch: eod_dump.py converts entry_time to ET in SELECT (fixes time_et display bug — DB always stored correct timestamptz, only the dump was rendering UTC); backend container TZ=America/New_York for ET-stamped logs/APScheduler/naive datetimes (DB stays timestamptz); resolver gains _compute_fmd() with tz-normalized index + diagnostic logging + 7-day backfill of null five_min_direction across closed rows; 15-min per-ticker dedup in api/dip_scanner.py:_save_alert (suppresses correlated back-to-back live alerts; backtest exempt); time_stop enforcement in resolver per signal_type (dip_buy 25 / orb_breakout 60 / vwap_reclaim 20 / failed_breakdown 30 min) — frees capital from dead-money trades that drift to ~breakeven by EOD |
| 2026-05-10 | EOD analysis tooling: eod_dump.py queries DB → writes local_debugging/eod_signals/YYYY-MM-DD.json (signals/near-misses/score-bands/vs-60day/analysis_prompts); _log_near_miss() in dip_scanner.py logs score 65-71 signals to near_miss_log.jsonl; make eod + make eod-date targets |
| 2026-05-10 | Data-driven ETF filter: ETF_TIERS cut to SPY+QQQ (tier1) + XLK (tier2) — IWM/DIA/XLF/XLV/TLT removed based on <50% win rates; score threshold raised 65→72; analytics endpoint adds by_signal_type_summary (win rate+EV per signal type) and by_score_band (72-79/80-89/90+) for ongoing tuning; ScannerPerformanceCard shows both new tables |
| 2026-05-09 | AI signal analysis: POST /dip-scanner/analyze — queries DB win/loss history, builds structured prompt, calls LLM; returns verdict+plain_english+key_risk+watch_for; "What does this mean?" button in pro view; result clears on each new scan; blocked in saver mode |
| 2026-05-09 | Ticker history + order labels: GET /dip-scanner/ticker-history/{ticker}; side:"BUY" on all 4 signal types; TickerHistoryModal (click ticker name); "Other setups" mini-cards with Buy Limit/Sell Limit/Stop Loss grid; BUY badge + order-label relabeling throughout |
| 2026-05-09 | Manual trade log (batch 12): ManualTradeLog.tsx — log actual trades (ticker+P&L$+note), ISO-week scoped localStorage, shares dts_weekly_target with WeeklyTargetBar, progress bar + TARGET HIT badge; rendered below WeeklyTargetBar on Dashboard |
| 2026-05-08 | Data integrity fixes (batch 11): backfill KeyError min_dip_pct→min_dip_atr; backfill uses ATR stop/target from scorer; signal_type+five_min_direction added to backfill dict+ORM; live scan saves all 4 signal types (was only saving dip_buy) |
| 2026-05-08 | Scanner Opus batch 10 (#10,#18,#23,#24,#25,#29): GLD→TLT in ETF_TIERS; live distance-to-entry in entry cell; TERM_HINTS glossary+TermTip on VIX/ATR/dip labels; first-time onboarding modal (localStorage gate); Paper Trade button (localStorage, no DB); five_min_direction column+migration+resolver+analytics; 5-Min Accuracy metric in ScannerPerformanceCard |
| 2026-05-08 | Scanner Opus batch 9 (#14,#17,#28): MISSED badge (10s polling, price>entry+0.2×ATR); /dip-scanner/similar endpoint (last N closed signals per ticker/session/signal_type cell); by_signal_type analytics breakdown; SignalHeatmap in ScannerPerformanceCard (EV-colored cells); signal_type column + Alembic migration c7d3e4f5a6b7 |
| 2026-05-08 | Scanner Opus batch 7+8 (#13,#26): ORB 3:1 R, VWAP reclaim 1.5:1, failed breakdown 2.5:1; _refine_entry_1min() adjusts best signal entry to min of last 3×1-min lows (floored at −0.5%); entry_refined field in payload |
| 2026-05-08 | Scanner Opus batch 6 (#1,#11): _get_atr_5m() Wilder ATR-14 on 5-min bars (30-min cache); VIX thresholds → ATR multiples (0.4/0.7/1.1×ATR); support proximity → 0.10/0.20/0.35×ATR; stops entry−max(0.5×ATR,0.25%), targets entry+max(1.0×ATR,0.4%); atr_5m+atr_adjusted in payload |
| 2026-05-08 | Market regime gate (Opus #2): classify_regime() in regime.py (SPY 20-EMA + VIX 5d change + range-vs-ATR); trend_down blocks dip_buy, trend_up requires RSI<30; regime badge + blocking banner in DipScannerCard |
| 2026-05-08 | Scanner UX batch (Opus #12,#15,#22,#19): time_stop_minutes per signal type; ENTER NOW/READY state badge; pre-trade checklist modal (3 confirmations before Robinhood link); simple/pro view toggle (scannerView in Zustand); confidence tier very_high/high/medium replaces numeric score in simple view; top_reasons filtered in simple Why line |
| 2026-05-08 | Scanner signal intelligence (Opus #5,#7,#8,#9): capitulation penalty -15; 30-min trend alignment ±5/−10; CVD +8/+5/−5 from 5-min bars; failed_breakdown signal type (trapped shorts) |
| 2026-05-08 | Scanner quality sprint (Opus ideas #3,#4,#6,#16,#21,#30): hammer weight +15→+5 with stricter volume+wick definition; VIX slope scoring replaces VIX level (rising VIX = -10, falling = +12); hard lunch block score<80; WHITELIST_CELLS scaffold (disabled, enable at n≥5/cell); invalidation field in signal payload (price_close_below/vix_above/rvol_resurge); frontend "Risk $X → Make $Y" as primary P&L; invalidation line below chart |
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
