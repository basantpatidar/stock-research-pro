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
| Cache strategy (Redis TTLs) | docs/architecture.md | `SEC:CACHE` |
| Database models | docs/architecture.md | `SEC:DB_MODELS` |
| Project directory map | docs/architecture.md | `SEC:DIR_MAP` |
| V1 API routes | docs/api.md | `SEC:V1_ROUTES` |
| V2 tiered routes | docs/api.md | `SEC:V2_ROUTES` |
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

---

## Recent Changes

| Date | Change |
|---|---|
| 2025-04-27 | Fix SSE stream: unwrap LangGraph node output before reading messages |
| 2025-04-27 | Create `api/research_v2.py` + `api/usage.py` — were missing, caused 404s |
| 2025-04-27 | Fix news panel hang: pass `company_name` from tier1 to skip yfinance lookup |
| 2025-04-27 | Add `asyncio.wait_for` timeout (25 s tier2, 90 s tier3) against infinite hangs |
| 2025-04-27 | Fix `ExpandablePanel`: fire `onExpand` on mount when panel starts auto-expanded |
| 2025-04-27 | Resolve merge conflict in `research.py` — kept thread+queue SSE pattern |
