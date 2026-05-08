import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T } from "../theme"

interface AnalyticsData {
  total_signals: number
  wins: number
  losses: number
  win_rate_pct: number | null
  avg_win_pct: number | null
  avg_loss_pct: number | null
  expected_value_pct: number | null
  expected_value_dollar: number | null
  current_streak: { type: string; count: number } | null
  by_ticker: Record<string, { signals: number; wins: number; losses: number; win_rate_pct: number; avg_pnl_pct: number }>
  by_window: Record<string, { signals: number; wins: number; losses: number; win_rate_pct: number; label: string }>
  recent_alerts: RecentAlert[]
  cumulative_pnl: { date: string; cumulative_pnl: number }[]
  live_signals: number
  backtest_signals: number
  note: string
}

interface RecentAlert {
  id: string
  ticker: string
  entry_time: string
  entry_price: number
  outcome_price: number
  actual_pnl_pct: number
  actual_pnl_dollar: number
  status: string
  resolved_by: string
  session_window: string
  score: number
  source: string
}

function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 6, background: T.surface2, borderRadius: 3, overflow: "hidden" }}>
      <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: color, borderRadius: 3 }} />
    </div>
  )
}

function CumulativeChart({ data }: { data: { date: string; cumulative_pnl: number }[] }) {
  if (!data || data.length < 2) return null
  const values = data.map(d => d.cumulative_pnl)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const W = 300, H = 60
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W
    const y = H - ((d.cumulative_pnl - min) / range) * H
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(" ")
  const lastVal = values[values.length - 1]
  const lineColor = lastVal >= 0 ? T.green : T.red

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
        Cumulative P&L
        <span style={{ marginLeft: 8, color: lineColor, fontFamily: T.mono, fontWeight: 600 }}>
          {lastVal >= 0 ? "+" : ""}${lastVal.toFixed(2)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H, display: "block" }}>
        <polyline points={points} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinejoin="round" />
        <line x1="0" y1={H - ((0 - min) / range) * H} x2={W} y2={H - ((0 - min) / range) * H}
          stroke={T.border} strokeWidth="0.5" strokeDasharray="3,3" />
      </svg>
    </div>
  )
}

export function ScannerPerformanceCard() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [backfilling, setBackfilling] = useState(false)

  const fetchAnalytics = async () => {
    try {
      const res = await api.get("/dip-scanner/analytics")
      setData(res.data)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const triggerBackfill = async () => {
    setBackfilling(true)
    try {
      await api.post("/dip-scanner/backfill", { tiers: [1], days: 60 })
      setTimeout(() => { fetchAnalytics(); setBackfilling(false) }, 3000)
    } catch {
      setBackfilling(false)
    }
  }

  useEffect(() => { fetchAnalytics() }, [])

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Scanner Performance</div>
          <div style={{ fontSize: 11, color: T.text2, marginTop: 2 }}>
            {data ? (
              <>
                {data.backtest_signals > 0 && <span style={{ color: T.text3 }}>Backtest {data.backtest_signals} · </span>}
                {data.live_signals > 0 && <span style={{ color: T.green }}>Live {data.live_signals}</span>}
                {data.live_signals === 0 && data.backtest_signals === 0 && "No data yet"}
              </>
            ) : "Loading…"}
          </div>
        </div>
        {data && data.total_signals === 0 && (
          <button
            onClick={triggerBackfill}
            disabled={backfilling}
            style={{
              fontSize: 11, padding: "6px 12px",
              background: backfilling ? T.surface2 : T.amber,
              color: backfilling ? T.text2 : "#000",
              border: "none", borderRadius: 6, cursor: backfilling ? "not-allowed" : "pointer",
              fontWeight: 600,
            }}
          >
            {backfilling ? "Backfilling…" : "Seed 60-day history"}
          </button>
        )}
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "20px 0", color: T.text3, fontSize: 12 }}>Loading analytics…</div>
      )}

      {!loading && data && data.total_signals === 0 && (
        <div style={{ textAlign: "center", padding: "16px 0" }}>
          <div style={{ fontSize: 13, color: T.text2, marginBottom: 6 }}>No resolved signals yet</div>
          <div style={{ fontSize: 11, color: T.text3, lineHeight: 1.6 }}>
            Click "Seed 60-day history" to backfill historical data immediately,<br />
            or wait for live alerts to accumulate over the next few days.
          </div>
        </div>
      )}

      {!loading && data && data.total_signals > 0 && (
        <>
          {/* Key metrics */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, marginBottom: 14 }}>
            {[
              {
                label: "Win Rate",
                value: data.win_rate_pct !== null ? `${data.win_rate_pct}%` : "—",
                sub: `${data.wins}W / ${data.losses}L`,
                color: data.win_rate_pct !== null && data.win_rate_pct >= 60 ? T.green : T.amber,
              },
              {
                label: "Avg EV / Trade",
                value: data.expected_value_dollar !== null ? `${data.expected_value_dollar >= 0 ? "+" : ""}$${data.expected_value_dollar.toFixed(2)}` : "—",
                sub: "on $1,000 capital",
                color: data.expected_value_dollar !== null && data.expected_value_dollar >= 0 ? T.green : T.red,
              },
              {
                label: "Streak",
                value: data.current_streak ? `${data.current_streak.count}×` : "—",
                sub: data.current_streak ? data.current_streak.type.toUpperCase() : "",
                color: data.current_streak?.type === "win" ? T.green : T.red,
              },
            ].map(({ label, value, sub, color }) => (
              <div key={label} style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: T.mono, color }}>{value}</div>
                <div style={{ fontSize: 10, color: T.text3, marginTop: 3 }}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Cumulative P&L chart */}
          {data.cumulative_pnl.length > 1 && <CumulativeChart data={data.cumulative_pnl} />}

          {/* By ETF */}
          {Object.keys(data.by_ticker).length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>By ETF</div>
              {Object.entries(data.by_ticker)
                .sort(([, a], [, b]) => b.win_rate_pct - a.win_rate_pct)
                .map(([ticker, d]) => (
                  <div key={ticker} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <span style={{ width: 38, fontSize: 12, fontFamily: T.mono, fontWeight: 600, color: T.blue }}>{ticker}</span>
                    <MiniBar pct={d.win_rate_pct} color={d.win_rate_pct >= 60 ? T.green : T.amber} />
                    <span style={{ width: 40, fontSize: 12, fontFamily: T.mono, textAlign: "right", color: d.win_rate_pct >= 60 ? T.green : T.amber }}>
                      {d.win_rate_pct}%
                    </span>
                    <span style={{ width: 32, fontSize: 11, color: T.text3, textAlign: "right" }}>{d.signals}</span>
                  </div>
                ))}
            </div>
          )}

          {/* By session window */}
          {Object.keys(data.by_window).length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>By Session</div>
              {Object.entries(data.by_window)
                .sort(([, a], [, b]) => b.win_rate_pct - a.win_rate_pct)
                .map(([key, d]) => (
                  <div key={key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <span style={{ width: 100, fontSize: 11, color: T.text2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {d.label || key}
                    </span>
                    <MiniBar pct={d.win_rate_pct} color={d.win_rate_pct >= 65 ? T.green : d.win_rate_pct >= 50 ? T.amber : T.red} />
                    <span style={{ width: 40, fontSize: 12, fontFamily: T.mono, textAlign: "right", color: d.win_rate_pct >= 65 ? T.green : T.amber }}>
                      {d.win_rate_pct}%
                    </span>
                  </div>
                ))}
            </div>
          )}

          {/* Recent alerts */}
          {data.recent_alerts.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Recent</div>
              {data.recent_alerts.slice(0, 8).map(alert => {
                const isWin = alert.status === "win"
                const dt = alert.entry_time ? new Date(alert.entry_time) : null
                const dateStr = dt ? `${dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ${dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}` : "—"
                return (
                  <div key={alert.id} style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
                    borderBottom: `1px solid ${T.border}`, fontSize: 12,
                  }}>
                    <span style={{ color: isWin ? T.green : T.red, fontSize: 12, width: 12 }}>{isWin ? "✓" : "✗"}</span>
                    <span style={{ fontFamily: T.mono, fontWeight: 600, color: T.blue, width: 34 }}>{alert.ticker}</span>
                    <span style={{ color: T.text3, fontSize: 11, flex: 1 }}>{dateStr}</span>
                    <span style={{ fontFamily: T.mono, color: isWin ? T.green : T.red, fontWeight: 600 }}>
                      {isWin ? "+" : ""}{alert.actual_pnl_dollar?.toFixed(2) ?? "—"}
                    </span>
                    <span style={{
                      fontSize: 10, padding: "1px 5px",
                      background: alert.source === "live" ? `${T.green}22` : T.surface2,
                      color: alert.source === "live" ? T.green : T.text3,
                      border: `1px solid ${alert.source === "live" ? T.green + "44" : T.border}`,
                      borderRadius: 4,
                    }}>
                      {alert.source?.toUpperCase()}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {data.total_signals < 30 && (
            <div style={{ marginTop: 10, fontSize: 11, color: T.text3, fontStyle: "italic" }}>
              Win rate becomes reliable after 30+ signals ({data.total_signals} so far)
            </div>
          )}
        </>
      )}
    </div>
  )
}
