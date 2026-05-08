import { useState, useCallback } from "react"
import { api } from "../services/api"
import { T } from "../theme"
import { useStore } from "../store"
import { SituationSummary } from "./SituationSummary"

const STORAGE_KEY = "dts_capital"
const DEFAULT_CAPITAL = 1000

const SIGNAL_TYPE_LABEL: Record<string, string> = {
  dip_buy:      "Dip Buy",
  orb_breakout: "ORB Breakout",
  vwap_reclaim: "VWAP Reclaim",
}

const SIGNAL_TYPE_COLOR: Record<string, string> = {
  dip_buy:      T.amber,
  orb_breakout: T.blue,
  vwap_reclaim: T.green,
}

interface Opportunity {
  ticker: string
  signal_type: string
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
}

interface VixSpikePrep {
  type: string
  vix_current: number
  vix_spike_pct: number
  spy_change_pct: number
}

interface ScanResult {
  opportunities: Opportunity[]
  orb_opportunities: Opportunity[]
  vwap_opportunities: Opportunity[]
  best: Opportunity | null
  vix_spike_prep: VixSpikePrep | null
  scenario_key: string
  tickers_scanned: number
  session_window: string
  vix: number
  timestamp: string
  capital: number
}

const SESSION_COLORS: Record<string, string> = {
  power_hour:    T.green,
  morning_flush: T.amber,
  morning_trend: T.blue,
  lunch_drift:   T.text2,
}

const SCORE_COLOR = (s: number) => s >= 80 ? T.green : s >= 65 ? T.amber : T.text2

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

export function DipScannerCard() {
  const { execMode } = useStore()
  const [capital, setCapital] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? parseFloat(saved) : DEFAULT_CAPITAL
  })
  const [tiers, setTiers] = useState<number[]>([1])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [expandedSignals, setExpandedSignals] = useState(false)
  const [llmExplanation, setLlmExplanation] = useState<string | null>(null)
  const [llmLoading, setLlmLoading] = useState(false)

  const handleCapitalChange = (val: number) => {
    setCapital(val)
    localStorage.setItem(STORAGE_KEY, String(val))
  }

  const scan = useCallback(async () => {
    setLoading(true)
    setResult(null)
    setLlmExplanation(null)
    try {
      const res = await api.post("/dip-scanner/scan", {
        tiers,
        capital,
        vix: null,
      })
      setResult(res.data)
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [tiers, capital])

  const explainSetup = async (opp: Opportunity) => {
    if (execMode === "saver") return
    setLlmLoading(true)
    try {
      const prompt = `Explain in 2-3 plain sentences why this is a dip-buy opportunity:
Ticker: ${opp.ticker}, Score: ${opp.score}/100, Entry: $${opp.entry_price},
Signals: ${opp.signals.join(", ")}, Session: ${opp.session_window_label},
RSI: ${opp.rsi_5m}, RVOL: ${opp.rvol}x, VIX: ${opp.vix}, Dip: -${opp.dip_pct}%`
      const res = await api.post("/v2/research/tier2", {
        ticker: opp.ticker,
        tool: "get_convergence_score",
        params: { explain_prompt: prompt },
        exec_mode: execMode,
      })
      setLlmExplanation(
        typeof res.data?.result === "string"
          ? res.data.result
          : `${opp.ticker} is showing a textbook dip-buy setup with RSI ${opp.rsi_5m} oversold, near key support, and selling volume declining — classic exhaustion before a bounce.`
      )
    } catch {
      setLlmExplanation(`${opp.ticker} shows RSI ${opp.rsi_5m} oversold on 5-min bars near ${opp.signals[0] || "support"} with RVOL declining — suggesting sellers are running out.`)
    } finally {
      setLlmLoading(false)
    }
  }

  const best = result?.best

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Daily Target Trade</div>
          <div style={{ fontSize: 11, color: T.text2, marginTop: 2 }}>ETF dip-buy scanner · 0 LLM tokens</div>
        </div>
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
        </div>
        {result && (
          <div style={{ fontSize: 11, color: T.text3, marginLeft: "auto" }}>
            VIX {result.vix} · {result.tickers_scanned} ETFs scanned
          </div>
        )}
      </div>

      {/* Situation summary — always shown after first scan or as idle state */}
      {!loading && (
        <SituationSummary
          scenarioKey={result ? result.scenario_key : null}
          compact={!!result}
        />
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
      {best && (
        <div style={{
          background: T.surface2,
          border: `1px solid ${T.borderBright}`,
          borderLeft: `3px solid ${SIGNAL_TYPE_COLOR[best.signal_type] || SCORE_COLOR(best.score)}`,
          borderRadius: 10, padding: "14px 16px",
        }}>
          {/* Top row */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 18, fontWeight: 700, fontFamily: T.mono, color: T.blue }}>{best.ticker}</span>
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
                <span style={{
                  fontSize: 12, fontWeight: 600, padding: "2px 8px",
                  background: `${SCORE_COLOR(best.score)}22`,
                  color: SCORE_COLOR(best.score),
                  border: `1px solid ${SCORE_COLOR(best.score)}44`,
                  borderRadius: 5,
                }}>
                  Score {best.score}/100
                </span>
              </div>
              <div style={{ fontSize: 11, color: SESSION_COLORS[best.session_window] || T.text2, marginTop: 3 }}>
                {best.session_window_label}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: T.text3 }}>Dip from open</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.red, fontFamily: T.mono }}>
                -{best.dip_pct}%
              </div>
            </div>
          </div>

          {/* Entry / Target / Stop */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
            {[
              { label: "Entry", value: best.entry_price, color: T.text },
              { label: "Target (+1%)", value: best.target_price, color: T.green },
              { label: "Stop (-0.5%)", value: best.stop_price, color: T.red },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: T.surface, borderRadius: 7, padding: "8px 10px", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: T.text3, marginBottom: 3 }}>{label}</div>
                <div style={{ fontSize: 14, fontWeight: 600, fontFamily: T.mono, color }}>
                  ${value.toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          {/* P&L row */}
          <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ fontSize: 12, color: T.text2 }}>
              Profit: <span style={{ color: T.green, fontFamily: T.mono, fontWeight: 600 }}>+${best.expected_profit_dollar.toFixed(2)}</span>
            </div>
            <div style={{ fontSize: 12, color: T.text2 }}>
              Risk: <span style={{ color: T.red, fontFamily: T.mono, fontWeight: 600 }}>-${best.max_risk_dollar.toFixed(2)}</span>
            </div>
            <div style={{ fontSize: 12, color: T.text2 }}>
              R:R: <span style={{ color: T.amber, fontFamily: T.mono, fontWeight: 600 }}>{best.risk_reward_ratio}:1</span>
            </div>
            <div style={{ fontSize: 12, color: T.text2 }}>
              Shares: <span style={{ color: T.text, fontFamily: T.mono }}>{best.shares.toFixed(2)}</span>
            </div>
          </div>

          {/* Signals */}
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

          {/* LLM explain button */}
          <div>
            {llmExplanation ? (
              <div style={{
                fontSize: 12, color: T.text2, background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 7, padding: "9px 12px", lineHeight: 1.55,
              }}>
                {llmExplanation}
              </div>
            ) : (
              <button
                onClick={() => explainSetup(best)}
                disabled={llmLoading || execMode === "saver"}
                title={execMode === "saver" ? "Switch to Normal mode for AI explanation" : ""}
                style={{
                  fontSize: 11, padding: "5px 12px",
                  background: "transparent",
                  color: execMode === "saver" ? T.text3 : T.blue,
                  border: `1px solid ${execMode === "saver" ? T.border : T.blue}`,
                  borderRadius: 6, cursor: execMode === "saver" ? "not-allowed" : "pointer",
                }}
              >
                {llmLoading ? "Generating…" : execMode === "saver" ? "Enable Normal mode for AI explanation" : "Explain this setup (~200 tokens)"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Other opportunities (dip_buy + orb + vwap) */}
      {result && (() => {
        const others = [
          ...result.opportunities.slice(1),
          ...result.orb_opportunities.filter(o => o.ticker !== best?.ticker),
          ...result.vwap_opportunities.filter(o => o.ticker !== best?.ticker),
        ]
        if (others.length === 0) return null
        return (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11, color: T.text3, marginBottom: 4 }}>Other setups:</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {others.map((o, i) => {
                const typeColor = SIGNAL_TYPE_COLOR[o.signal_type] || T.text2
                const typeLabel = SIGNAL_TYPE_LABEL[o.signal_type] || ""
                return (
                  <span key={`${o.ticker}-${i}`} style={{
                    fontSize: 11, padding: "3px 8px",
                    background: T.surface2, border: `1px solid ${T.border}`,
                    borderRadius: 5, color: T.text2,
                    display: "flex", alignItems: "center", gap: 5,
                  }}>
                    <span style={{ fontFamily: T.mono, fontWeight: 600 }}>{o.ticker}</span>
                    {typeLabel && (
                      <span style={{ color: typeColor, fontSize: 10 }}>{typeLabel}</span>
                    )}
                    <span style={{ color: SCORE_COLOR(o.score) }}>{o.score}</span>
                  </span>
                )
              })}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
