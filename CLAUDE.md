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
| Order execution — broker factory, paper/live, phases, risk gates | docs/trading.md | `SEC:GOALS` / `SEC:PHASES` / `SEC:ARCH` / `SEC:RISK` |
| Broker API routes (account, orders, positions, clock) | docs/api.md | `SEC:BROKER_ROUTES` |
| Portfolio page + OrderTicketModal + BrokerStatusBadge | docs/frontend.md | `SEC:PORTFOLIO_PAGE` |
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
| 2026-05-14 | Trading Phase 2 shipped: server-side risk caps (`services/trading/limits.py` — per-order $, per-position $, daily order count, daily realised loss via `account.equity - account.last_equity`), full `/broker/*` route set (POST orders with cap enforcement + idempotent client_order_id, GET positions/orders/clock, DELETE cancel), `BrokerOrder` rows persisted *before* the broker call so a mid-flight failure still leaves evidence of intent. Frontend: `/portfolio` page (account header + positions + open orders + fills, polls every 10s), `OrderTicketModal` (buy/sell with bracket + live-mode typed confirmation + cap-rejection copy mapping), `BrokerStatusBadge` in top nav, and a `Trade Signal →` button on `DipScannerCard` that pre-fills the modal from scanner entry/stop/target. |
| 2026-05-14 | New `docs/trading.md` plans broker integration (paper trading first, live after sign-off). Provider-agnostic via `BROKER` + `BROKER_MODE` env vars mirroring the LLM factory shape; Alpaca implementation first. Three phases: foundation (factory + smoke route + DB model), manual paper trading (portfolio page + order ticket), auto-trade behind feature flag. Risk caps (`TRADE_MAX_ORDER_DOLLARS` etc.) defined as their own service alongside `services/usage/limits.py`. |
| 2026-05-14 | Scanner data-quality batch (`fix/scanner-data-quality`): backtest `_append` now applies the live score gate (≥72, ≥80 in lunch_drift) — previously ORB/VWAP/Failed-Breakdown paths persisted sub-72 signals, polluting the 60-day baseline; near-miss writer stamps the bar's intraday timestamp (was using `datetime.now()`, producing all-16:01 entries on backtest replays) and dedups on (date, ticker, window, time, score); new heartbeat log (`scanner_heartbeat.jsonl`, configurable via `SCANNER_HEARTBEAT_LOG`) records each scan tick with status / candidates / duration so EOD can distinguish a stalled scanner from a quiet market — wired into `eod_dump.py` analysis prompts. |
| 2026-05-12 | New Market Context First (MCF) Funnel Scanner added alongside Dip Scanner. Separate `/mcf` dashboard. Uses 3-layer checking logic with SPY/QQQ/IWM/DIA to predict entries with ~1% targets. DB caching implemented to avoid `yfinance` rate limits. |
| 2026-05-12 | Docs sweep: rewrote SEC:DIP_SCANNER (features.md) for current scanner reality — 4 signal types (incl. failed_breakdown), ATR-based stops/targets, regime gate, time stop, dedup, fmd backfill, near-miss logging, AI signal analysis; SEC:DIP_SCANNER_ROUTES (api.md) adds /similar /ticker-history /analyze /chart routes; SEC:DB_MODELS (architecture.md) adds full ScannerAlert schema with signal_type + five_min_direction + resolved_by; new docs/rules.md codifies operating rules (docs discipline, git workflow, code conventions, TZ) + tracks known doc debt; CLAUDE.md gains Critical Rule #8 referencing rules.md |
| 2026-05-08 | Scanner quality sprint (Opus ideas #3,#4,#6,#16,#21,#30): hammer weight +15→+5 with stricter volume+wick definition; VIX slope scoring replaces VIX level (rising VIX = -10, falling = +12); hard lunch block score<80; WHITELIST_CELLS scaffold (disabled, enable at n≥5/cell); invalidation field in signal payload (price_close_below/vix_above/rvol_resurge); frontend "Risk $X → Make $Y" as primary P&L; invalidation line below chart |
