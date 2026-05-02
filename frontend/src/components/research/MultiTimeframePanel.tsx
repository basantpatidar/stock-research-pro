import { T } from "../../theme"

interface TFResult {
  direction: string
  bullish_signals: number
  total_signals: number
  rsi?: number
  rsi_bullish?: boolean
  macd_bullish?: boolean
  price_above_vwap?: boolean
  score?: number
}

interface MtfData {
  ticker: string
  confluence_score: number
  label: string
  alignment: string
  timeframes: Record<string, TFResult>
}

const SIGNAL_DOT = ({ on }: { on: boolean }) => (
  <span style={{
    display: "inline-block", width: 8, height: 8, borderRadius: "50%",
    background: on ? T.green : T.red,
    boxShadow: on ? `0 0 4px ${T.green}` : "none",
    flexShrink: 0,
  }} />
)

const TF_ORDER = ["5m", "15m", "1h", "1d"] as const

function scoreColor(score: number): string {
  if (score >= 75) return T.green
  if (score >= 55) return "#4ade80"     // light green
  if (score >= 45) return T.amber
  if (score >= 25) return "#f97316"     // orange
  return T.red
}

function directionStyle(dir: string): { color: string; bg: string } {
  if (dir === "BULLISH")  return { color: T.green, bg: "rgba(74,222,128,0.08)" }
  if (dir === "BEARISH")  return { color: T.red,   bg: "rgba(248,113,113,0.08)" }
  return { color: T.amber, bg: "rgba(251,191,36,0.08)" }
}

export function MultiTimeframePanel({ data }: { data: MtfData | null }) {
  if (!data) return null
  if ("error" in (data as any)) {
    return <div style={{ fontSize: 12, color: T.red }}>{(data as any).error}</div>
  }

  const score = data.confluence_score
  const color = scoreColor(score)

  return (
    <div>
      {/* Score bar */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
          <span style={{ fontSize: 32, fontWeight: 700, fontFamily: T.mono, color }}>{score}</span>
          <span style={{ fontSize: 13, color: T.text2 }}>/ 100</span>
          <span style={{
            padding: "2px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
            fontFamily: T.mono, letterSpacing: "0.06em",
            background: `${color}18`, color, border: `1px solid ${color}`,
          }}>
            {data.label}
          </span>
        </div>
        <div style={{ height: 6, background: T.border, borderRadius: 3, overflow: "hidden" }}>
          <div style={{
            width: `${score}%`, height: "100%", borderRadius: 3,
            background: color, transition: "width 0.6s ease",
          }} />
        </div>
        <div style={{ fontSize: 11, color: T.text3, marginTop: 5 }}>{data.alignment}</div>
      </div>

      {/* Per-timeframe grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {TF_ORDER.map(tf => {
          const r = data.timeframes[tf]
          if (!r) return null
          const isData = r.direction !== "ERROR" && r.direction !== "INSUFFICIENT_DATA"
          const ds = directionStyle(isData ? r.direction : "NEUTRAL")

          return (
            <div key={tf} style={{
              borderRadius: 8, padding: "10px 12px",
              background: isData ? ds.bg : T.surface,
              border: `1px solid ${isData ? ds.color + "30" : T.border}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 13, fontWeight: 600, color: T.text }}>{tf}</span>
                {isData && (
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.07em", color: ds.color }}>
                    {r.direction}
                  </span>
                )}
              </div>

              {isData ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: T.text2 }}>
                    <SIGNAL_DOT on={r.rsi_bullish ?? false} />
                    <span>RSI {r.rsi != null ? r.rsi.toFixed(0) : "—"}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: T.text2 }}>
                    <SIGNAL_DOT on={r.macd_bullish ?? false} />
                    <span>MACD</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: T.text2 }}>
                    <SIGNAL_DOT on={r.price_above_vwap ?? false} />
                    <span>VWAP</span>
                  </div>
                  <div style={{ marginTop: 4, fontSize: 10, color: T.text3, fontFamily: T.mono }}>
                    {r.bullish_signals}/{r.total_signals ?? 3} bullish
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: 10, color: T.text3 }}>
                  {r.direction === "ERROR" ? "Fetch error" : "Not enough data"}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 10, fontSize: 10, color: T.text3 }}>
        Weights: 1d 40% · 1h 30% · 15m 20% · 5m 10% — signals: RSI &gt;50, MACD crossover, price vs VWAP
      </div>
    </div>
  )
}
