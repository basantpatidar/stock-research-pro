# docs/frontend.md — Pages, components, Zustand store, hooks, key types
# Sections: grep -n "SEC:" docs/frontend.md

**Doc version:** 1.0 · **Last updated:** 2026-05-14

# SEC:PAGES       Page components and their responsibilities
# SEC:COMPONENTS  Key shared + research components
# SEC:PORTFOLIO_PAGE  Portfolio page + order ticket modal + broker status badge
# SEC:STORE       Zustand store shape
# SEC:HOOKS       Custom hooks
# SEC:TYPES       Core TypeScript interfaces (abbreviated)
# SEC:THEME       Theme tokens (T.xxx)

---

<!-- SEC:PAGES -->
## Pages (`frontend/src/pages/`)

| Page | Route | Responsibility |
|---|---|---|
| `ResearchPage.tsx` | `/` | Ticker search → tier1 data + expandable T2/T3 panels |
| `WatchlistPage.tsx` | `/watchlist` | Live signals table + alert feed |
| `ScreenerPage.tsx` | `/screener` | Filter builder + results + preset management |
| `MacroPage.tsx` | `/macro` | Sector heatmap + geopolitical events + macro indicators + FRED Credit & Rates Dashboard |
| `UsagePage.tsx` | `/usage` | Token usage chart (30d) + guard-rail limits table |
| `DashboardPage.tsx` | `/dashboard` | Market pulse, top movers, sector rotation grid, Weekly P&L bar, Daily Target Trade Scanner (DipScannerCard + ScannerPerformanceCard) |
| `PortfolioPage.tsx` | `/portfolio` | Broker account header, open positions, open orders, recent fills. Polls `/broker/*` every 10s. See SEC:PORTFOLIO_PAGE. |

**ResearchPage flow:**
1. User enters ticker → `runSearch()` fires simultaneously:
   - `startResearch(sym, mode)` → starts V1 SSE stream for agent reasoning
   - `researchV2.tier1(sym, mode, execMode)` → fetches structured data
2. T1 data renders immediately (Price Chart, OHLCV, Technicals, News, + mode-specific panels)
3. T2 panels are collapsed; user clicks to load (filtered by mode)
4. T3 panels require explicit click (filtered by mode)
5. In `deep` exec mode: T2 panels auto-expand AND auto-load on mount via `ExpandablePanel` `useEffect`

**Mode-aware panel filtering** (`show(modes, currentMode)` helper):
- `day_trade`: Options Intelligence, Risk/Reward, Short Interest, Sentiment, Convergence, Forecast, Backtester, Bull/Bear, Paper Trade
- `long_term`: Analyst Consensus, Earnings History, Fundamentals, Earnings Quality, Congressional, Sentiment, Convergence, Forecast, Investor Personas, Earnings Transcript, Bull/Bear
- `both`: all panels shown; day trade panels first
- A "MODE VIEW" badge appears when a filter is active, with a link to switch to Both mode
- Price chart default period: `1d` for day_trade, `3M` for long_term

---

<!-- SEC:COMPONENTS -->
## Key Components

### Shared (`frontend/src/components/shared/`)

**`ExpandablePanel.tsx`**
Props: `title`, `tier: 1|2|3`, `estimatedTokens?`, `loading`, `error`, `onExpand?`, `children`, `autoExpand?`
- Tier badge (T1 green / T2 blue / T3 purple)
- Shows token estimate when collapsed
- `shouldAutoExpand = autoExpand || tier===1 || (tier===2 && execMode==="deep")`
- When starting pre-opened (auto-expand), fires `onExpand` once on mount via `useRef` guard
- Body states: loading text → error (red) → children (content)
- In `saver` mode: T2/T3 buttons are disabled

**`ExecModeBar.tsx`** — Saver / Normal / Deep toggle + session token counter

**`ModeToggle.tsx`** — Day Trade / Long Term / Both toggle

**Top-nav usage pills** (inline in `App.tsx`, not a separate component)
Two live pills in the top-right of the nav showing `% tokens` and `% api` today, polled from `GET /usage/today` every 30 s. Colour tiers: green <50%, amber 50–79%, red ≥80% (matches backend `warning` thresholds). Hidden when count is zero so the nav stays clean before any usage accumulates. Hover tooltip shows the raw `count / limit`. Replaced the older `tokenCount`-from-store derivation so the pill reflects what's *actually* counted against the daily cap, not what the frontend session has locally accumulated.

### Research (`frontend/src/components/research/`)

**`PriceChart.tsx`** — Recharts area chart from `tier1.price.price_history`. Props: `data: PriceData`, `defaultPeriod?: Period` (default `"1d"`). On multi-day periods, overlays volume profile reference lines: VPOC (amber dashed), VAH (green dashed), VAL (red dashed) from `tier1.price.volume_profile`. Intraday (1d) uses 5-min candles with pre/after-market data; VP overlay hidden for intraday.
**`SignalScore.tsx`** — Convergence score 0-100 with label and signal breakdown
**`NewsPanel.tsx`** — News items with sentiment badges (POSITIVE/NEGATIVE/NEUTRAL)
**`StreamPanel.tsx`** — SSE event stream renderer (tool_call → tool_result → reasoning)
**`InvestorPersonasPanel.tsx`** — 5 investor persona verdict cards
**`EarningsHistoryPanel.tsx`** — Quarter-by-quarter earnings cards. Collapsed header shows Est (eps_estimate, muted) + EPS (eps_actual) side-by-side, beat/miss pill, surprise %. Expanded detail shows full EPS card + revenue card.
**`EarningsQualityPanel.tsx`** — 4-model institutional earnings quality analysis: Piotroski F-Score, Beneish M-Score, Altman Z-Score, Accruals Ratio. Each metric shows a direct verdict badge + score + plain-English explanation.
**`OptionsIntelligencePanel.tsx`** — Institutional-grade options signals: GEX, max pain, IV analysis, put/call skew, vol term structure. All computed from free yfinance data. Each metric shows verdict + signal.
**`Tier3Panels.tsx`** — BullBearPanel, BacktesterPanel, CongressionalPanel, EarningsTranscriptPanel, PaperTradePanel

### Daily Target Trade Scanner (`frontend/src/components/`)

**`DipScannerCard.tsx`**
Main scanner card on DashboardPage. Features:
- Capital input (localStorage key `dts_capital`, default $1,000) + Tier 1/2 toggle
- `SituationSummary` rendered between controls and opportunity card — idle shows "Ready to scan" (expanded), post-scan shows scenario-matched guidance (compact, collapsible)
- VIX spike prep amber banner when `result.vix_spike_prep` is non-null
- Opportunity card: signal-type badge (ORB Breakout / VWAP Reclaim; hidden for plain dip_buy), left-border color follows signal type, entry/target/stop grid, P&L row, signal chips with hover hints
- "Explain this setup" button — disabled in saver mode, ~200 tokens via tier2 API
- Other setups row: all signal types (dip_buy + orb + vwap) with type label + score chip

**`ScannerPerformanceCard.tsx`**
Analytics card on DashboardPage. Features:
- Win rate, expected value/trade, current streak
- SVG cumulative P&L line chart (chronological from analytics endpoint)
- By-ETF and by-session-window mini breakdowns
- Recent 20 alerts table with LIVE / BACKTEST source labels
- "Seed 60-day history" button → `POST /dip-scanner/backfill`
- "Gathering data" note shown until ≥ 30 resolved signals

**`SituationSummary.tsx`**
Props: `scenarioKey: string|null`, `compact?: boolean`
Looks up `scenarioKey` in `scenarios.json`. Falls back to `"waiting"` for unknown keys.
Renders: left-border + background tinted by scenario type, label badge (`BUY SIGNAL` / `STAND BY` / `PREPARE` / `SELL SIGNAL` / `HOLD`), headline, expandable body with summary, action, risk note.
`compact=true`: body hidden by default, click headline to toggle.

**`WeeklyTargetBar.tsx`**
Placed above scanner grid on DashboardPage. Features:
- Progress bar: `pnl / target × 100%`, color green (hit) / blue (positive) / red (negative)
- Inline-editable weekly target (click dashed underline → input, localStorage key `dts_weekly_target`, default $150)
- Wins / losses count, "TARGET HIT" badge when goal reached
- Day-by-day P&L: Mon–Fri columns, green/red per day
- Data from `GET /dip-scanner/weekly`

---

<!-- SEC:PORTFOLIO_PAGE -->
## Portfolio Page + Trading Components

The `/portfolio` page, `OrderTicketModal`, `BrokerStatusBadge`,
`AutoTradePanel`, and `PortfolioRiskPanel` together implement Phases 2 + 3
of the broker integration (see `docs/trading.md` SEC:PHASES). Phase 1 was
the backend factory + smoke route; Phase 3 layers auto-paper-trade onto
the manual trading UI behind a feature flag. **Live trading is not on the
roadmap** — the `BROKER_MODE=live` path exists in code but no sprint is
planned for it.

### `pages/PortfolioPage.tsx`
Layout, top to bottom:
1. **Header** — page title, mode pill (`PAPER` amber / `LIVE` red), `+ New Order` button (opens blank `OrderTicketModal`; disabled when `brokerStatus !== 'ok'`), manual refresh button.
2. **Auto-trade status banner** (`AutoTradePanel`) — Phase 3. Reads `GET /broker/auto-trade/status` and shows: enabled state, allowlist, orders today / cap, signals today / cap, scanner-halted flag, last auto order. Colour: grey when off, amber when enabled-with-empty-allowlist, green when armed, red when the scanner has halted for the day.
3. **Account stat strip** — equity, buying power, cash, day P&L (`account.equity - account.last_equity`).
4. **Risk panel** (`PortfolioRiskPanel`) — Phase 3 read-only view. 4 stat cards (total exposure, position count + largest weight, max loss if all stops hit, uncovered positions) + per-symbol table with weight %, market value, stop price, max loss to that stop. Warns at ≥40% concentration on a single position or any position without a sell-stop. Pure client-side compute over the positions + open orders the page already fetches — no extra endpoint.
5. **Open positions table** — symbol, qty, avg entry, current price, market value, unrealized P&L $/%. Inline `[Close]` button → opens `OrderTicketModal` pre-filled as a sell at current qty.
6. **Open orders table** — symbol, side (color-coded), qty, type, limit, status, submitted_at. Inline `[Cancel]` button → `DELETE /broker/orders/{id}`.
7. **Recent fills table** — last 50 filled orders, read-only.

Polls all five broker endpoints (account, positions, orders open, orders
closed, auto-trade status) in parallel every 10 s via `Promise.all`. On
HTTP 503, reads the `X-Broker-Status` header to distinguish `unreachable`
(red banner — try again later) from `misconfigured` (amber banner — set
`ALPACA_API_KEY` in `.env`). Existing rows stay visible during an outage —
the page never blanks out.

### `components/trading/OrderTicketModal.tsx`
Props: `prefill: TicketPrefill`, `onClose`, `onPlaced`. Self-contained modal
that overlays any page. Behaviour:
- **Qty mode toggle**: `shares` or `$`. Dollar mode auto-computes whole shares once a limit price is set (`Math.floor(dollars / limit_price)`).
- **Bracket checkbox**: when enabled, the body includes `stop_price` + `take_profit_price` so a bracket order is submitted in one round-trip.
- **Live-mode confirmation**: when `brokerAccount.mode === 'live'`, an extra row appears with the exact string the backend expects (`"BUY 10 SPY"`) and the submit button stays disabled until the user types it verbatim. The token is computed via `expectedConfirmToken()` in `services/broker.ts` — same source of truth as the backend.
- **`client_order_id` is generated once per modal mount** via `crypto.randomUUID` (with a Math.random fallback) and reused on retries — the backend looks up by this UUID for idempotency.
- **Cap-rejection mapping**: the backend returns `HTTP 422 { error: <code>, ...detail }`; the modal's `CAP_COPY` table turns each code into actionable copy (e.g. `max_position_dollars_exceeded` → "trim qty or close an existing position first") rather than raw error strings.

### `components/shared/BrokerStatusBadge.tsx`
Pill in the top nav. Polls `GET /broker/account` every 30 s and writes the
result into the store (`brokerAccount`, `brokerStatus`). States:
- `ok` → `PAPER` (amber) or `LIVE` (red) text, green status dot
- `misconfigured` → `NOT SET` (grey), red dot, tooltip nudges to `.env`
- `unreachable` → `DOWN` (red), red dot

Click → navigates to `/portfolio`. This is also what keeps `brokerAccount`
fresh for other components (e.g. `OrderTicketModal` reads it to decide
whether to show the live-mode confirmation gate).

### `components/trading/AutoTradePanel.tsx`
Inline banner rendered between the account header and the risk panel on
`/portfolio`. Driven by `GET /broker/auto-trade/status`. Colour state
mirrors the subscriber's actual state (see backend `services/trading/auto_trade.py`):
- **Grey** — `AUTO_TRADE_ENABLED=false`. Subscriber self-skips every tick.
- **Amber** — enabled but `AUTO_TRADE_SIGNAL_TYPES` is empty. Subscriber runs but no signal type fires.
- **Green** — armed: both enabled AND at least one signal_type in the allowlist.
- **Red** — scanner halted for the day (`scanner_signals_today >= SCANNER_DAILY_SIGNAL_CAP`). Both dip + MCF scanners skip remaining ticks.

### `components/trading/PortfolioRiskPanel.tsx`
Pure client-side risk view — no extra API call, derives everything from
the positions + open orders the page already fetches. Builds a `stops`
lookup from the open SELL orders' `stop_price` field, computes per-symbol
max loss to stop, and surfaces concentration warnings. Designed to catch
"auto-trade bought 30 correlated tickers" before max-loss-if-stops-hit
becomes the issue.

### Scanner integration — `components/DipScannerCard.tsx`
Adds a `Trade Signal →` button next to the existing `Paper Trade`
(localStorage) and `Enter Trade →` (manual checklist) buttons on the
opportunity card. Pre-fills the `OrderTicketModal` with the scanner's
`entry_price` as limit, `stop_price` and `target_price` as bracket legs,
and `source: 'scanner_alert'` so Phase 3 auto-trade analytics can join
broker orders back to their triggering signal. Disabled when
`brokerStatus !== 'ok'` with a tooltip explaining which state.

---

<!-- SEC:STORE -->
## Zustand Store (`frontend/src/store.ts`)

```typescript
mode: "day_trade" | "long_term" | "both"    // trade mode — changes agent prompt
execMode: "saver" | "normal" | "deep"        // execution mode — controls token usage
lastTicker: string                           // last searched ticker
tokenCount: number                           // session token accumulator
watchlist: WatchlistItem[]
alerts: Alert[]
streamEvents: SSEEvent[]
isStreaming: boolean
wsConnected: boolean
scannerView: "simple" | "pro" | "guide"

// Broker / trading (Phase 2)
brokerAccount: BrokerAccount | null
brokerStatus: "ok" | "unreachable" | "misconfigured" | "unknown"
positions: BrokerPosition[]
openOrders: BrokerOrder[]

// Actions
setMode(m)  setExecMode(m)  setLastTicker(t)  addTokens(n)
setWatchlist(items)  addAlert(a)
addStreamEvent(e)  clearStreamEvents()
setStreaming(b)  setWsConnected(b)
setBrokerAccount(a)  setBrokerStatus(s)  setPositions(p)  setOpenOrders(o)
```

**Persistence:** `mode`, `execMode`, `lastTicker`, and `scannerView` are persisted to `localStorage` via `zustand/middleware persist`. They survive page reloads and browser restarts. **Broker state (`brokerAccount`, `brokerStatus`, `positions`, `openOrders`) is intentionally NOT persisted** — it must always reflect live broker state on a fresh load, never stale localStorage.

---

<!-- SEC:HOOKS -->
## Custom Hooks (`frontend/src/hooks/`)

| Hook | Purpose |
|---|---|
| `useSSE.ts` | Connects to `/research/stream`, pushes events into Zustand `streamEvents` |
| `useWebSocket.ts` | Persistent WS to `/alerts/ws` — auto-reconnect 5 s, ping/pong 20 s |
| `useWatchlist.ts` | CRUD operations + API sync for watchlist |
| `useScreener.ts` | Filter state management + run + preset CRUD |

`useSSE` returns `{ startResearch(ticker, mode), isStreaming }`.
Calling `startResearch` closes any existing EventSource before opening a new one.

---

<!-- SEC:TYPES -->
## Core TypeScript Types (abbreviated, full list in `types/index.ts`)

```typescript
TradeMode = "day_trade" | "long_term" | "both"
ExecMode  = "saver" | "normal" | "deep"

Tier1Response { ticker, price, technicals, analyst, earnings,
                fundamentals, short_interest, congressional,
                macro, sectors, cached, exec_mode }

Tier2Response { ticker, tool, result: any, tokens_used, cached, exec_mode }
Tier3Response { ticker, tool, result: any, tokens_used, cached }
TokenEstimate { tool, estimated_tokens, estimated_cost_usd, cached }

PriceData     { ticker, current_price, change_pct_today, change_pct_7d,
                company_name, sector, market_cap, price_history[] }
TechnicalData { rsi_14, rsi_signal, macd{crossover}, bollinger_bands,
                moving_averages{crossover}, vwap_20d }
AnalystData   { consensus, price_target, upside_pct, rating_counts, recent_rating_changes[] }
EarningsData  { next_earnings_date, earnings_history[], beat_rate_pct }
CongressionalData { recent_trades[], net_sentiment, total_trades }

SSEEvent = start | tool_call | tool_result | reasoning | done | error
WSMessage = connected | heartbeat | pong | watchlist_alert | screener_alert
```

---

<!-- SEC:THEME -->
## Theme (`frontend/src/theme.ts`)

Import: `import { T } from "../theme"`
Key tokens: `T.surface`, `T.surface2`, `T.border`, `T.borderBright`
Text: `T.text`, `T.text2`, `T.text3`
Colors: `T.blue`, `T.green`, `T.red`, `T.amber`, `T.purple`
Dim variants: `T.greenDim`, `T.redDim`, `T.amberDim`
Glow: `T.blueGlow`
Font: `T.mono` (monospace family)
Helpers: `chgColor(pct)`, `chgDim(pct)`, `scoreStyle(score)`
