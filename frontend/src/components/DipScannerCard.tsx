import { useState, useCallback, useEffect, type ReactNode } from "react"
import { AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip, YAxis } from "recharts"
import { api } from "../services/api"
import { T } from "../theme"
import { useStore } from "../store"
import { SituationSummary } from "./SituationSummary"

interface Candle { time: string; open: number; high: number; low: number; close: number }

const STORAGE_KEY = "dts_capital"
const HISTORY_KEY = "dts_signal_history"
const DEFAULT_CAPITAL = 1000
const HISTORY_RETENTION_DAYS = 30

interface HistoryEntry {
  id: string
  ticker: string
  signal_type: string
  score: number
  entry_price: number
  target_price: number
  stop_price: number
  shares: number
  expected_profit_dollar: number
  max_risk_dollar: number
  risk_reward_ratio: number
  session_window_label: string
  capital: number
  timestamp: string
}

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const entries: HistoryEntry[] = JSON.parse(raw)
    const cutoff = Date.now() - HISTORY_RETENTION_DAYS * 24 * 60 * 60 * 1000
    return entries.filter(e => new Date(e.timestamp).getTime() > cutoff)
  } catch {
    return []
  }
}

function saveHistory(entries: HistoryEntry[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(entries))
}

function formatHistoryTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))
  const timeStr = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  if (diffDays === 0) return `Today ${timeStr}`
  if (diffDays === 1) return `Yesterday ${timeStr}`
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${timeStr}`
}

const TERM_HINTS: Record<string, string> = {
  RVOL: "Relative Volume — today's volume vs the average for this time of day. 1.5× means 50% more activity than normal; signals institutional participation.",
  RSI:  "Relative Strength Index (0–100). Below 30 = oversold, sellers likely exhausted. Above 70 = overbought. We wait for RSI < 38–42 before entering a dip-buy.",
  VIX:  "Volatility Index — the market's 'fear gauge.' Higher VIX = bigger swings both ways. We tighten entry criteria when VIX > 18 and pause entirely above 35.",
  VWAP: "Volume-Weighted Average Price — the average price weighted by volume for today's session. Institutions treat this as their 'fair value'; price tends to snap back to it.",
  ATR:  "Average True Range — measures how much the ETF moves per bar on average. All stop and target distances are expressed as ATR multiples so they scale with volatility.",
  "Dip from open": "How far price has fallen from today's opening print. The scanner requires at least 0.4–1.1× ATR of dip (depending on VIX) before considering an entry.",
}

const SIGNAL_TYPE_LABEL: Record<string, string> = {
  dip_buy:          "Dip Buy",
  orb_breakout:     "ORB Breakout",
  vwap_reclaim:     "VWAP Reclaim",
  failed_breakdown: "Failed Breakdown",
}

const SIGNAL_TYPE_COLOR: Record<string, string> = {
  dip_buy:          T.amber,
  orb_breakout:     T.blue,
  vwap_reclaim:     T.green,
  failed_breakdown: T.green,
}

interface AnalysisResult {
  verdict: "FAVORABLE" | "MIXED" | "UNFAVORABLE"
  plain_english: string
  key_risk: string
  watch_for: string
  history_count: number
  win_rate_pct: number | null
  tokens_used: number
}

interface Invalidation {
  price_close_below: number
  vix_above: number
  rvol_resurge_above: number
}

interface TickerSignalHistory {
  id: string
  signal_type: string
  side: string
  entry_time: string | null
  session_window: string
  score: number | null
  entry_price: number
  target_price: number
  stop_price: number
  status: string
  outcome_price: number | null
  actual_pnl_pct: number | null
  actual_pnl_dollar: number | null
  resolved_by: string | null
  five_min_direction: string | null
}

interface Opportunity {
  ticker: string
  signal_type: string
  side?: string
  score: number
  entry_price: number
  target_price: number
  stop_price: number
  signals: string[]
  signal_hints: Record<string, string>
  session_window: string
  session_window_label: string
  intraday_vwap: number
  rsi_5m: number
  rvol: number
  vix: number
  dip_pct: number
  shares: number
  expected_profit_dollar: number
  max_risk_dollar: number
  risk_reward_ratio: number
  capital_used: number
  invalidation?: Invalidation
  time_stop_minutes?: number
  confidence_tier?: string
  top_reasons?: string[]
  atr_5m?: number
  atr_adjusted?: boolean
  entry_refined?: boolean
}

interface VixSpikePrep {
  type: string
  vix_current: number
  vix_spike_pct: number
  spy_change_pct: number
}

interface RegimeInfo {
  regime: "mean_revert" | "chop" | "trend_up" | "trend_down"
  reason: string
  spy_above_ema: boolean
  vix_5d_change_pct: number
  spy_vs_ema_pct: number
  range_vs_atr: number
}

interface ScanResult {
  opportunities: Opportunity[]
  orb_opportunities: Opportunity[]
  vwap_opportunities: Opportunity[]
  failed_breakdown_opportunities: Opportunity[]
  best: Opportunity | null
  vix_spike_prep: VixSpikePrep | null
  scenario_key: string
  tickers_scanned: number
  session_window: string
  vix: number
  regime?: RegimeInfo
  timestamp: string
  capital: number
  loose_gates_active?: boolean
}

const SESSION_COLORS: Record<string, string> = {
  power_hour:    T.green,
  morning_flush: T.amber,
  morning_trend: T.blue,
  lunch_drift:   T.text2,
  pre_market:    T.amber,
  after_hours:   T.amber,
}

const EXTENDED_HOURS = new Set(["pre_market", "after_hours"])

const SCORE_COLOR = (s: number) => s >= 80 ? T.green : s >= 65 ? T.amber : T.text2

function TermTip({ term }: { term: string }) {
  const hint = TERM_HINTS[term]
  if (!hint) return <span>{term}</span>
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 2 }}>
      <span style={{ borderBottom: `1px dotted ${T.text3}`, cursor: "help" }}>{term}</span>
      <HintTooltip hint={hint} />
    </span>
  )
}

function HintTooltip({ hint }: { hint: string }) {
  const [show, setShow] = useState(false)
  if (!hint) return null
  return (
    <span style={{ position: "relative", display: "inline-block" }}>
      <span
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        style={{ cursor: "help", color: T.text3, fontSize: 10, marginLeft: 3 }}
      >
        [?]
      </span>
      {show && (
        <span style={{
          position: "absolute", bottom: "120%", left: "50%", transform: "translateX(-50%)",
          background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7,
          padding: "7px 10px", fontSize: 11, color: T.text2, whiteSpace: "normal",
          width: 220, zIndex: 200, boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
          lineHeight: 1.45, pointerEvents: "none",
        }}>
          {hint}
        </span>
      )}
    </span>
  )
}

const SIGNAL_TYPE_GUIDE: Record<string, { what: string; why: string; edge: string; watch: string }> = {
  dip_buy: {
    what: "Price has pulled back from the opening price by at least 0.4–1.1× ATR (depending on market fear). Sellers appear exhausted — volume is declining and RSI is oversold.",
    why: "ETFs mean-revert. When a broad index drops sharply intraday, institutional buyers typically step in near key support levels to buy the dip, pushing price back up.",
    edge: "Works best in morning flush and power hour sessions. Requires declining sell volume (not a knife still falling) and RSI below 38–42. Blocked on trend-down days.",
    watch: "Exit immediately if price closes below your stop. If it consolidates sideways for more than your time stop window with no move, exit — the bounce isn't coming.",
  },
  orb_breakout: {
    what: "Price broke above the Opening Range High — the highest point of the first 15 minutes of trading. This range acts as the market's initial price discovery zone.",
    why: "The opening 15 minutes set the battleground between buyers and sellers. A clean break above that range on elevated volume signals that buyers won the battle and momentum is accelerating.",
    edge: "Most reliable after 10:30 AM when the opening range is fully established. Requires at least 1.3× relative volume to confirm real institutional buying, not a low-volume fake-out.",
    watch: "If price breaks out but volume fades within 1–2 bars, exit — it's likely a trap. The ORB high becomes your new support; if price falls back below it, stop out.",
  },
  vwap_reclaim: {
    what: "Price was trading below VWAP (the volume-weighted average price for today), then crossed back above it on strong volume. Institutions treat VWAP as their fair value reference.",
    why: "Large funds benchmark their trades to VWAP. When price reclaims VWAP with volume, it often means institutional buyers stepped in — they'll defend this level, creating a floor.",
    edge: "The reclaim bar itself must show at least 1.5× relative volume to be meaningful. A low-volume VWAP cross is noise; a high-volume cross is a real shift in order flow.",
    watch: "If price crosses back below VWAP after entry, exit — the setup has failed. VWAP reclaim trades are fast; if you don't see follow-through within 10–15 minutes, consider exiting.",
  },
  failed_breakdown: {
    what: "Price briefly broke below a key support level (pivot S1/S2 or ORB low) then snapped back above it. Traders who shorted the breakdown are now trapped.",
    why: "When price breaks a well-known support level, short sellers pile in expecting a drop. When it reverses and reclaims that level, those shorts must buy to cover — fueling a squeeze upward.",
    edge: "The reversal bar volume should be at least 1.4× average to confirm real buying. The more traders who were caught short, the stronger the squeeze. Works best in morning and power hour.",
    watch: "Your stop is just below the broken support level. If price falls back through it again, the setup failed — the support is truly broken. Exit fast; these can drop quickly.",
  },
}

const SESSION_GUIDE: Record<string, { when: string; edge: string; caution: string }> = {
  morning_flush:  { when: "9:40–10:30 AM ET", edge: "Highest volatility window. Big gap-downs from pre-market often flush out weak holders here — classic dip-buy territory when volume peaks then fades.", caution: "Moves are fast and can overshoot. Wait for RSI to hit oversold AND volume to start declining before entering. Never chase the first red candle." },
  morning_trend:  { when: "10:30 AM–12 PM ET", edge: "Trend is established. ORB breakouts and VWAP reclaims are most reliable here — the market has made its initial move and momentum is cleaner.", caution: "Dip buys are harder here — if price is still falling after 10:30, the dip may be a real trend reversal, not a flush." },
  lunch_drift:    { when: "12–2 PM ET", edge: "Very low activity. Occasionally good for ORB continuation if morning trend is strong.", caution: "Dip buys are blocked below score 80 here — backtest showed near 0% win rate. Volume dries up and price action is unpredictable. Avoid most setups." },
  power_hour:     { when: "2–4 PM ET", edge: "Best session overall. Institutional rebalancing and end-of-day positioning creates real directional moves with follow-through. Score gets +10 bonus.", caution: "Less time to be wrong — you only have until 4 PM. Keep position sizes standard and don't average down." },
  pre_market:     { when: "4–9:30 AM ET", edge: "Occasionally useful for gap setups after major news. Score is penalized −10.", caution: "Wide spreads, low liquidity, and price action that often reverses at open. Treat any signal here as low-confidence." },
  after_hours:    { when: "4–8 PM ET", edge: "Rarely actionable. Score penalized −10.", caution: "Spreads are wide and fills are poor. Avoid unless you have a specific catalyst thesis." },
}

function GuideView({ opp }: { opp: Opportunity }) {
  const sg = SIGNAL_TYPE_GUIDE[opp.signal_type] ?? SIGNAL_TYPE_GUIDE.dip_buy
  const sesh = SESSION_GUIDE[opp.session_window] ?? SESSION_GUIDE.morning_trend
  const wholeShares = Math.floor(opp.shares)
  const adjProfit = wholeShares * (opp.target_price - opp.entry_price)
  const adjRisk = wholeShares * (opp.entry_price - opp.stop_price)
  const rr = opp.risk_reward_ratio

  const section = (title: string, color: string, children: ReactNode) => (
    <div style={{ marginBottom: 14, borderLeft: `3px solid ${color}`, paddingLeft: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  )

  const row = (label: string, value: React.ReactNode, detail?: string) => (
    <div style={{ display: "flex", gap: 8, marginBottom: 5, alignItems: "flex-start" }}>
      <div style={{ width: 120, flexShrink: 0, fontSize: 11, color: T.text3 }}>{label}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: typeof value === "string" ? T.mono : undefined }}>{value}</div>
        {detail && <div style={{ fontSize: 11, color: T.text3, marginTop: 2, lineHeight: 1.5 }}>{detail}</div>}
      </div>
    </div>
  )

  return (
    <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 0 }}>

      {/* What is this setup */}
      {section(SIGNAL_TYPE_LABEL[opp.signal_type] || opp.signal_type, SIGNAL_TYPE_COLOR[opp.signal_type] || T.blue, (
        <>
          <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.65, marginBottom: 8 }}>{sg.what}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {[
              { icon: "📐", label: "Why it works", text: sg.why },
              { icon: "✅", label: "What creates the edge", text: sg.edge },
              { icon: "⚠️", label: "What to watch", text: sg.watch },
            ].map(({ icon, label, text }) => (
              <div key={label} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>{icon}</span>
                <div>
                  <span style={{ fontSize: 11, fontWeight: 600, color: T.text }}>{label}: </span>
                  <span style={{ fontSize: 11, color: T.text2, lineHeight: 1.6 }}>{text}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      ))}

      {/* Score */}
      {section("Score: " + opp.score + "/100", SCORE_COLOR(opp.score), (
        <>
          {row("What it means", opp.score >= 80 ? "ENTER NOW — all key criteria met" : opp.score >= 65 ? "READY — minimum threshold cleared" : "Too weak — below 65 threshold",
            "Score combines: RSI level (−/+), RVOL (how active volume is), support proximity, VIX slope (rising fear = penalty), session window bonus/penalty, 30-min trend alignment, and CVD (cumulative buy/sell pressure)."
          )}
          {row("Confidence tier", opp.confidence_tier ?? "—",
            opp.confidence_tier === "very_high" ? "Score 90+. All signals aligned. Highest-probability setup in the session."
            : opp.confidence_tier === "high" ? "Score 80–89. Strong setup. Most criteria met clearly."
            : "Score 65–79. Minimum viable. Be more conservative with size."
          )}
          {opp.atr_5m != null && row("ATR (5-min)", `$${opp.atr_5m.toFixed(2)}`,
            `Average True Range on 5-min bars — how much ${opp.ticker} typically moves per 5-min candle. All stops and targets are ATR multiples, not fixed percentages, so they scale with actual volatility.`
          )}
        </>
      ))}

      {/* Session */}
      {section(`Session: ${sesh.when}`, SESSION_COLORS[opp.session_window] || T.text2, (
        <>
          {row("Edge", sesh.edge)}
          {row("Caution", sesh.caution)}
        </>
      ))}

      {/* Order levels */}
      {section("Order Levels", T.text2, (
        <>
          {row("Buy Limit", `$${opp.entry_price.toFixed(2)}`,
            `Set a limit order at this price — do NOT market buy. A limit order ensures you get the price the scanner identified. Market orders on ETFs can fill $0.05–0.15 worse during fast moves.`
          )}
          {row("Sell Limit (target)", `$${opp.target_price.toFixed(2)}`,
            `Set this as a limit sell order immediately after entry. This is ${rr}× your risk. The target is capped at 1.5% above entry for dip buys to avoid unrealistic expectations.`
          )}
          {row("Stop Loss", `$${opp.stop_price.toFixed(2)}`,
            `Set this as a stop-market order immediately after entry. Never skip the stop. If you forget, price can blow through your intended exit before you react.`
          )}
          {wholeShares > 0 && row("Position math",
            <span>Risk <span style={{ color: "#ef4444" }}>−${adjRisk.toFixed(2)}</span> → Make <span style={{ color: T.green }}>+${adjProfit.toFixed(2)}</span></span>,
            `${wholeShares} shares × $${(opp.entry_price - opp.stop_price).toFixed(2)} stop distance = $${adjRisk.toFixed(2)} max loss. ${wholeShares} shares × $${(opp.target_price - opp.entry_price).toFixed(2)} to target = $${adjProfit.toFixed(2)} max gain. R:R = ${rr}:1.`
          )}
        </>
      ))}

      {/* Time stop */}
      {opp.time_stop_minutes && section("Time Stop", T.amber, (
        row(`Exit after ${opp.time_stop_minutes} min`, "If price hasn't moved +0.3% in your favor",
          `A trade that stalls is a trade that's losing edge. The setup thesis depends on momentum — if price sits flat, buyers haven't stepped in and the thesis is wrong. Exit cleanly at a small loss rather than waiting for the stop to get hit.`
        )
      ))}

      {/* Invalidation */}
      {opp.invalidation && section("Setup Invalidated If…", "#ef4444", (
        <>
          {row("Price closes below", `$${opp.invalidation.price_close_below.toFixed(2)}`, "A 5-min bar close below this level means support has genuinely broken — the bounce thesis is wrong.")}
          {row("VIX spikes above", `${opp.invalidation.vix_above.toFixed(1)}`, "A sudden VIX surge means macro fear is accelerating — ETF dips in this environment tend to continue rather than bounce.")}
          {row("RVOL resurges above", `${opp.invalidation.rvol_resurge_above}×`, "If volume surges again after declining, sellers are back — the exhaustion read was wrong.")}
        </>
      ))}

      {/* Step-by-step */}
      {section("Step-by-Step Execution", T.blue, (
        <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
          {[
            `Open ${opp.ticker} in your broker.`,
            `Place a BUY LIMIT order at $${opp.entry_price.toFixed(2)} — do not market buy.`,
            `Immediately set a SELL LIMIT at $${opp.target_price.toFixed(2)} for ${wholeShares} shares.`,
            `Immediately set a STOP MARKET at $${opp.stop_price.toFixed(2)} for ${wholeShares} shares.`,
            `Walk away. Do not watch every tick — you have a plan, trust it.`,
            opp.time_stop_minutes ? `If no +0.3% move within ${opp.time_stop_minutes} minutes — exit at market.` : `Monitor for the time stop shown above.`,
            `After close — log the outcome in Manual Trade Log regardless of win or loss.`,
          ].map((step, i) => (
            <li key={i} style={{ fontSize: 11, color: T.text2, lineHeight: 1.6 }}>{step}</li>
          ))}
        </ol>
      ))}

    </div>
  )
}

// Signal state derived from score + session
function getSignalState(opp: Opportunity): "enter_now" | "ready" {
  return opp.score >= 80 ? "enter_now" : "ready"
}

const STATE_CONFIG = {
  enter_now: { label: "ENTER NOW", color: T.green,    bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.35)" },
  ready:     { label: "READY",     color: T.amber,    bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.30)" },
  wait:      { label: "WAIT",      color: T.text3,    bg: T.surface2,              border: T.border },
  missed:    { label: "MISSED",    color: T.text3,    bg: T.surface2,              border: T.border },
}

const CONFIDENCE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  very_high: { label: "Very High Confidence", color: T.green, bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.35)" },
  high:      { label: "High Confidence",      color: T.blue,  bg: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.35)" },
  medium:    { label: "Medium Confidence",    color: T.amber, bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.30)" },
}

const REGIME_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  mean_revert: { label: "Mean Revert Day",  color: T.green, bg: "rgba(34,197,94,0.10)",  icon: "✓" },
  chop:        { label: "Choppy Day",       color: T.blue,  bg: "rgba(59,130,246,0.10)", icon: "↔" },
  trend_up:    { label: "Trend Up Day",     color: T.amber, bg: "rgba(245,158,11,0.10)", icon: "↑" },
  trend_down:  { label: "Trend Down Day",   color: "#ef4444", bg: "rgba(239,68,68,0.10)", icon: "⛔" },
}

interface RecentSetup {
  entry_time: string
  entry_price: number
  outcome_price: number | null
  status: string
  actual_pnl_pct: number | null
  actual_pnl_dollar: number | null
  score: number | null
}

function RecentOutcomes({ ticker, session, signalType }: { ticker: string; session: string; signalType: string }) {
  const [setups, setSetups] = useState<RecentSetup[]>([])
  useEffect(() => {
    api.get(`/dip-scanner/similar?ticker=${ticker}&session=${session}&signal_type=${signalType}&limit=4`)
      .then(r => setSetups(r.data.setups ?? []))
      .catch(() => setSetups([]))
  }, [ticker, session, signalType])

  if (setups.length === 0) return null

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 10, color: T.text3, marginBottom: 5, textTransform: "uppercase", letterSpacing: 1 }}>
        Last {setups.length} similar setup{setups.length !== 1 ? "s" : ""} · {ticker} {session.replace("_", " ")}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {setups.map((s, i) => {
          const won = s.status === "win"
          const color = won ? T.green : "#ef4444"
          const pnl = s.actual_pnl_dollar != null
            ? `${won ? "+" : ""}$${s.actual_pnl_dollar.toFixed(2)}`
            : s.status
          const dt = s.entry_time ? new Date(s.entry_time).toLocaleDateString([], { month: "short", day: "numeric" }) : "—"
          return (
            <div key={i} style={{
              flex: 1, background: T.surface2, border: `1px solid ${color}33`,
              borderRadius: 6, padding: "5px 7px",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color, fontFamily: T.mono }}>{pnl}</div>
              <div style={{ fontSize: 10, color: T.text3, marginTop: 1 }}>{dt}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TickerHistoryModal({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const [data, setData] = useState<{ count: number; signals: TickerSignalHistory[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/dip-scanner/ticker-history/${ticker}?limit=30`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [ticker])

  const statusColor = (s: string) =>
    s === "win" ? T.green : s === "loss" ? "#ef4444" : s === "open" ? T.blue : T.text3

  const fmtDate = (iso: string | null) => {
    if (!iso) return "—"
    const d = new Date(iso)
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 600, background: "rgba(0,0,0,0.65)", display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ background: T.surface, border: `1px solid ${T.borderBright}`, borderRadius: 14, padding: "22px 24px", width: 520, maxWidth: "95vw", maxHeight: "80vh", display: "flex", flexDirection: "column" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <span style={{ fontSize: 16, fontWeight: 700, fontFamily: T.mono, color: T.blue }}>{ticker}</span>
            <span style={{ fontSize: 12, color: T.text3, marginLeft: 8 }}>Scanner History</span>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: T.text3, fontSize: 18, cursor: "pointer", lineHeight: 1 }}>×</button>
        </div>

        {loading && <div style={{ textAlign: "center", padding: "24px 0", color: T.text3, fontSize: 12 }}>Loading…</div>}
        {!loading && !data && <div style={{ textAlign: "center", padding: "24px 0", color: T.text3, fontSize: 12 }}>No history yet</div>}
        {!loading && data && data.signals.length === 0 && (
          <div style={{ textAlign: "center", padding: "24px 0", color: T.text3, fontSize: 12 }}>No scan records for {ticker}</div>
        )}

        {!loading && data && data.signals.length > 0 && (
          <div style={{ overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {data.signals.map(s => {
              const sc = statusColor(s.status)
              const pnl = s.actual_pnl_dollar != null
                ? `${s.actual_pnl_dollar >= 0 ? "+" : ""}$${s.actual_pnl_dollar.toFixed(2)}`
                : null
              const fivMin = s.five_min_direction === "up" ? "↑ up" : s.five_min_direction === "down" ? "↓ dn" : s.five_min_direction === "flat" ? "→ flat" : null
              return (
                <div key={s.id} style={{
                  background: T.surface2, border: `1px solid ${T.border}`,
                  borderLeft: `3px solid ${SIGNAL_TYPE_COLOR[s.signal_type] || T.text3}`,
                  borderRadius: 8, padding: "10px 12px",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, flexWrap: "wrap", gap: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 6px", background: "rgba(34,197,94,0.12)", color: T.green, border: "1px solid rgba(34,197,94,0.3)", borderRadius: 4 }}>
                        {s.side}
                      </span>
                      <span style={{ fontSize: 11, color: SIGNAL_TYPE_COLOR[s.signal_type] || T.text2 }}>
                        {SIGNAL_TYPE_LABEL[s.signal_type] || s.signal_type}
                      </span>
                      {s.score != null && <span style={{ fontSize: 10, color: SCORE_COLOR(s.score) }}>Score {s.score}</span>}
                      {s.session_window && <span style={{ fontSize: 10, color: T.text3 }}>{s.session_window.replace(/_/g, " ")}</span>}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {pnl && (
                        <span style={{ fontSize: 13, fontWeight: 700, fontFamily: T.mono, color: sc }}>{pnl}</span>
                      )}
                      <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 6px", background: `${sc}20`, color: sc, border: `1px solid ${sc}40`, borderRadius: 4 }}>
                        {s.status}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 4 }}>
                    {[
                      { label: "Buy Limit", value: s.entry_price, color: T.text },
                      { label: "Sell Limit", value: s.target_price, color: T.green },
                      { label: "Stop Loss", value: s.stop_price, color: "#ef4444" },
                    ].map(({ label, value, color }) => (
                      <div key={label} style={{ background: T.surface, borderRadius: 6, padding: "5px 8px", textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: T.text3, marginBottom: 2 }}>{label}</div>
                        <div style={{ fontSize: 12, fontWeight: 600, fontFamily: T.mono, color }}>${value?.toFixed(2) ?? "—"}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 10, fontSize: 10, color: T.text3, flexWrap: "wrap" }}>
                    <span>{fmtDate(s.entry_time)}</span>
                    {s.outcome_price && <span>Exit ${s.outcome_price.toFixed(2)}</span>}
                    {fivMin && <span style={{ color: s.five_min_direction === "up" ? T.green : s.five_min_direction === "down" ? "#ef4444" : T.text3 }}>5-min {fivMin}</span>}
                    {s.resolved_by && <span>· {s.resolved_by}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function RegimeBadge({ regime }: { regime: RegimeInfo }) {
  const cfg = REGIME_CONFIG[regime.regime] ?? REGIME_CONFIG.mean_revert
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{
        fontSize: 11, fontWeight: 600, color: cfg.color,
        background: cfg.bg, border: `1px solid ${cfg.color}40`,
        borderRadius: 5, padding: "2px 7px",
        display: "flex", alignItems: "center", gap: 4,
      }}>
        <span>{cfg.icon}</span>
        <span>{cfg.label}</span>
      </span>
      {regime.regime === "trend_down" && (
        <span style={{ fontSize: 10, color: "#ef4444" }}>· dip buys blocked</span>
      )}
      {regime.regime === "trend_up" && (
        <span style={{ fontSize: 10, color: T.text3 }}>· RSI &lt; 30 required</span>
      )}
    </div>
  )
}

export function DipScannerCard() {
  const { execMode, scannerView, setScannerView, addTokens } = useStore()
  const [capital, setCapital] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? parseFloat(saved) : DEFAULT_CAPITAL
  })
  const [tiers, setTiers] = useState<number[]>([1])
  const [looseGates, setLooseGates] = useState<boolean>(() => localStorage.getItem("dts_loose_gates") === "1")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [expandedSignals, setExpandedSignals] = useState(false)
  const [llmAnalysis, setLlmAnalysis] = useState<AnalysisResult | null>(null)
  const [llmLoading, setLlmLoading] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(() => loadHistory())
  const [showHistory, setShowHistory] = useState(false)
  const [chartData, setChartData] = useState<Candle[]>([])
  const [checklist, setChecklist] = useState(false)
  const [checklistBoxes, setChecklistBoxes] = useState([false, false, false])
  const [livePrice, setLivePrice] = useState<number | null>(null)
  const [showOnboarding, setShowOnboarding] = useState<boolean>(() => !localStorage.getItem("srp_onboarded"))
  const [paperTraded, setPaperTraded] = useState<string | null>(null)  // null | ticker key
  const [historyTicker, setHistoryTicker] = useState<string | null>(null)

  const dismissOnboarding = () => {
    localStorage.setItem("srp_onboarded", "1")
    setShowOnboarding(false)
  }

  const paperTrade = (opp: Opportunity) => {
    const key = `${opp.ticker}-${Date.now()}`
    const entry = {
      id: key,
      ticker: opp.ticker,
      signal_type: opp.signal_type,
      entry_price: opp.entry_price,
      target_price: opp.target_price,
      stop_price: opp.stop_price,
      score: opp.score,
      shares: Math.floor(opp.shares),
      session_window_label: opp.session_window_label,
      timestamp: new Date().toISOString(),
    }
    const existing = JSON.parse(localStorage.getItem("srp_paper_trades") || "[]")
    localStorage.setItem("srp_paper_trades", JSON.stringify([entry, ...existing].slice(0, 50)))
    setPaperTraded(opp.ticker)
    setTimeout(() => setPaperTraded(null), 3000)
  }

  useEffect(() => {
    if (!result?.best) { setChartData([]); setLivePrice(null); return }
    const fetchChart = () =>
      api.get(`/dip-scanner/chart/${result.best!.ticker}`)
        .then(r => {
          const candles = r.data.candles ?? []
          setChartData(candles)
          if (candles.length > 0) setLivePrice(candles[candles.length - 1].close)
        })
        .catch(() => {})
    fetchChart()
    const interval = setInterval(fetchChart, 10_000)  // poll every 10s for MISSED check
    return () => clearInterval(interval)
  }, [result?.best?.ticker])

  // MISSED: price moved >0.2×ATR above entry since signal fired (#14)
  const signalMissed = !!result?.best && livePrice !== null && (() => {
    const atr = result.best!.atr_5m ?? result.best!.entry_price * 0.002
    return livePrice > result.best!.entry_price + 0.2 * atr
  })()

  const handleCapitalChange = (val: number) => {
    setCapital(val)
    localStorage.setItem(STORAGE_KEY, String(val))
  }

  const toggleLooseGates = () => {
    setLooseGates(prev => {
      const next = !prev
      localStorage.setItem("dts_loose_gates", next ? "1" : "0")
      return next
    })
  }

  const scan = useCallback(async () => {
    setLoading(true)
    setResult(null)
    setLlmAnalysis(null)
    try {
      const res = await api.post("/dip-scanner/scan", {
        tiers,
        capital,
        vix: null,
        loose_gates: looseGates,
      })
      const data: ScanResult = res.data
      setResult(data)
      if (data.best) {
        const b = data.best
        const ws = Math.floor(b.shares)
        const entry: HistoryEntry = {
          id: `${b.ticker}-${Date.now()}`,
          ticker: b.ticker,
          signal_type: b.signal_type,
          score: b.score,
          entry_price: b.entry_price,
          target_price: b.target_price,
          stop_price: b.stop_price,
          shares: ws,
          expected_profit_dollar: ws * (b.target_price - b.entry_price),
          max_risk_dollar: ws * (b.entry_price - b.stop_price),
          risk_reward_ratio: b.risk_reward_ratio,
          session_window_label: b.session_window_label,
          capital,
          timestamp: new Date().toISOString(),
        }
        setHistory(prev => {
          const updated = [entry, ...prev]
          saveHistory(updated)
          return updated
        })
      }
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [tiers, capital, looseGates])

  const analyzeSetup = async (opp: Opportunity) => {
    if (execMode === "saver") return
    setLlmLoading(true)
    try {
      const res = await api.post("/dip-scanner/analyze", {
        ticker: opp.ticker,
        signal_type: opp.signal_type,
        score: opp.score,
        confidence_tier: opp.confidence_tier ?? null,
        session_window: opp.session_window,
        session_window_label: opp.session_window_label,
        entry_price: opp.entry_price,
        target_price: opp.target_price,
        stop_price: opp.stop_price,
        rsi_5m: opp.rsi_5m,
        rvol: opp.rvol,
        vix: opp.vix,
        dip_pct: opp.dip_pct,
        risk_reward_ratio: opp.risk_reward_ratio,
        atr_5m: opp.atr_5m ?? null,
        signals: opp.signals,
        top_reasons: opp.top_reasons ?? [],
      })
      setLlmAnalysis(res.data as AnalysisResult)
      if (res.data.tokens_used > 0) addTokens(res.data.tokens_used)
    } catch {
      setLlmAnalysis({
        verdict: opp.score >= 80 ? "FAVORABLE" : "MIXED",
        plain_english: `${opp.ticker} shows RSI ${opp.rsi_5m} oversold on 5-min bars with RVOL ${opp.rvol}x — sellers appear to be running out of steam near the -${opp.dip_pct}% intraday dip.`,
        key_risk: `Exit if price closes below the stop at $${opp.stop_price.toFixed(2)}.`,
        watch_for: `Watch for price to move toward $${opp.target_price.toFixed(2)} with sustained volume.`,
        history_count: 0,
        win_rate_pct: null,
        tokens_used: 0,
      })
    } finally {
      setLlmLoading(false)
    }
  }

  const best = result?.best

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>

      {/* First-time onboarding modal (#24) */}
      {showOnboarding && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 600,
          background: "rgba(0,0,0,0.65)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={dismissOnboarding}>
          <div onClick={e => e.stopPropagation()} style={{
            background: T.surface, border: `1px solid ${T.borderBright}`,
            borderRadius: 14, padding: "26px 28px", width: 380, maxWidth: "92vw",
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 6 }}>
              Daily Target Trade Scanner
            </div>
            <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.65, marginBottom: 18 }}>
              This scanner runs every 5 minutes during market hours and looks for high-probability dip-buy setups across 8 ETFs — with zero AI tokens used.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
              {[
                ["Scan Now", "Run a manual scan any time. Results appear within 2–3 seconds."],
                ["Score ≥ 80 = ENTER NOW", "Score combines RSI, RVOL, support proximity, VIX slope, and session window."],
                ["Pre-trade checklist", "Before entering, confirm your stop and target so you have a plan before emotions kick in."],
                ["Simple / Pro view", "Simple hides the noise. Pro shows every signal and the AI explain button."],
              ].map(([label, desc]) => (
                <div key={label} style={{ display: "flex", gap: 10 }}>
                  <div style={{ width: 5, flexShrink: 0, background: T.blue, borderRadius: 3, marginTop: 3 }} />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{label}</div>
                    <div style={{ fontSize: 11, color: T.text2, marginTop: 2 }}>{desc}</div>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={dismissOnboarding}
              style={{
                width: "100%", fontSize: 13, fontWeight: 600, padding: "10px",
                background: T.blue, color: "#fff",
                border: "none", borderRadius: 8, cursor: "pointer",
              }}
            >
              Got it — start scanning
            </button>
          </div>
        </div>
      )}

      {/* Ticker history modal */}
      {historyTicker && <TickerHistoryModal ticker={historyTicker} onClose={() => setHistoryTicker(null)} />}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Daily Target Trade</div>
          <div style={{ fontSize: 11, color: T.text2, marginTop: 2 }}>
            ETF dip-buy scanner · 0 LLM tokens
            <span style={{ marginLeft: 8, fontSize: 10, color: T.text3 }}>· {scannerView} view</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {/* View toggle: simple → pro → guide */}
          {(["simple", "pro", "guide"] as const).map(v => (
            <button
              key={v}
              onClick={() => setScannerView(v)}
              style={{
                fontSize: 11, padding: "4px 10px",
                background: scannerView === v ? T.blue : T.surface2,
                color: scannerView === v ? "#fff" : T.text3,
                border: `1px solid ${scannerView === v ? T.blue : T.border}`,
                borderRadius: 5, cursor: "pointer",
              }}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
          <button
            onClick={scan}
            disabled={loading}
            style={{
              fontSize: 12, fontWeight: 500, padding: "7px 16px",
              background: loading ? T.surface2 : T.blue,
              color: loading ? T.text2 : "#fff",
              border: `1px solid ${loading ? T.border : T.blue}`,
              borderRadius: 7, cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Scanning…" : "Scan Now"}
          </button>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ fontSize: 12, color: T.text2 }}>Capital</span>
          <div style={{ display: "flex", alignItems: "center", gap: 0, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, overflow: "hidden" }}>
            <span style={{ padding: "5px 8px", fontSize: 12, color: T.text3 }}>$</span>
            <input
              type="number"
              value={capital}
              onChange={e => handleCapitalChange(parseFloat(e.target.value) || DEFAULT_CAPITAL)}
              style={{
                background: "transparent", border: "none", outline: "none",
                color: T.text, fontSize: 13, fontFamily: T.mono,
                width: 80, padding: "5px 8px 5px 0",
              }}
            />
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: T.text2 }}>Tier</span>
          {[1, 2].map(t => (
            <button
              key={t}
              onClick={() => setTiers(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])}
              style={{
                fontSize: 11, padding: "4px 10px",
                background: tiers.includes(t) ? T.blue : T.surface2,
                color: tiers.includes(t) ? "#fff" : T.text2,
                border: `1px solid ${tiers.includes(t) ? T.blue : T.border}`,
                borderRadius: 5, cursor: "pointer",
              }}
            >
              Tier {t}
            </button>
          ))}
          <button
            onClick={toggleLooseGates}
            title="Relaxes regime gate, RVOL-declining gate, and score threshold ~25%. Diagnostic only — results NOT saved to analytics. Use to see what would have qualified on a quiet day; do not trade these entries with full size."
            style={{
              fontSize: 11, padding: "4px 10px", marginLeft: 6,
              background: looseGates ? T.amber : T.surface2,
              color: looseGates ? "#1a1a1a" : T.text2,
              border: `1px solid ${looseGates ? T.amber : T.border}`,
              borderRadius: 5, cursor: "pointer", fontWeight: looseGates ? 600 : 400,
            }}
          >
            Loose Gates {looseGates ? "ON" : "OFF"}
          </button>
        </div>
        {result && (
          <div style={{ fontSize: 11, color: T.text3, marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
            {result.regime && <RegimeBadge regime={result.regime} />}
            <span><TermTip term="VIX" /> {result.vix} · {result.tickers_scanned} ETFs</span>
          </div>
        )}
      </div>

      {/* Loose-gates banner — only when scan was run with loose mode */}
      {result?.loose_gates_active && (
        <div style={{
          background: "rgba(245,158,11,0.12)",
          border: `1px solid ${T.amber}66`,
          borderLeft: `3px solid ${T.amber}`,
          borderRadius: 8, padding: "9px 14px", marginBottom: 10,
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <span style={{ fontSize: 15, flexShrink: 0 }}>⚠</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.amber, marginBottom: 2 }}>
              Loose Gates active — diagnostic only
            </div>
            <div style={{ fontSize: 11, color: T.text2, lineHeight: 1.5 }}>
              Thresholds relaxed ~25%, regime + RVOL-declining gates bypassed.
              Results <b>not saved</b> to analytics. Win rates not validated for this profile —
              do not trade these with full size.
            </div>
          </div>
        </div>
      )}

      {/* Situation summary — always shown after first scan or as idle state */}
      {!loading && (
        <SituationSummary
          scenarioKey={result ? result.scenario_key : null}
          compact={!!result}
        />
      )}

      {/* Trend-down blocking banner — regime gate active */}
      {result?.regime?.regime === "trend_down" && (
        <div style={{
          background: "rgba(239,68,68,0.07)",
          border: "1px solid rgba(239,68,68,0.35)",
          borderLeft: "3px solid #ef4444",
          borderRadius: 8, padding: "10px 14px", marginBottom: 10,
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <span style={{ fontSize: 16, flexShrink: 0 }}>⛔</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#ef4444", marginBottom: 2 }}>
              Trend Down Day — Dip buys blocked
            </div>
            <div style={{ fontSize: 11, color: T.text2 }}>
              {result.regime.reason}
              {" · "}VWAP reclaims and ORB breakouts still active if they meet score threshold.
            </div>
          </div>
        </div>
      )}

      {/* Trend-up tighter-criteria notice */}
      {result?.regime?.regime === "trend_up" && (
        <div style={{
          background: "rgba(245,158,11,0.07)",
          border: "1px solid rgba(245,158,11,0.35)",
          borderLeft: `3px solid ${T.amber}`,
          borderRadius: 8, padding: "8px 14px", marginBottom: 10,
          fontSize: 11, color: T.text2,
        }}>
          <span style={{ fontWeight: 600, color: T.amber }}>Trend Up Day</span>
          {" — dip entries require RSI < 30. "}
          {result.regime.reason}
        </div>
      )}

      {/* VIX spike prep alert */}
      {result?.vix_spike_prep && (
        <div style={{
          background: "rgba(245,158,11,0.08)",
          border: `1px solid ${T.amber}44`,
          borderLeft: `3px solid ${T.amber}`,
          borderRadius: 8, padding: "10px 14px", marginBottom: 10,
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <span style={{ fontSize: 16, flexShrink: 0 }}>⚡</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.amber, marginBottom: 2 }}>
              VIX Spike Prep — Fear surge in progress
            </div>
            <div style={{ fontSize: 11, color: T.text2 }}>
              VIX +{result.vix_spike_prep.vix_spike_pct.toFixed(1)}% intraday
              · SPY {result.vix_spike_prep.spy_change_pct.toFixed(2)}%
              · Stand by for dip-buy entry
            </div>
          </div>
        </div>
      )}

      {/* Extended hours warning */}
      {result && EXTENDED_HOURS.has(result.session_window) && (
        <div style={{
          background: "rgba(245,158,11,0.07)",
          border: `1px solid ${T.amber}44`,
          borderLeft: `3px solid ${T.amber}`,
          borderRadius: 8, padding: "9px 14px", marginBottom: 10,
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <span style={{ fontSize: 15, flexShrink: 0 }}>⚠</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.amber, marginBottom: 2 }}>
              Extended Hours — {result.session_window === "pre_market" ? "Pre-Market" : "After-Hours"}
            </div>
            <div style={{ fontSize: 11, color: T.text2 }}>
              Lower liquidity and wider spreads. Signals carry extra risk — confirm volume before entering.
              Scores are penalized –10 vs regular session.
            </div>
          </div>
        </div>
      )}

      {/* No result states */}
      {!loading && !result && (
        <div style={{ textAlign: "center", padding: "12px 0 4px", color: T.text3, fontSize: 11 }}>
          Alerts fire automatically every 5 min during market hours.
        </div>
      )}

      {!loading && result && !best && (
        <div style={{ textAlign: "center", padding: "8px 0 4px" }}>
          <div style={{ fontSize: 11, color: T.text3 }}>
            Session: {result.session_window.replace(/_/g, " ")} · VIX {result.vix} · threshold 65/100
          </div>
        </div>
      )}

      {/* Opportunity card */}
      {best && (() => {
        const wholeShares = Math.floor(best.shares)
        const adjProfit = wholeShares * (best.target_price - best.entry_price)
        const adjRisk   = wholeShares * (best.entry_price - best.stop_price)
        return (
        <div style={{
          background: T.surface2,
          border: `1px solid ${T.borderBright}`,
          borderLeft: `3px solid ${SIGNAL_TYPE_COLOR[best.signal_type] || SCORE_COLOR(best.score)}`,
          borderRadius: 10, padding: "14px 16px",
        }}>
          {/* State badge + CTA — #15 / #14 MISSED */}
          {(() => {
            const state = signalMissed ? "missed" : getSignalState(best)
            const cfg = STATE_CONFIG[state]
            const allChecked = checklistBoxes.every(Boolean)
            return (
              <>
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  marginBottom: 10, gap: 10,
                }}>
                  <div>
                    <div style={{
                      fontSize: 13, fontWeight: 700, letterSpacing: "0.08em",
                      padding: "5px 14px", borderRadius: 6,
                      background: cfg.bg, color: cfg.color,
                      border: `1px solid ${cfg.border}`,
                      display: "inline-block",
                    }}>
                      {cfg.label}
                    </div>
                    {signalMissed && (
                      <div style={{ fontSize: 10, color: T.text3, marginTop: 3 }}>
                        Price moved past entry — wait for next setup
                      </div>
                    )}
                    {best.entry_refined && (
                      <div style={{ fontSize: 10, color: T.blue, marginTop: 3 }}>
                        Entry refined via 1-min bars
                      </div>
                    )}
                  </div>
                  {!signalMissed && (
                    <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
                      <button
                        onClick={() => { setChecklist(true); setChecklistBoxes([false, false, false]) }}
                        style={{
                          fontSize: 12, fontWeight: 600, padding: "6px 14px",
                          background: cfg.color, color: "#000",
                          border: "none", borderRadius: 6, cursor: "pointer",
                        }}
                      >
                        Enter Trade →
                      </button>
                      {/* Paper trade button (#25) — logs without brokerage link */}
                      <button
                        onClick={() => paperTrade(best)}
                        style={{
                          fontSize: 11, padding: "6px 10px",
                          background: "transparent",
                          color: paperTraded === best.ticker ? T.green : T.text3,
                          border: `1px solid ${paperTraded === best.ticker ? T.green : T.border}`,
                          borderRadius: 6, cursor: "pointer",
                        }}
                        title="Log as a paper trade — no real money, tracks your record locally"
                      >
                        {paperTraded === best.ticker ? "Paper ✓" : "Paper Trade"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Pre-trade checklist modal — #22 */}
                {checklist && (
                  <div style={{
                    position: "fixed", inset: 0, zIndex: 500,
                    background: "rgba(0,0,0,0.6)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}
                    onClick={() => setChecklist(false)}
                  >
                    <div
                      onClick={e => e.stopPropagation()}
                      style={{
                        background: T.surface, border: `1px solid ${T.borderBright}`,
                        borderRadius: 12, padding: "22px 24px", width: 340, maxWidth: "90vw",
                      }}
                    >
                      <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 16 }}>
                        Before you enter — confirm your plan
                      </div>
                      {[
                        `Stop Loss at $${best.stop_price.toFixed(2)} — I'll exit and accept the $${adjRisk.toFixed(2)} loss`,
                        `Sell Limit at $${best.target_price.toFixed(2)} — I'll take the $${adjProfit.toFixed(2)} profit`,
                        `I won't add more shares no matter what`,
                      ].map((label, i) => (
                        <label key={i} style={{
                          display: "flex", alignItems: "flex-start", gap: 10,
                          marginBottom: 12, cursor: "pointer",
                        }}>
                          <input
                            type="checkbox"
                            checked={checklistBoxes[i]}
                            onChange={() => setChecklistBoxes(prev => {
                              const next = [...prev]; next[i] = !next[i]; return next
                            })}
                            style={{ marginTop: 2, flexShrink: 0, accentColor: T.green }}
                          />
                          <span style={{ fontSize: 12, color: T.text2, lineHeight: 1.5 }}>{label}</span>
                        </label>
                      ))}
                      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                        <button
                          onClick={() => setChecklist(false)}
                          style={{
                            flex: 1, fontSize: 12, padding: "8px",
                            background: T.surface2, color: T.text2,
                            border: `1px solid ${T.border}`, borderRadius: 6, cursor: "pointer",
                          }}
                        >
                          Cancel
                        </button>
                        <a
                          href={`https://robinhood.com/stocks/${best.ticker}`}
                          target="_blank" rel="noopener noreferrer"
                          onClick={() => setChecklist(false)}
                          style={{
                            flex: 2, fontSize: 12, fontWeight: 600, padding: "8px",
                            background: allChecked ? T.green : T.surface2,
                            color: allChecked ? "#000" : T.text3,
                            border: `1px solid ${allChecked ? T.green : T.border}`,
                            borderRadius: 6, cursor: allChecked ? "pointer" : "not-allowed",
                            textDecoration: "none", textAlign: "center", display: "block",
                            pointerEvents: allChecked ? "auto" : "none",
                          }}
                        >
                          Open {best.ticker} in Robinhood
                        </a>
                      </div>
                      <div style={{ fontSize: 10, color: T.text3, marginTop: 8, textAlign: "center" }}>
                        Check all three boxes to enable the link
                      </div>
                    </div>
                  </div>
                )}
              </>
            )
          })()}

          {/* Top row */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => setHistoryTicker(best.ticker)}
                  title="View scan history for this ticker"
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
                >
                  <span style={{ fontSize: 18, fontWeight: 700, fontFamily: T.mono, color: T.blue, textDecoration: "underline dotted", textUnderlineOffset: 3 }}>{best.ticker}</span>
                </button>
                <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 7px", background: "rgba(34,197,94,0.12)", color: T.green, border: "1px solid rgba(34,197,94,0.3)", borderRadius: 4 }}>
                  BUY
                </span>
                {best.signal_type && best.signal_type !== "dip_buy" && (
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: "2px 7px",
                    background: `${SIGNAL_TYPE_COLOR[best.signal_type]}22`,
                    color: SIGNAL_TYPE_COLOR[best.signal_type],
                    border: `1px solid ${SIGNAL_TYPE_COLOR[best.signal_type]}44`,
                    borderRadius: 4,
                  }}>
                    {SIGNAL_TYPE_LABEL[best.signal_type] || best.signal_type}
                  </span>
                )}
                {scannerView === "simple" && best.confidence_tier && CONFIDENCE_CONFIG[best.confidence_tier] ? (
                  <span style={{
                    fontSize: 12, fontWeight: 600, padding: "2px 8px",
                    background: CONFIDENCE_CONFIG[best.confidence_tier].bg,
                    color: CONFIDENCE_CONFIG[best.confidence_tier].color,
                    border: `1px solid ${CONFIDENCE_CONFIG[best.confidence_tier].border}`,
                    borderRadius: 5,
                  }}>
                    {CONFIDENCE_CONFIG[best.confidence_tier].label}
                  </span>
                ) : (
                  <span style={{
                    fontSize: 12, fontWeight: 600, padding: "2px 8px",
                    background: `${SCORE_COLOR(best.score)}22`,
                    color: SCORE_COLOR(best.score),
                    border: `1px solid ${SCORE_COLOR(best.score)}44`,
                    borderRadius: 5,
                  }}>
                    Score {best.score}/100
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: SESSION_COLORS[best.session_window] || T.text2, marginTop: 3 }}>
                {best.session_window_label}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: T.text3 }}><TermTip term="Dip from open" /></div>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.red, fontFamily: T.mono }}>
                -{best.dip_pct}%
              </div>
            </div>
          </div>

          {/* Buy Limit / Sell Limit / Stop Loss */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
            {[
              { label: "Buy Limit", value: best.entry_price, color: T.text },
              { label: "Sell Limit", value: best.target_price, color: T.green },
              { label: "Stop Loss", value: best.stop_price, color: "#ef4444" },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: T.surface, borderRadius: 7, padding: "8px 10px", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: T.text3, marginBottom: 3 }}>{label}</div>
                <div style={{ fontSize: 14, fontWeight: 600, fontFamily: T.mono, color }}>
                  ${value.toFixed(2)}
                </div>
                {/* Live distance-to-entry (#18) — only shown on entry cell */}
                {label === "Entry" && livePrice !== null && !signalMissed && (() => {
                  const distPct = ((value - livePrice) / value * 100)
                  if (Math.abs(distPct) < 0.01) return <div style={{ fontSize: 9, color: T.green, marginTop: 2, fontFamily: T.mono }}>at entry</div>
                  return (
                    <div style={{ fontSize: 9, marginTop: 2, fontFamily: T.mono, color: distPct > 0 ? T.amber : T.text3 }}>
                      {distPct > 0 ? `${distPct.toFixed(2)}% away` : `${Math.abs(distPct).toFixed(2)}% past`}
                    </div>
                  )
                })()}
                {label !== "Entry" && (
                  <div style={{ fontSize: 10, color: T.text3, marginTop: 3, fontFamily: T.mono }}>
                    {wholeShares} sh
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Intraday mini chart */}
          {chartData.length > 0 && (() => {
            const prices = chartData.map(c => c.close)
            const yMin = Math.min(...prices)
            const yMax = Math.max(...prices)
            const pad = (yMax - yMin) * 0.1 || 0.5
            const fmtTime = (iso: string) => {
              const d = new Date(iso)
              return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
            }
            return (
              <div style={{ marginBottom: 12 }}>
                <ResponsiveContainer width="100%" height={110}>
                  <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={T.blue} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={T.blue} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <YAxis domain={[yMin - pad, yMax + pad]} hide />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null
                        const d = payload[0].payload as Candle
                        return (
                          <div style={{
                            background: T.surface2, border: `1px solid ${T.border}`,
                            borderRadius: 6, padding: "5px 9px", fontSize: 11,
                          }}>
                            <div style={{ color: T.text3 }}>{fmtTime(d.time)}</div>
                            <div style={{ color: T.text, fontFamily: T.mono, fontWeight: 600 }}>${d.close.toFixed(2)}</div>
                          </div>
                        )
                      }}
                    />
                    <ReferenceLine y={best.target_price} stroke={T.green}  strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "T", position: "right", fill: T.green,  fontSize: 9 }} />
                    <ReferenceLine y={best.entry_price}  stroke={T.text2}  strokeDasharray="4 3" strokeWidth={1}   label={{ value: "E", position: "right", fill: T.text2,  fontSize: 9 }} />
                    <ReferenceLine y={best.stop_price}   stroke={T.red}    strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "S", position: "right", fill: T.red,    fontSize: 9 }} />
                    <ReferenceLine y={best.intraday_vwap} stroke={T.amber} strokeDasharray="3 3" strokeWidth={1}   label={{ value: "V", position: "right", fill: T.amber,  fontSize: 9 }} />
                    <Area type="monotone" dataKey="close" stroke={T.blue} strokeWidth={1.5} fill="url(#chartGrad)" dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
                <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", fontSize: 10, color: T.text3, marginTop: 2 }}>
                  <span style={{ color: T.green }}>─ Sell Limit</span>
                  <span style={{ color: T.text2 }}>─ Buy Limit</span>
                  <span style={{ color: "#ef4444" }}>─ Stop Loss</span>
                  <span style={{ color: T.amber }}>─ VWAP</span>
                </div>
                {/* Invalidation line — Opus #16 */}
                {best.invalidation && (
                  <div style={{ fontSize: 11, color: T.text3, marginTop: 6, lineHeight: 1.5 }}>
                    <span style={{ color: T.text2, fontWeight: 500 }}>Setup invalid if: </span>
                    price closes below <span style={{ fontFamily: T.mono, color: T.red }}>${best.invalidation.price_close_below.toFixed(2)}</span>
                    {" · "}VIX above <span style={{ fontFamily: T.mono, color: T.amber }}>{best.invalidation.vix_above.toFixed(1)}</span>
                    {" · "}RVOL resurges above <span style={{ fontFamily: T.mono, color: T.amber }}>{best.invalidation.rvol_resurge_above}×</span>
                  </div>
                )}
              </div>
            )
          })()}

          {/* P&L row */}
          {wholeShares === 0 ? (
            <div style={{
              fontSize: 12, color: T.amber, background: `${T.amber}11`,
              border: `1px solid ${T.amber}44`, borderRadius: 6,
              padding: "6px 10px", marginBottom: 12,
            }}>
              Capital too low — need at least ${best.entry_price.toFixed(2)} to buy 1 share
            </div>
          ) : (
            <div style={{ marginBottom: 12 }}>
              {/* Primary: dollars first — Opus #21 */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5, flexWrap: "wrap" }}>
                <span style={{ fontSize: 13, color: T.text2 }}>Risk</span>
                <span style={{ fontSize: 16, fontWeight: 700, fontFamily: T.mono, color: T.red }}>−${adjRisk.toFixed(2)}</span>
                <span style={{ fontSize: 16, color: T.text3 }}>→</span>
                <span style={{ fontSize: 13, color: T.text2 }}>Make</span>
                <span style={{ fontSize: 16, fontWeight: 700, fontFamily: T.mono, color: T.green }}>+${adjProfit.toFixed(2)}</span>
                <span style={{ fontSize: 11, color: T.text3, marginLeft: 4 }}>({wholeShares} shares · R:R {best.risk_reward_ratio}:1)</span>
              </div>
            </div>
          )}

          {/* Time stop — #12 */}
          {best.time_stop_minutes && (
            <div style={{ fontSize: 11, color: T.text3, marginBottom: 8 }}>
              Exit if no <span style={{ color: T.text2 }}>+0.3%</span> move within{" "}
              <span style={{ color: T.amber, fontFamily: T.mono }}>{best.time_stop_minutes} min</span> of entry
              {best.atr_5m && best.atr_5m > 0 && (
                <span style={{ marginLeft: 10, color: T.text3 }}>
                  · <TermTip term="ATR" /> <span style={{ fontFamily: T.mono }}>${best.atr_5m.toFixed(2)}</span>
                  {best.atr_adjusted && <span style={{ color: T.blue, marginLeft: 4 }}>scaled</span>}
                </span>
              )}
            </div>
          )}

          {/* Signals — hidden in simple view, shown in pro + guide */}
          {(scannerView === "pro" || scannerView === "guide") && (
            <div style={{ marginBottom: 10 }}>
              <button
                onClick={() => setExpandedSignals(!expandedSignals)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, marginBottom: 6 }}
              >
                <span style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Signals {expandedSignals ? "▲" : "▼"}
                </span>
              </button>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {best.signals.map((sig, i) => {
                  const hintKey = Object.keys(best.signal_hints || {}).find(k => sig.includes(k) || k.includes("RSI") && sig.includes("RSI"))
                  const hint = hintKey ? best.signal_hints[hintKey] : ""
                  return (
                    <span key={i} style={{
                      fontSize: 11, padding: "3px 8px",
                      background: T.surface, border: `1px solid ${T.border}`,
                      borderRadius: 5, color: T.text2,
                    }}>
                      {sig}
                      <HintTooltip hint={hint} />
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          {/* In simple view show top reasons (filtered positive signals) */}
          {scannerView === "simple" && (() => {
            const reasons = best.top_reasons?.length ? best.top_reasons : best.signals.slice(0, 2)
            if (!reasons.length) return null
            return <div style={{ fontSize: 11, color: T.text2, marginBottom: 10 }}>Why: {reasons.join(" · ")}</div>
          })()}

          {/* Guide view — full educational overlay */}
          {scannerView === "guide" && <GuideView opp={best} />}

          {/* AI signal analysis — pro view only, click-triggered */}
          {scannerView === "pro" && <div style={{ marginTop: 4 }}>
            {llmAnalysis ? (
              <div style={{
                background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 8, padding: "12px 14px",
              }}>
                {/* Verdict pill */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 5,
                    background: llmAnalysis.verdict === "FAVORABLE" ? "rgba(34,197,94,0.15)" : llmAnalysis.verdict === "UNFAVORABLE" ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)",
                    color: llmAnalysis.verdict === "FAVORABLE" ? T.green : llmAnalysis.verdict === "UNFAVORABLE" ? "#ef4444" : T.amber,
                    border: `1px solid ${llmAnalysis.verdict === "FAVORABLE" ? T.green : llmAnalysis.verdict === "UNFAVORABLE" ? "#ef4444" : T.amber}44`,
                  }}>
                    {llmAnalysis.verdict}
                  </span>
                  {llmAnalysis.history_count >= 3 && llmAnalysis.win_rate_pct !== null && (
                    <span style={{ fontSize: 10, color: T.text3 }}>
                      {llmAnalysis.history_count} past signals · {llmAnalysis.win_rate_pct}% win rate
                    </span>
                  )}
                  <button
                    onClick={() => setLlmAnalysis(null)}
                    style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: T.text3, fontSize: 13, padding: 0 }}
                    title="Dismiss"
                  >×</button>
                </div>
                {/* Body */}
                <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.6, marginBottom: 8 }}>
                  {llmAnalysis.plain_english}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  <div style={{ fontSize: 11, color: T.text2 }}>
                    <span style={{ color: "#ef4444", fontWeight: 600 }}>Key risk: </span>
                    {llmAnalysis.key_risk}
                  </div>
                  <div style={{ fontSize: 11, color: T.text2 }}>
                    <span style={{ color: T.amber, fontWeight: 600 }}>Watch for: </span>
                    {llmAnalysis.watch_for}
                  </div>
                </div>
                {llmAnalysis.tokens_used > 0 && (
                  <div style={{ fontSize: 10, color: T.text3, marginTop: 8 }}>~{llmAnalysis.tokens_used} tokens used</div>
                )}
              </div>
            ) : (
              <button
                onClick={() => analyzeSetup(best)}
                disabled={llmLoading || execMode === "saver"}
                title={execMode === "saver" ? "Switch to Normal or Deep mode for AI analysis" : ""}
                style={{
                  fontSize: 11, padding: "5px 14px",
                  background: "transparent",
                  color: execMode === "saver" ? T.text3 : T.blue,
                  border: `1px solid ${execMode === "saver" ? T.border : T.blue}`,
                  borderRadius: 6, cursor: execMode === "saver" ? "not-allowed" : "pointer",
                }}
              >
                {llmLoading ? "Analyzing…" : execMode === "saver" ? "Enable Normal mode for AI analysis" : "What does this mean? (~500 tokens)"}
              </button>
            )}
          </div>}
        </div>
        )
      })()}

      {/* Signal history */}
      {history.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <button
            onClick={() => setShowHistory(h => !h)}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 0, marginBottom: 6 }}
          >
            <span style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Signal History ({history.length}) {showHistory ? "▲" : "▼"}
            </span>
          </button>
          {showHistory && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {history.map(h => (
                <div key={h.id} style={{
                  background: T.surface2, border: `1px solid ${T.border}`,
                  borderLeft: `3px solid ${SIGNAL_TYPE_COLOR[h.signal_type] || T.text3}`,
                  borderRadius: 8, padding: "9px 12px",
                  display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, fontFamily: T.mono, color: T.blue }}>{h.ticker}</span>
                      <span style={{ fontSize: 10, color: SCORE_COLOR(h.score) }}>Score {h.score}</span>
                      <span style={{ fontSize: 10, color: T.text3 }}>{h.session_window_label}</span>
                      <span style={{ fontSize: 10, color: T.text3, marginLeft: "auto" }}>{formatHistoryTime(h.timestamp)}</span>
                    </div>
                    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                      {[
                        { label: "Buy Limit", value: h.entry_price, color: T.text },
                        { label: "Sell Limit", value: h.target_price, color: T.green },
                        { label: "Stop Loss", value: h.stop_price, color: "#ef4444" },
                      ].map(({ label, value, color }) => (
                        <div key={label}>
                          <span style={{ fontSize: 10, color: T.text3 }}>{label} </span>
                          <span style={{ fontSize: 12, fontFamily: T.mono, fontWeight: 600, color }}>${value.toFixed(2)}</span>
                          <span style={{ fontSize: 10, color: T.text3, marginLeft: 4 }}>{h.shares.toFixed(2)}sh</span>
                        </div>
                      ))}
                      <div>
                        <span style={{ fontSize: 10, color: T.text3 }}>R:R </span>
                        <span style={{ fontSize: 12, fontFamily: T.mono, color: T.amber }}>{h.risk_reward_ratio}:1</span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => setHistory(prev => {
                      const updated = prev.filter(e => e.id !== h.id)
                      saveHistory(updated)
                      return updated
                    })}
                    title="Remove this signal"
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: T.text3, fontSize: 14, padding: "0 4px", flexShrink: 0,
                      lineHeight: 1,
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Other opportunities (dip_buy + orb + vwap) */}
      {/* Similar past setups — reference cases for current signal (#17) */}
      {result?.best && (
        <RecentOutcomes
          ticker={result.best.ticker}
          session={result.best.session_window}
          signalType={result.best.signal_type}
        />
      )}

      {result && (() => {
        const others = [
          ...result.opportunities.slice(1),
          ...result.orb_opportunities.filter(o => o.ticker !== best?.ticker),
          ...result.vwap_opportunities.filter(o => o.ticker !== best?.ticker),
          ...(result.failed_breakdown_opportunities ?? []).filter(o => o.ticker !== best?.ticker),
        ]
        if (others.length === 0) return null
        return (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11, color: T.text3, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>Other setups</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {others.map((o, i) => {
                const typeColor = SIGNAL_TYPE_COLOR[o.signal_type] || T.text2
                const typeLabel = SIGNAL_TYPE_LABEL[o.signal_type] || "Dip Buy"
                return (
                  <div key={`${o.ticker}-${i}`} style={{
                    background: T.surface2, border: `1px solid ${T.border}`,
                    borderLeft: `3px solid ${typeColor}`,
                    borderRadius: 8, padding: "9px 12px",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <button
                          onClick={() => setHistoryTicker(o.ticker)}
                          title="View scan history for this ticker"
                          style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
                        >
                          <span style={{ fontSize: 13, fontWeight: 700, fontFamily: T.mono, color: T.blue, textDecoration: "underline dotted", textUnderlineOffset: 3 }}>{o.ticker}</span>
                        </button>
                        <span style={{ fontSize: 11, fontWeight: 700, padding: "1px 5px", background: "rgba(34,197,94,0.12)", color: T.green, border: "1px solid rgba(34,197,94,0.3)", borderRadius: 3 }}>BUY</span>
                        <span style={{ fontSize: 10, color: typeColor }}>{typeLabel}</span>
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 600, color: SCORE_COLOR(o.score), fontFamily: T.mono }}>{o.score}/100</span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 5 }}>
                      {[
                        { label: "Buy Limit", value: o.entry_price, color: T.text },
                        { label: "Sell Limit", value: o.target_price, color: T.green },
                        { label: "Stop Loss", value: o.stop_price, color: "#ef4444" },
                      ].map(({ label, value, color }) => (
                        <div key={label} style={{ background: T.surface, borderRadius: 5, padding: "4px 7px", textAlign: "center" }}>
                          <div style={{ fontSize: 9, color: T.text3, marginBottom: 1 }}>{label}</div>
                          <div style={{ fontSize: 12, fontWeight: 600, fontFamily: T.mono, color }}>${value.toFixed(2)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
