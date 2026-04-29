import { T } from "../../theme"

// ── Bull/Bear Debate ──────────────────────────────────────────────────────────

interface BullBearProps { data: any }

export function BullBearPanel({ data }: BullBearProps) {
  if (!data) return null
  const bull   = data.bull_case  ?? {}
  const bear   = data.bear_case  ?? {}
  const verdict = data.verdict   ?? {}

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {/* Bull case */}
        <div style={{ background: T.greenDim, border: `1px solid ${T.green}`, borderRadius: 10, padding: "12px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.green, letterSpacing: "0.06em", marginBottom: 8 }}>
            ▲ BULL CASE
          </div>
          {bull.thesis && (
            <div style={{ fontSize: 12, color: T.text, marginBottom: 8, lineHeight: 1.5 }}>{bull.thesis}</div>
          )}
          {bull.key_points?.map((pt: string, i: number) => (
            <div key={i} style={{ display: "flex", gap: 6, fontSize: 11, color: T.text2, marginTop: 4, lineHeight: 1.4 }}>
              <span style={{ color: T.green, flexShrink: 0 }}>+</span>
              <span>{pt}</span>
            </div>
          ))}
        </div>

        {/* Bear case */}
        <div style={{ background: T.redDim, border: `1px solid ${T.red}`, borderRadius: 10, padding: "12px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: T.red, letterSpacing: "0.06em", marginBottom: 8 }}>
            ▼ BEAR CASE
          </div>
          {bear.thesis && (
            <div style={{ fontSize: 12, color: T.text, marginBottom: 8, lineHeight: 1.5 }}>{bear.thesis}</div>
          )}
          {bear.key_points?.map((pt: string, i: number) => (
            <div key={i} style={{ display: "flex", gap: 6, fontSize: 11, color: T.text2, marginTop: 4, lineHeight: 1.4 }}>
              <span style={{ color: T.red, flexShrink: 0 }}>−</span>
              <span>{pt}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Judge verdict */}
      {(verdict.winner || verdict.reasoning) && (
        <div style={{
          background: T.surface2, border: `1px solid ${T.borderBright}`,
          borderRadius: 10, padding: "12px 14px",
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: T.text2, letterSpacing: "0.06em", marginBottom: 6 }}>
            ⚖ JUDGE VERDICT
            {verdict.winner && (
              <span style={{
                marginLeft: 8, fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20,
                background: verdict.winner === "bull" ? T.greenDim : T.redDim,
                color: verdict.winner === "bull" ? T.green : T.red,
                border: `1px solid ${verdict.winner === "bull" ? T.green : T.red}`,
              }}>
                {verdict.winner.toUpperCase()} WINS
              </span>
            )}
          </div>
          {verdict.reasoning && (
            <div style={{ fontSize: 12, color: T.text, lineHeight: 1.55 }}>{verdict.reasoning}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Backtester ────────────────────────────────────────────────────────────────

interface BacktestProps { data: any }

export function BacktesterPanel({ data }: BacktestProps) {
  if (!data?.strategies) return <div style={{ fontSize: 12, color: T.text2 }}>No backtest data.</div>
  const strategies: [string, any][] = Object.entries(data.strategies)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {data.period && (
        <div style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>Backtest period: {data.period}</div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
        {strategies.map(([name, s]) => {
          const ret = s.total_return ?? s.return_pct ?? 0
          const positive = ret >= 0
          return (
            <div key={name} style={{
              background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 10,
              padding: "12px 14px",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                {name.replace(/_/g, " ")}
              </div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: T.mono, color: positive ? T.green : T.red, marginBottom: 4 }}>
                {positive ? "+" : ""}{ret.toFixed(1)}%
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {s.win_rate != null && (
                  <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono }}>
                    Win: <span style={{ color: T.text }}>{(s.win_rate * 100).toFixed(0)}%</span>
                  </span>
                )}
                {s.trades != null && (
                  <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono }}>
                    Trades: <span style={{ color: T.text }}>{s.trades}</span>
                  </span>
                )}
              </div>
              {s.signal && (
                <div style={{ marginTop: 8 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
                    background: s.signal === "buy" ? T.greenDim : s.signal === "sell" ? T.redDim : T.surface,
                    color: s.signal === "buy" ? T.green : s.signal === "sell" ? T.red : T.text2,
                    border: `1px solid ${s.signal === "buy" ? T.green : s.signal === "sell" ? T.red : T.borderBright}`,
                  }}>
                    {s.signal.toUpperCase()} SIGNAL
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Congressional Trades ──────────────────────────────────────────────────────

interface CongressionalProps { data: any }

const PARTY_STYLE: Record<string, { color: string; bg: string }> = {
  R: { color: "#f87171", bg: "rgba(248,113,113,0.12)" },
  D: { color: "#60a5fa", bg: "rgba(96,165,250,0.12)" },
}

export function CongressionalPanel({ data }: CongressionalProps) {
  if (!data?.recent_trades?.length) {
    return <div style={{ fontSize: 12, color: T.text2 }}>No recent congressional trades on record.</div>
  }

  const sentimentStyle = data.net_sentiment === "bullish"
    ? { color: T.green, bg: T.greenDim }
    : data.net_sentiment === "bearish"
    ? { color: T.red, bg: T.redDim }
    : { color: T.text2, bg: T.surface2 }

  return (
    <div>
      {data.net_sentiment && (
        <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: T.text2 }}>Congressional sentiment:</span>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: "2px 10px", borderRadius: 20,
            background: sentimentStyle.bg, color: sentimentStyle.color,
          }}>
            {data.net_sentiment.toUpperCase()}
          </span>
          <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>{data.total_trades} trades</span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, auto)", gap: 0, borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border}` }}>
        {/* Header */}
        {["Politician", "Party", "Date", "Type", "Amount"].map(h => (
          <div key={h} style={{
            fontSize: 10, color: T.text3, fontWeight: 500, textTransform: "uppercase",
            letterSpacing: "0.06em", padding: "7px 10px", background: T.surface2,
            borderBottom: `1px solid ${T.border}`,
          }}>{h}</div>
        ))}
        {/* Rows */}
        {data.recent_trades.slice(0, 8).map((t: any, i: number) => {
          const ps = PARTY_STYLE[t.party] ?? { color: T.text2, bg: "transparent" }
          const isBuy = t.transaction_type?.toLowerCase().includes("purchase")
          return [
            <div key={`n${i}`} style={{ fontSize: 12, color: T.text, padding: "8px 10px", borderBottom: `1px solid ${T.border}` }}>{t.politician}</div>,
            <div key={`p${i}`} style={{ fontSize: 11, padding: "8px 10px", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ background: ps.bg, color: ps.color, padding: "1px 6px", borderRadius: 4, fontFamily: T.mono, fontWeight: 600 }}>{t.party}</span>
            </div>,
            <div key={`d${i}`} style={{ fontSize: 11, color: T.text2, padding: "8px 10px", fontFamily: T.mono, borderBottom: `1px solid ${T.border}` }}>{t.trade_date?.slice(0, 10)}</div>,
            <div key={`ty${i}`} style={{ fontSize: 11, padding: "8px 10px", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ color: isBuy ? T.green : T.red, fontWeight: 500 }}>{t.transaction_type}</span>
            </div>,
            <div key={`a${i}`} style={{ fontSize: 11, color: T.text2, padding: "8px 10px", fontFamily: T.mono, borderBottom: `1px solid ${T.border}` }}>{t.amount_range}</div>,
          ]
        })}
      </div>
    </div>
  )
}
