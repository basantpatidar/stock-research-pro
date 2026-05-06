# docs/frontend.md — Pages, components, Zustand store, hooks, key types
# Sections: grep -n "SEC:" docs/frontend.md
# SEC:PAGES       5 page components and their responsibilities
# SEC:COMPONENTS  Key shared + research components
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

**ResearchPage flow:**
1. User enters ticker → `runSearch()` fires simultaneously:
   - `startResearch(sym, mode)` → starts V1 SSE stream for agent reasoning
   - `researchV2.tier1(sym, mode, execMode)` → fetches structured data
2. T1 data renders immediately (Analyst Consensus, Earnings History, Price Chart, etc.)
3. T2 panels (News, Sentiment, Convergence, Forecast, Risk/Reward) are collapsed; user clicks to load
4. T3 panels (Investor Personas, Bull/Bear, Backtester, etc.) require explicit click
5. In `deep` exec mode: T2 panels auto-expand AND auto-load on mount via `ExpandablePanel` `useEffect`

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

### Research (`frontend/src/components/research/`)

**`PriceChart.tsx`** — Recharts area chart from `tier1.price.price_history`. On multi-day periods, overlays volume profile reference lines: VPOC (amber dashed), VAH (green dashed), VAL (red dashed) from `tier1.price.volume_profile`. Intraday (1d) uses 5-min candles with pre/after-market data; VP overlay hidden for intraday.
**`SignalScore.tsx`** — Convergence score 0-100 with label and signal breakdown
**`NewsPanel.tsx`** — News items with sentiment badges (POSITIVE/NEGATIVE/NEUTRAL)
**`StreamPanel.tsx`** — SSE event stream renderer (tool_call → tool_result → reasoning)
**`InvestorPersonasPanel.tsx`** — 5 investor persona verdict cards
**`EarningsHistoryPanel.tsx`** — Quarter-by-quarter earnings cards. Collapsed header shows Est (eps_estimate, muted) + EPS (eps_actual) side-by-side, beat/miss pill, surprise %. Expanded detail shows full EPS card + revenue card.
**`EarningsQualityPanel.tsx`** — 4-model institutional earnings quality analysis: Piotroski F-Score, Beneish M-Score, Altman Z-Score, Accruals Ratio. Each metric shows a direct verdict badge + score + plain-English explanation.
**`OptionsIntelligencePanel.tsx`** — Institutional-grade options signals: GEX, max pain, IV analysis, put/call skew, vol term structure. All computed from free yfinance data. Each metric shows verdict + signal.
**`Tier3Panels.tsx`** — BullBearPanel, BacktesterPanel, CongressionalPanel, EarningsTranscriptPanel, PaperTradePanel

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

// Actions
setMode(m)  setExecMode(m)  setLastTicker(t)  addTokens(n)
setWatchlist(items)  addAlert(a)
addStreamEvent(e)  clearStreamEvents()
setStreaming(b)  setWsConnected(b)
```

**Persistence:** `mode`, `execMode`, and `lastTicker` are persisted to `localStorage` via `zustand/middleware persist`. They survive page reloads and browser restarts.

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
