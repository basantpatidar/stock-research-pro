# docs/trading.md — Order execution: paper trading only (live not on roadmap)
# Sections: grep -n "SEC:" docs/trading.md

**Doc version:** 1.0 · **Last updated:** 2026-05-14

# SEC:GOALS            What this initiative covers and what it explicitly does NOT
# SEC:PHASES           Three-phase delivery plan with exit criteria per phase (paper only — live is not on the roadmap)
# SEC:ARCH             Broker factory pattern — mirrors LLM factory shape
# SEC:BROKER_PROVIDERS Per-provider notes (Alpaca first, others later)
# SEC:DATA_MODEL       BrokerOrder + position snapshots — local source of truth
# SEC:ROUTES           API routes (/broker/*)
# SEC:FRONTEND         Pages, components, store changes
# SEC:RISK             Risk gates — position sizing, daily-loss cap, live-mode confirmations
# SEC:ENV              Env vars (BROKER, BROKER_MODE, ALPACA_*, risk limits)
# SEC:TESTING          How to verify paper trading end-to-end before flipping to live

---

<!-- SEC:GOALS -->
## Goals

Add **paper-money order execution** to the app — simulate buy/sell of US-listed equities/ETFs from inside the existing scanner workflow so we can measure whether the scanner's signals are profitable. The whole initiative is paper-only by design: the goal is signal validation, not capital deployment.

**In scope (this initiative):**
- A broker-agnostic order layer (`backend/app/brokers/`) that mirrors the LLM factory pattern — swap providers via `BROKER` env, no code changes.
- Alpaca paper sandbox as the first (and for now, only) provider. Free, no real capital ever at risk.
- Local persistence of every order we submit, independent of broker uptime.
- Manual order placement from the scanner card and a portfolio page.
- Auto-paper-trade subscriber that converts scanner alerts into bracket orders — the validation harness for the scanner.
- Risk gates that mirror live-mode safeguards (per-order cap, per-day loss cap, daily order count cap) even though paper money can't actually be lost — the caps exist so the *behaviour* generalises if we ever change our mind later.

**Explicitly out of scope (not planned, not on the roadmap):**
- Live trading. The code path exists (`BROKER_MODE=live`) and the broker layer supports it, but **no sprint is planned for it**. We will not plan or scope live trading until paper P&L is clearly and convincingly profitable, and even then it will be a separate explicit decision — not a default next step.
- Margin, shorts, options strategies.
- Order routing optimisation. Whatever Alpaca's smart router does is fine.
- Multi-account / per-user accounts. Single broker account, single API key.

**Why Alpaca:**
- Free paper sandbox with realistic fills against a $100k simulated account.
- Library: [`alpaca-py`](https://github.com/alpacahq/alpaca-py).
- Already-built websocket trade-updates stream — drops into our existing alert infra later.

---

<!-- SEC:PHASES -->
## Phases

| Phase | Deliverable | Exit criteria | Branch |
|---|---|---|---|
| **1 — Foundation** ✅ | Broker factory + BaseBroker interface + Alpaca client + `GET /broker/account` smoke test + `BrokerOrder` model | `curl /broker/account` returns paper account equity/buying_power; no UI yet | `feat/trading-foundation` |
| **2 — Manual paper trading** ✅ | `POST /broker/orders` + portfolio page (positions + open orders + recent fills) + "Buy/Sell" button on scanner card → confirm modal → submit + "New Order" button on portfolio page | A trade placed from the UI shows up in the portfolio page and in Alpaca's paper dashboard with matching qty/avg_price | `feat/trading-foundation` |
| **3 — Auto-paper-trade (validation harness)** 🔧 | `services/trading/auto_trade.py` subscriber polls `scanner_alerts`, converts each into a bracket paper order through the **same** risk caps the manual route uses. Per-signal-type allowlist (`AUTO_TRADE_SIGNAL_TYPES`); off by default. Scanner halts for the day once `SCANNER_DAILY_SIGNAL_CAP` is hit. Status panel on `/portfolio`. | 4+ weeks of unbiased paper P&L per signal_type, captured on `/portfolio` + DB. The data tells us which signals are profitable — it does NOT imply a follow-on "go live" phase. | `feat/trading-auto` |

Each phase ships as one branch + one PR ([[docs/rules.md]] Rule 5). Phase 3 work is uncommitted in the working tree as of 2026-05-14 — see `local_debugging/push_plan.md`.

**There is no Phase 4 on the roadmap.** Live trading is intentionally not planned. The `BROKER_MODE=live` code path exists (paper/live are mostly the same Alpaca REST surface) but turning it on is a separate, explicit, future decision — not a scheduled sprint. We will only consider it after sustained, repeatedly-verified paper profitability, and even then it would warrant its own design review, not just a phase rollover.

**Why Phase 3 is the whole point:** if a human clicks every trade, the resulting P&L reflects the human's selection bias, not the strategy. The auto-trade subscriber takes every signal in the allowlist so the dataset is unbiased. Paper money makes this safe.

---

<!-- SEC:ARCH -->
## Architecture — Broker Factory

Mirrors `backend/app/llm/factory.py` exactly:

```
backend/app/brokers/
├── __init__.py
├── base.py        # BaseBroker abstract class + Pydantic DTOs
├── alpaca.py      # Alpaca implementation
└── factory.py     # get_broker(settings) → BaseBroker
```

`get_broker(settings)` reads `settings.broker` (default `alpaca`) and `settings.broker_mode` (default `paper`) and returns an instance. To add a new broker (IBKR, Schwab):
1. Create `backend/app/brokers/<name>.py` implementing `BaseBroker`.
2. Wire it into `factory.get_broker()`.
3. Document credential env vars in [[SEC:ENV]].

**BaseBroker interface** (`base.py`):

| Method | Returns | Notes |
|---|---|---|
| `get_account()` | `AccountInfo` | cash, buying_power, equity, daytrade_count |
| `get_positions()` | `list[Position]` | symbol, qty, avg_entry, market_value, unrealized_pl |
| `get_orders(status, limit)` | `list[Order]` | open / all / closed |
| `get_order(order_id)` | `Order` | single order lookup |
| `place_order(req: PlaceOrderRequest)` | `Order` | market/limit/stop, time_in_force, optional bracket (stop_loss + take_profit) |
| `cancel_order(order_id)` | `None` | best-effort; silently succeeds if already filled |
| `is_market_open()` | `bool` | broker's clock — don't compute locally |

**Failure semantics:** unlike scanner tools, broker methods **raise** typed exceptions (`BrokerError`, `BrokerRejected`, `BrokerUnreachable`). The order placement path needs structured error handling at the API layer, not silent `{"error": "..."}` dicts. This is the only place in the codebase where Critical Rule #1 (tools never raise) does not apply — and the rule explicitly scopes itself to `@tool`-decorated functions, which broker methods are not.

**DTOs (Pydantic):**
- `AccountInfo`, `Position`, `Order`, `PlaceOrderRequest` — defined in `base.py`, broker-agnostic. Each provider implementation converts its native types to these.

---

<!-- SEC:BROKER_PROVIDERS -->
## Broker Providers

### Alpaca (Phase 1+)

| Env var | Required? | Notes |
|---|---|---|
| `BROKER` | yes — default `alpaca` | provider selector |
| `BROKER_MODE` | yes — default `paper` | `paper` or `live` |
| `ALPACA_API_KEY` | yes | paper key for `paper` mode, live key for `live` mode |
| `ALPACA_API_SECRET` | yes | secret matching the key |
| `ALPACA_BASE_URL` | optional | auto-selects `https://paper-api.alpaca.markets` vs `https://api.alpaca.markets` based on `BROKER_MODE`. Override only for sandbox testing. |

Paper and live keys are **different** — Alpaca isolates them. Switching `BROKER_MODE` without rotating keys will fail with `403 unauthorized`. Surface this as a clear error message on startup, not a stack trace.

### Future providers
- **IBKR** — would need their Python `ib_insync` client; account model is richer (multi-currency, futures, options chains). Defer until requested.
- **Schwab** — public API exists but requires OAuth dance per user; not worth the complexity for a single-account app.

---

<!-- SEC:DATA_MODEL -->
## Data Model

We persist a **local snapshot of every order we submit** so the UI never blocks on Alpaca being up, and so historical P&L analysis doesn't depend on Alpaca's retention.

**New model:** `BrokerOrder` (in `backend/app/db/models.py`). See [[docs/architecture.md]] SEC:DB_MODELS for the canonical model index.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `broker` | str | `alpaca` etc. |
| `broker_order_id` | str, indexed, unique | broker's id; nullable until first response |
| `mode` | str | `paper` or `live` at the time of submission — frozen for audit |
| `symbol` | str | |
| `side` | str | `buy` / `sell` |
| `qty` | float | whole shares only at first; float reserved for fractional later |
| `order_type` | str | `market` / `limit` / `stop` |
| `limit_price` | float? | |
| `stop_price` | float? | bracket-order stop |
| `take_profit_price` | float? | bracket-order target |
| `time_in_force` | str | `day` / `gtc` / `ioc` / `fok` |
| `status` | str, indexed | `new` / `accepted` / `partially_filled` / `filled` / `canceled` / `rejected` / `expired` |
| `filled_qty` | float | |
| `filled_avg_price` | float? | |
| `submitted_at` | timestamptz | server-side, see [[docs/rules.md]] SEC:TIMEZONE |
| `filled_at` | timestamptz? | |
| `canceled_at` | timestamptz? | |
| `rejected_reason` | str? | |
| `source` | str | `manual` / `scanner_alert` |
| `scanner_alert_id` | UUID? | FK-style link to `scanner_alerts.id` when source = `scanner_alert` |
| `client_order_id` | str, unique | UUID we generate so retries are idempotent on Alpaca's side |

**Why a local copy:** the alternative is "ask Alpaca every time". That couples our UI uptime to Alpaca uptime, fails when their websocket lags, and makes backtesting against historical orders impossible. A periodic sync job (Phase 2) keeps `status`/`filled_qty`/`filled_avg_price` fresh.

Positions are **not** persisted — they're a derived view from filled orders, and Alpaca's `/positions` is authoritative for market value. Cache the snapshot in Redis for 30s.

---

<!-- SEC:ROUTES -->
## API Routes

All under `/broker/*`, gated by the existing API-key middleware ([[docs/api.md]] SEC:AUTH). New routes also surface in [[docs/api.md]] under a new SEC:BROKER_ROUTES anchor.

| Method | Path | Phase | Notes |
|---|---|---|---|
| GET | `/broker/account` | 1 | broker, mode, buying_power, cash, equity, daytrade_count — smoke test |
| GET | `/broker/positions` | 2 | list[Position] from broker, 30s redis cache |
| GET | `/broker/orders?status=open\|all\|closed&limit=50` | 2 | merges local BrokerOrder rows with broker's current status |
| POST | `/broker/orders` | 2 | place an order; body = PlaceOrderRequest |
| GET | `/broker/orders/{order_id}` | 2 | single order lookup |
| DELETE | `/broker/orders/{order_id}` | 2 | cancel best-effort |
| GET | `/broker/clock` | 2 | is_market_open + next open/close — used by the UI to disable buy buttons |
| WS | `/broker/ws` | 2 | optional — relay Alpaca's trade-update websocket so the UI updates without polling. Defer if 2-3s polling is good enough. |

All endpoints raise HTTP 503 with `X-Broker-Status: unreachable` if the broker is down — frontend shows a banner instead of a blank UI.

---

<!-- SEC:FRONTEND -->
## Frontend

**New page:** `/portfolio` (Phase 2). Sections, top to bottom:
1. **Account header** — mode pill (PAPER / LIVE), equity, buying_power, day P&L.
2. **Open positions table** — symbol, qty, avg entry, current price, unrealized P&L $, unrealized P&L %, [Close] button.
3. **Open orders table** — symbol, side, qty, type, limit, status, submitted_at, [Cancel] button.
4. **Recent fills (last 50)** — read-only, sortable.

**New components:**
- `OrderTicketModal.tsx` — buy/sell form. Symbol, side, qty (or $ amount → shares math), order type, optional bracket (stop/target). Live mode shows a typed-confirmation gate ("type BUY 10 SPY to confirm").
- `BrokerStatusBadge.tsx` — top-nav indicator. Shows broker + mode + connectivity. Click → /portfolio.

**Existing component changes:**
- `DipScannerCard.tsx` (Phase 2) — add a "Trade this signal" button that pre-fills `OrderTicketModal` with the scanner's entry/stop/target. Stays a manual click — no auto-fire until Phase 3.

**Store additions** ([[docs/frontend.md]] SEC:STORE):
```ts
brokerMode: 'paper' | 'live' | null
accountEquity: number | null
positions: Position[]
openOrders: Order[]
```

[[docs/frontend.md]] gets a new SEC:PORTFOLIO_PAGE anchor describing the page layout.

---

<!-- SEC:RISK -->
## Risk Gates

Risk is the difference between a side project and a margin call. Every gate below is **non-bypassable in code** — `BROKER_MODE=live` does not silently relax them.

**Per-order caps** (limits.py, mirrors SEC:GUARD_RAILS pattern):

| Gate | Default | Env var | Behavior |
|---|---|---|---|
| Max order notional | $2,000 | `TRADE_MAX_ORDER_DOLLARS` | order rejected before submit if `qty * price > limit` |
| Max position per symbol | $5,000 | `TRADE_MAX_POSITION_DOLLARS` | rejected if existing position + new order would exceed |
| Daily realized loss cap | -$200 | `TRADE_DAILY_LOSS_CAP_DOLLARS` | once today's realized PnL ≤ this, all new buy orders blocked until midnight ET |
| Daily order count cap | 20 | `TRADE_DAILY_ORDER_COUNT_CAP` | guards against runaway auto-trade loops |
| Live-mode typed confirmation | always on | n/a | live submissions require the typed string to match an expected token (`BUY 10 SPY`) — kills fat-finger |

**Where caps live:** `backend/app/services/trading/limits.py` — same pattern as `services/usage/limits.py` ([[docs/features.md]] SEC:GUARD_RAILS Critical Rule #6 in [[CLAUDE.md]]).

**Pre-live checklist** (must all be true before flipping `BROKER_MODE=live`):
- [ ] 4+ weeks of paper trading with positive expectancy on this account
- [ ] Daily-loss cap has triggered at least once and behaved correctly
- [ ] Order placement, cancellation, and partial-fill UI verified manually
- [ ] Account is funded with money you'd be OK losing entirely
- [ ] Two-factor on the Alpaca account
- [ ] `ALPACA_API_KEY` and `ALPACA_API_SECRET` rotated to live-mode keys
- [ ] All three risk-cap env vars set to your live limits (not paper defaults)

---

<!-- SEC:ENV -->
## Environment Variables

Add to `.env.example` and document in [[docs/dev.md]] SEC:ENV_VARS:

```bash
# Broker — paper trading first, flip mode to "live" after sign-off
BROKER=alpaca                      # alpaca | ... (future: ibkr, schwab)
BROKER_MODE=paper                  # paper | live — different keys per mode
ALPACA_API_KEY=                    # https://app.alpaca.markets/paper/dashboard/overview
ALPACA_API_SECRET=
ALPACA_BASE_URL=                   # optional — auto-resolved from BROKER_MODE if blank

# Trading risk caps — enforced server-side, not bypassable by frontend
TRADE_MAX_ORDER_DOLLARS=2000
TRADE_MAX_POSITION_DOLLARS=5000
TRADE_DAILY_LOSS_CAP_DOLLARS=-200
TRADE_DAILY_ORDER_COUNT_CAP=20

# Auto-trade — off until Phase 3 sign-off; even then, gated per signal type
AUTO_TRADE_ENABLED=false
AUTO_TRADE_SIGNAL_TYPES=           # comma-separated allowlist, empty = none
```

---

<!-- SEC:TESTING -->
## Testing

**Phase 1 smoke test** (no UI yet):
```bash
make up
# put paper keys in .env
curl -H "X-API-Key: $API_KEY" http://localhost:8000/broker/account
# expect: {"broker":"alpaca","mode":"paper","equity":100000,"buying_power":100000,...}
```

**Phase 2 manual paper-trade test:**
1. Place a $100 SPY buy from the UI.
2. Confirm BrokerOrder row appears in `scanner_alerts` / `broker_orders` with `mode=paper`.
3. Confirm the order appears in Alpaca's paper dashboard at https://app.alpaca.markets/paper.
4. Confirm /portfolio reflects the fill within 30s.
5. Cancel an open limit order; confirm both UI and Alpaca dashboard reflect cancellation.

**Pytest** ([[docs/dev.md]] SEC:TESTING):
- `tests/brokers/test_alpaca.py` — mock `alpaca-py` client; assert order request shape, error mapping.
- `tests/api/test_broker.py` — uses the existing test client; mocks `get_broker()` to return a fake. **No real Alpaca calls in CI** — same rule as yfinance ([[docs/dev.md]] SEC:TESTING).

**Manual end-to-end (do not automate):**
The pre-live checklist in [[SEC:RISK]] is a one-time human gate before flipping `BROKER_MODE=live`. Do not script this; the friction is the safety.
