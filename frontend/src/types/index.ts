// ── Core stock types ──────────────────────────────────────────────────────────

export type TradeMode = "day_trade" | "long_term" | "both"
export type ExecMode  = "saver" | "normal" | "deep"

// ── V2 tiered API types ───────────────────────────────────────────────────────

export interface NewsResult {
  ticker: string
  articles_found: number
  news: NewsItem[]
  sentiment_breakdown: {
    positive: number
    negative: number
    neutral: number
    overall: string
  }
}

export interface PreTradeCheck {
  label: string
  pass: boolean | null
  value: string
  tip?: string
}

export interface PreTradeScore {
  score: number
  total: number
  verdict: "PROCEED" | "CAUTION" | "AVOID"
  verdict_color: "green" | "amber" | "red"
  checks: PreTradeCheck[]
}

export interface Tier1Response {
  ticker: string
  price: PriceData | { error: string }
  technicals: TechnicalData | { error: string }
  analyst: AnalystData | { error: string }
  earnings: EarningsData | { error: string }
  fundamentals: FundamentalsData | { error: string }
  short_interest: ShortInterestData | { error: string }
  congressional: CongressionalData | { error: string }
  news: NewsResult | { error: string }
  macro: any
  sectors: any
  pretrade_score: PreTradeScore | null
  cached: boolean
  exec_mode: ExecMode
}

export interface Tier2Response {
  ticker: string
  tool: string
  result: any
  tokens_used: number
  cached: boolean
  exec_mode: ExecMode
}

export interface Tier3Response {
  ticker: string
  tool: string
  result: any
  tokens_used: number
  cached: boolean
}

export interface TokenEstimate {
  tool: string
  estimated_tokens: number
  estimated_cost_usd: number
  cached: boolean
}

export interface FundamentalsData {
  ticker: string
  pe_ratio: number | null
  peg_ratio: number | null
  price_to_book: number | null
  profit_margin: number | null
  debt_to_equity: number | null
  free_cash_flow: number | null
  revenue_growth: number | null
}

export interface ShortInterestData {
  ticker: string
  short_float_pct: number | null
  days_to_cover: number | null
  short_squeeze_potential: string
}

export interface CongressionalTrade {
  politician: string
  party: string
  chamber: string
  trade_date: string
  transaction_type: string
  amount_range: string
  ticker: string
}

export interface CongressionalData {
  ticker: string
  recent_trades: CongressionalTrade[]
  net_sentiment: "bullish" | "bearish" | "neutral"
  total_trades: number
}
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

export interface VolumeProfile {
  vpoc: number
  vah: number
  val: number
  hvn_levels: number[]
  period_days: number
}

export interface Pivots {
  P: number
  R1: number
  R2: number
  S1: number
  S2: number
}

export interface SupportResistance {
  resistance: number[]
  support: number[]
}

export interface ORBLevel {
  high: number
  low: number
  position: "above" | "below" | "inside"
  breakout: "above" | "below" | "none"
}

export interface ORBData {
  orb_15: ORBLevel
  orb_30: ORBLevel
}

export interface PriceData {
  ticker: string
  current_price: number
  regular_close: number
  market_state: string
  extended_change_pct: number | null
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
  intraday_history: PricePoint[]
  volume_profile: VolumeProfile | null
  pivots: Pivots | null
  support_resistance: SupportResistance | null
  orb: ORBData | null
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
  total_ratings: number
  rating_counts: {
    strong_buy: number
    buy: number
    hold: number
    sell: number
    strong_sell: number
  }
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

// ── Earnings Quality types ────────────────────────────────────────────────────

export type Verdict = "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "AVOID" | "RISK_FLAG"
export type Conviction = "HIGH" | "MODERATE" | "LOW" | "MIXED"
export type SignalDirection = "IMPROVING" | "DETERIORATING" | "STABLE" | "UNKNOWN"

export interface SignalResult {
  value: string | number | null
  verdict: Verdict
  conviction: Conviction
  headline: string
  why: string
  action: string
  key_risk: string
  direction: SignalDirection
  direction_note: string
  score_contribution: number
}

export interface CompositeVerdict {
  verdict: Verdict
  conviction: Conviction
  score: number
  signal_count: number
  agree_count: number
}

export interface PiotroskiCheck {
  passed: boolean
  label: string
}

export interface EarningsQualityResult {
  ticker: string
  overall: CompositeVerdict
  piotroski: {
    score: number
    max_score: number
    checks: Record<string, PiotroskiCheck>
    signal: SignalResult
  }
  beneish: {
    score: number | null
    threshold_manipulator: number
    threshold_likely_manipulator: number
    components: Record<string, number>
    signal: SignalResult
  }
  altman: {
    score: number | null
    zone: "SAFE" | "GREY" | "DISTRESS" | "UNKNOWN"
    thresholds: { distress: number; grey_zone: number }
    components: Record<string, number>
    signal: SignalResult
  }
  accruals: {
    accruals_ratio_pct: number | null
    net_income: number
    operating_cash_flow: number
    cash_earnings_pct_of_net_income: number | null
    signal: SignalResult
  }
}

// ── Options Intelligence types ────────────────────────────────────────────────

export interface GEXLevel {
  strike: number
  gex: number
}

export interface TermPoint {
  expiry: string
  atm_iv_pct: number
}

export interface OptionsGEX {
  net_gex: number
  call_gex: number
  put_gex: number
  flip_level: number | null
  top_levels: GEXLevel[]
  signal: SignalResult
}

export interface OptionsMaxPain {
  strike: number
  distance_pct: number
  signal: SignalResult
}

export interface OptionsIVAnalysis {
  atm_iv_pct: number
  realized_vol_30d_pct: number | null
  iv_rv_ratio: number
  signal: SignalResult
}

export interface OptionsSkew {
  otm_put_iv_pct: number
  otm_call_iv_pct: number
  skew_pct: number
  signal: SignalResult
}

export interface OptionsTermStructure {
  shape: string
  near_iv_pct: number
  far_iv_pct: number
  slope: number
  term: TermPoint[]
  signal: SignalResult
}

export interface OptionsIntelligenceResult {
  ticker: string
  spot_price: number
  nearest_expiry: string
  gex: OptionsGEX
  max_pain: OptionsMaxPain
  iv_analysis: OptionsIVAnalysis
  skew: OptionsSkew
  term_structure: OptionsTermStructure
  composite: CompositeVerdict
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

// ── FRED Macro types ──────────────────────────────────────────────────────────

export interface FREDIndicator {
  label: string
  series_id: string
  current: number | null
  change_7d: number | null
  unit: string
  verdict: string
  color: string
  signal: string
  date: string | null
  error?: string
}

export interface FREDCrossAsset {
  label: string
  current: number
  change_7d: number
  unit: string
  verdict: string
  color: string
  signal: string
}

export interface FREDMacroData {
  credit_spreads: { hy_spread: FREDIndicator; ig_spread: FREDIndicator }
  rates: {
    real_yield_10y: FREDIndicator
    breakeven_10y: FREDIndicator
    yield_curve_2s10s: FREDIndicator
    yield_curve_3m10y: FREDIndicator
    sofr: FREDIndicator
  }
  liquidity: { m2: FREDIndicator }
  cross_asset: { copper_gold_ratio?: FREDCrossAsset; dxy?: FREDCrossAsset }
  composite_verdict: string
  composite_summary: string
  error?: string
  setup_url?: string
}

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
