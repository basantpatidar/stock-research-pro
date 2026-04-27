// ── Core stock types ──────────────────────────────────────────────────────────

export type TradeMode = "day_trade" | "long_term" | "both"
export type SignalLabel =
  | "Buy now"
  | "Buy — 1 week"
  | "Buy — 1 month"
  | "Hold"
  | "Watch — wait"
  | "Watch — risky"
  | "Avoid"
  | "Sell"

export interface PricePoint {
  date: string
  close: number
  volume: number
  high: number
  low: number
}

export interface PriceData {
  ticker: string
  current_price: number
  previous_close: number
  change_pct_today: number
  change_pct_7d: number
  day_open: number
  day_high: number
  day_low: number
  volume: number
  avg_volume: number
  volume_ratio: number
  company_name: string
  market_cap: number | null
  sector: string
  price_history: PricePoint[]
}

export interface TechnicalData {
  ticker: string
  rsi_14: number
  rsi_signal: string
  macd: {
    macd: number
    signal: number
    histogram: number
    crossover: "bullish" | "bearish"
  }
  bollinger_bands: {
    upper: number
    middle: number
    lower: number
    position: number
    interpretation: string
  }
  moving_averages: {
    ma_50d: number
    ma_200d: number
    crossover: string
    meaning: string
  }
  vwap_20d: number
  price_vs_vwap: string
  volume_trend: {
    today: number
    avg_20d: number
    above_average: boolean
  }
}

export interface NewsItem {
  headline: string
  description: string
  source: string
  published: string
  sentiment: "positive" | "negative" | "neutral"
  url: string
}

export interface AnalystData {
  ticker: string
  consensus: string
  mean_rating: number | null
  price_target: number | null
  current_price: number | null
  upside_pct: number | null
  num_analysts: number | null
  recent_rating_changes: Array<{
    firm: string
    to_grade: string
    from_grade: string
    action: string
  }>
}

export interface EarningsData {
  ticker: string
  next_earnings_date: string | null
  earnings_history: Array<{
    date: string
    eps_estimate: number | null
    eps_actual: number | null
    surprise: number | null
    beat: boolean | null
  }>
  beat_count: number
  miss_count: number
  beat_rate_pct: number | null
}

export interface ConvergenceSignal {
  signal: string
  value: string
  direction: "bullish" | "bearish" | "neutral"
  points: number
}

export interface ConvergenceScore {
  ticker: string
  convergence_score: number
  label: string
  signals: ConvergenceSignal[]
  bullish_signals: number
  bearish_signals: number
}

// ── Watchlist types ───────────────────────────────────────────────────────────

export interface WatchlistItem {
  id: number
  ticker: string
  company_name: string | null
  last_signal: SignalLabel | null
  last_score: number | null
  last_price: number | null
  last_evaluated: string | null
  added_at: string
  notes: string | null
}

// ── Screener types ────────────────────────────────────────────────────────────

export interface ScreenerFilters {
  min_market_cap_b: number
  min_volume: number
  min_price_drop_pct: number
  sector: string
  max_pe: number
}

export interface ScreenerResult {
  ticker: string
  company: string
  price: number
  change_7d_pct: number
  market_cap_b: number
  avg_volume: number
  sector: string
  pe_ratio: number | null
}

export interface ScreenerPreset {
  id: number
  name: string
  filters: ScreenerFilters
  auto_monitor: boolean
  last_run: string | null
  created_at: string
}

// ── Alert types ───────────────────────────────────────────────────────────────

export interface Alert {
  id: number
  ticker: string
  type: string
  title: string
  body: string
  score: number | null
  triggered_at: string
  source: "watchlist" | "screener"
}

export type WSMessage =
  | { type: "connected"; message: string; timestamp: string }
  | { type: "heartbeat" }
  | { type: "pong" }
  | { type: "watchlist_alert"; ticker: string; signal: string; score: number; price: number; change_7d: number; title: string; body: string; timestamp: string }
  | { type: "screener_alert"; ticker: string; preset: string; title: string; body: string; stock: ScreenerResult; timestamp: string }

// ── SSE stream types ──────────────────────────────────────────────────────────

export type SSEEvent =
  | { type: "start"; ticker: string; mode: string }
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; result: unknown }
  | { type: "reasoning"; content: string }
  | { type: "done" }
  | { type: "error"; message: string }

// ── Macro types ───────────────────────────────────────────────────────────────

export interface MacroIndicator {
  current: number
  change_today_pct: number
  change_7d_pct: number
}

export interface MacroEnvironment {
  environment: string
  vix: MacroIndicator | null
  sp500: MacroIndicator | null
  nasdaq: MacroIndicator | null
  oil_wti: MacroIndicator | null
  gold: MacroIndicator | null
  treasury_10y: MacroIndicator | null
  trading_recommendation: string
}

export interface SectorData {
  sector: string
  etf: string
  change_5d_pct: number
  trend: "up" | "down" | "flat"
}

export interface GeoEvent {
  title: string
  source: string
  published: string
  severity: "critical" | "high" | "medium"
  impacted_sectors: string[]
  url: string
}
