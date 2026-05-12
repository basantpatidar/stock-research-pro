# docs/rules.md — Operating rules for any change in this repo
# Sections: grep -n "SEC:" docs/rules.md
# SEC:DOCS         Docs-update discipline — when and how to update docs/
# SEC:GIT          Branching, commit hygiene, PR cadence
# SEC:CODE         Code-level rules that complement CLAUDE.md Critical Rules
# SEC:TIMEZONE     Timezone storage and display convention
# SEC:DOC_DEBT     Known stale docs / tracking list
# SEC:CHANGELOG    How to grow this file

This doc is the single place to look up "what am I supposed to do for X?"
Every rule has a **Why** and a **How to apply** so judgment calls work, not just blind compliance.
CLAUDE.md links here from its Critical Rules section.

---

<!-- SEC:DOCS -->
## Docs-update discipline

### Rule 1 — Every code change updates the relevant `docs/` file in the same commit / PR
**Why:** Docs that drift become noise. The user has called out twice this week that docs are stale; the cost is real (LLMs read stale docs and recommend wrong things; new contributors get false mental models).
**How to apply:**
- A new tool → `docs/tools.md` SEC:V1_TOOLS or SEC:V2_TOOLS row added in the same commit
- A new API route → `docs/api.md` under the matching SEC: anchor in the same commit
- A new frontend page → `docs/frontend.md` SEC:PAGES
- A new DB column / model → `docs/architecture.md` SEC:DB_MODELS
- A new env var → `docs/dev.md` SEC:ENV_VARS
- A new feature gate / guard rail / scoring rule → `docs/features.md` under the relevant section
- A new operating rule → this file (`docs/rules.md`) under the right SEC

### Rule 2 — Always add a row to CLAUDE.md "Recent Changes" for any user-visible change
**Why:** It's the breadcrumb trail that gives an incoming session 30 seconds of context on what shipped recently.
**How to apply:** One row, dated. Lead with the *what* (one phrase), follow with the *where* (file paths the user can grep for).

### Rule 3 — Never `Read` a full `docs/*.md` file
**Why:** Each ~250-line doc burns ~2k tokens; the SEC: index makes targeted reads cheap.
**How to apply:** `grep -n "SEC:ANCHOR" docs/file.md` → `Read` with `offset` + `limit` covering only that section. Mirrored in CLAUDE.md Critical Rule #7.

### Rule 4 — Personal planning docs do not ship
**Why:** Sprint notes, brainstorms, critiques, and todo files clutter the repo and confuse future readers about what's authoritative.
**How to apply:** Drop them in `local_debugging/` (already gitignored) **or** name them with one of the patterns in `.gitignore` (`docs/*-sprint.md`, `docs/*_critique*.md`, `docs/*_proposal*.md`, `docs/*_philosophy*.md`, `docs/*_strategy*.md`). Project docs that genuinely help a developer understand the codebase stay tracked.

---

<!-- SEC:GIT -->
## Git workflow

### Rule 5 — One branch + PR per sprint, no exceptions
**Why:** Stacked uncommitted work compounds; reverting becomes painful; PR review gets diluted.
**How to apply:** New sprint = new branch off `origin/main` (or off the parent feature branch if explicitly stacking). Open the PR before starting the next sprint.

### Rule 6 — Never add Co-Authored-By / AI attribution / "Generated with" trailers
**Why:** Work appears entirely as the user's own. This is a hard preference.
**How to apply:** No `Co-Authored-By: Claude`, no "🤖 Generated with Claude Code" footers, no mentions of Claude / Anthropic / AI in commits, PR bodies, file content, comments, or docstrings.

### Rule 7 — Atomic commits per concern
**Why:** Easier to review, easier to revert, easier to cherry-pick if a single piece breaks.
**How to apply:** If two unrelated changes land in the same file, prefer two commits. If `git add -p` isn't available (non-interactive), it's acceptable to bundle when the changes share a function and a bug-fix concern; document the bundling in the commit message.

### Rule 8 — Surgical commits when other unstaged work shares the file
**Why:** A naïve `git add CLAUDE.md` sweeps in 4 days of accumulated edits that belong on other branches.
**How to apply:** Backup the file → `git checkout HEAD -- file` → re-apply only the in-scope change → commit → restore the backup. The other accumulated edits stay in the working tree for their proper branches.

### Rule 9 — Never push or open PRs without explicit ask (unless Rule 5 implies it)
**Why:** Push is shared-state; force-push and PR creation are visible to others. Authorization is bounded.
**How to apply:** "Commit" means commit; "push" or "open PR" requires its own go-ahead, except when Rule 5's per-sprint cadence already implies it (and even then, flag what you're about to do in chat first).

---

<!-- SEC:CODE -->
## Code conventions (complements CLAUDE.md Critical Rules)

### Rule 10 — No comments unless they explain *why*
**Why:** Well-named code self-documents the *what*. Comments explaining *what* go stale; comments explaining *why* (constraint, invariant, workaround for a specific bug) age well.
**How to apply:** If removing the comment wouldn't confuse a future reader, don't write it. Don't reference "added for the X flow" — those rot.

### Rule 11 — No backwards-compatibility shims unless explicitly required
**Why:** Hidden state and dead code paths accumulate. Rename / delete / change confidently.
**How to apply:** Don't keep `_legacy_foo` aliases, don't add feature flags for "in case someone needs the old behavior". If you're certain something is unused, delete it.

### Rule 12 — Validate at boundaries only
**Why:** Internal-internal validation is noise that obscures real risk.
**How to apply:** Validate user input, external API responses, file inputs. Trust internal function calls and framework guarantees.

---

<!-- SEC:TIMEZONE -->
## Timezone convention

### Rule 13 — Store as `timestamptz`, present in ET
**Why:** Storage as absolute UTC moments avoids DST ambiguity (1:30 AM happens twice in November; 2:30 AM doesn't exist in March). The app's audience and market data are all NYSE-aligned, so display should be ET.
**How to apply:**
- DB columns: `DateTime(timezone=True)` (PostgreSQL `timestamptz`). Never naive `timestamp`.
- Backend container: `TZ=America/New_York` in docker-compose so logs / `datetime.now()` / serialized timestamps render as ET.
- SQL display: `entry_time AT TIME ZONE 'America/New_York'` when fetching for human consumption.
- Python display: convert with `.astimezone(ZoneInfo("America/New_York"))` at the rendering boundary.
- Boundary inputs (yfinance, NewsAPI): they return tz-aware UTC; pass through unchanged into `timestamptz` columns.

---

<!-- SEC:DOC_DEBT -->
## Known doc debt (track here so it doesn't get lost)

These are gaps surfaced during the 2026-05-12 docs audit. Address opportunistically — when touching the relevant code, sweep the doc with it.

| Doc | Gap | Owner / when |
|---|---|---|
| `docs/tools.md` SEC:V1_TOOLS | Catalog says "24 tools" but ~15 newer ones missing: `canslim`, `dividend`, `edgar_fundamentals`, `edgar_risk_factors`, `economic_calendar`, `fear_greed`, `gap_scanner`, `guru_tracker`, `market_breadth`, `moat`, `patterns`, `pretrade_score`, `regime`, `seasonality`, `smart_money`, `valuation`, `volatility_forecast` | Next sprint that touches any of these tools |
| `docs/frontend.md` SEC:PAGES | Missing `DashboardPage`, recent scanner card revamps, `ManualTradeLog` | Next frontend sprint |
| `docs/frontend.md` SEC:COMPONENTS | Missing `TickerHistoryModal`, scanner pretrade-checklist modal, `WeeklyTargetBar`, `SituationSummary`, scenario guidance, etc. | Same |
| `docs/architecture.md` SEC:DIR_MAP | May be stale — last verified 2026-05-02 | Quick scan once per month |
| `docs/dev.md` SEC:ENV_VARS | Missing newer env vars (TZ, USAGE_FILE, NEAR_MISS_LOG, possibly others) | Add when touched |
| `docs/dev.md` SEC:ADD_FEATURE | Doesn't mention `docs/rules.md` — should reference Rule 1 (docs in same commit) | Quick add |
| `docs/api.md` SEC:USAGE_ROUTES | Verify reflects current `/usage/` shape | Quick scan |

---

<!-- SEC:CHANGELOG -->
## How to grow this file

When the user gives me a new operating rule, or when a recurring failure mode emerges:

1. Add a numbered rule under the most relevant SEC: anchor (or create a new SEC: if the topic is genuinely new).
2. Always include **Why** (the reason — usually a past incident or strong preference) and **How to apply** (when/where this kicks in).
3. Update CLAUDE.md Critical Rules if the rule is hot enough to surface there too.
4. Add a one-line entry to CLAUDE.md Recent Changes naming the rule.
5. Update the doc-debt table above if a known gap is being closed.

Rules already promoted to CLAUDE.md Critical Rules: 1 (docs update), 3 (no full doc reads), 6 (no AI attribution).
