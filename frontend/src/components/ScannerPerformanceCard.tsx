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
  by_signal_type: Record<string, Record<string, { ticker: string; session: string; signals: number; wins: number; losses: number; win_rate_pct: number | null; ev_pct: number | null }>>
  by_signal_type_summary: Record<string, { signals: number; wins: number; losses: number; win_rate_pct: number | null; ev_pct: number | null; ev_dollar: number | null }>
  by_score_band: Record<string, { signals: number; wins: number; losses: number; win_rate_pct: number | null; ev_dollar: number | null }>
  recent_alerts: RecentAlert[]
  cumulative_pnl: { date: string; cumulative_pnl: number }[]
  live_signals: number
  backtest_signals: number
  forward_accuracy_pct: number | null
  forward_accuracy_n: number
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

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  dip_buy: "Dip Buy",
  orb_breakout: "ORB Breakout",
  vwap_reclaim: "VWAP Reclaim",
  failed_breakdown: "Failed Breakdown",
}

function evColor(ev: number | null): string {
  if (ev == null) return T.surface2
  if (ev > 0.3) return "rgba(34,197,94,0.25)"
  if (ev > 0) return "rgba(34,197,94,0.12)"
  if (ev > -0.3) return "rgba(239,68,68,0.10)"
  return "rgba(239,68,68,0.22)"
}

function SignalHeatmap({ bySignalType }: { bySignalType: AnalyticsData["by_signal_type"] }) {
  const signalTypes = Object.keys(bySignalType)
  if (signalTypes.length === 0) return null
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: T.text2, marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
        Signal Type Heatmap — EV by Cell (#28)
      </div>
      {signalTypes.map(st => {
        const cells = Object.values(bySignalType[st])
        if (cells.length === 0) return null
        return (
          <div key={st} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: T.text2, marginBottom: 5, fontWeight: 600 }}>
              {SIGNAL_TYPE_LABELS[st] ?? st}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {cells.map(cell => (
                <div key={`${cell.ticker}:${cell.session}`} style={{
                  background: evColor(cell.ev_pct),
                  border: `1px solid ${T.border}`,
                  borderRadius: 5, padding: "5px 8px", minWidth: 80,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: T.text }}>{cell.ticker}</div>
                  <div style={{ fontSize: 9, color: T.text3 }}>{cell.session.replace("_", " ")}</div>
                  <div style={{ fontSize: 10, fontFamily: T.mono, color: cell.ev_pct != null && cell.ev_pct > 0 ? "#4ade80" : "#f87171", marginTop: 2 }}>
                    {cell.ev_pct != null ? `EV ${cell.ev_pct > 0 ? "+" : ""}${cell.ev_pct.toFixed(2)}%` : "—"}
                  </div>
                  <div style={{ fontSize: 9, color: T.text3 }}>n={cell.signals}</div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ScannerPerformanceCard() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [backfilling, setBackfilling] = useState(false)

  const fetchAnalytics = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get("/dip-scanner/analytics")
      setData(res.data)
    } catch (e: any) {
      setData(null)
      setError(e?.response?.status === 500
        ? "DB error — run migrations (make migrate)"
        : "Could not reach backend")
    } finally {
      setLoading(false)
    }
  }

  const triggerBackfill = async () => {
    setBackfilling(true)
    try {
      await api.post("/dip-scanner/backfill", { tiers: [1, 2], days: 60 })
      // Poll until signal count grows (backfill runs in background, takes 2-3 min)
      const poll = setInterval(async () => {
        try {
          const res = await api.get("/dip-scanner/analytics")
          if (res.data.total_signals > 0) {
            setData(res.data)
            setBackfilling(false)
            clearInterval(poll)
          }
        } catch { /* keep polling */ }
      }, 8000)
      // Hard stop after 5 min
      setTimeout(() => { clearInterval(poll); setBackfilling(false); fetchAnalytics() }, 300_000)
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
            {loading ? "Loading…" : error ? (
              <span style={{ color: T.red }}>{error}</span>
            ) : data ? (
              <>
                {data.backtest_signals > 0 && <span style={{ color: T.text3 }}>Backtest {data.backtest_signals} · </span>}
                {data.live_signals > 0 && <span style={{ color: T.green }}>Live {data.live_signals}</span>}
                {data.live_signals === 0 && data.backtest_signals === 0 && "No data yet"}
              </>
            ) : "No data"}
          </div>
        </div>
        {data && (
          <button
            onClick={triggerBackfill}
            disabled={backfilling}
            title="Replay 60 days of historical bars for all 4 signal types across all ETFs"
            style={{
              fontSize: 11, padding: "6px 12px",
              background: backfilling ? T.surface2 : T.amber,
              color: backfilling ? T.text2 : "#000",
              border: "none", borderRadius: 6, cursor: backfilling ? "not-allowed" : "pointer",
              fontWeight: 600,
            }}
          >
            {backfilling ? "Backfilling…" : data.total_signals === 0 ? "Seed 60-day history" : "Re-seed history"}
          </button>
        )}
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "20px 0", color: T.text3, fontSize: 12 }}>Loading analytics…</div>
      )}

      {!loading && error && (
        <div style={{ textAlign: "center", padding: "16px 0" }}>
          <div style={{ fontSize: 12, color: T.red, marginBottom: 8 }}>{error}</div>
          <button
            onClick={fetchAnalytics}
            style={{
              fontSize: 11, padding: "5px 14px",
              background: T.surface2, color: T.text2,
              border: `1px solid ${T.border}`, borderRadius: 6, cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && data && data.total_signals === 0 && (
        <div style={{ textAlign: "center", padding: "16px 0" }}>
          <div style={{ fontSize: 13, color: T.text2, marginBottom: 6 }}>No resolved signals yet</div>
          <div style={{ fontSize: 11, color: T.text3, lineHeight: 1.6 }}>
            Click "Seed 60-day history" to backfill historical data immediately,<br />
            or wait for live alerts to accumulate over the next few days.
          </div>
        </div>
      )}

      {!loading && !error && data && data.total_signals > 0 && (
        <>
          {/* Key metrics */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8, marginBottom: 14 }}>
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
              {
                label: "5-Min Accuracy",
                value: data.forward_accuracy_pct !== null ? `${data.forward_accuracy_pct}%` : "—",
                sub: data.forward_accuracy_n > 0 ? `n=${data.forward_accuracy_n} signals` : "needs live data",
                color: data.forward_accuracy_pct !== null && data.forward_accuracy_pct >= 60 ? T.green : T.text3,
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
                    <span style={{ width: 40, fontSize: 12, fontFamily: T.mono, textAlign: "right", color: d.win_rate_pct >= 65 ? T.green : d.win_rate_pct >= 50 ? T.amber : T.red }}>
                      {d.win_rate_pct}%
                    </span>
                    <span style={{ width: 32, fontSize: 11, color: T.text3, textAlign: "right" }}>{d.signals}</span>
                  </div>
                ))}
            </div>
          )}

          {/* Signal type summary — win rate + EV per type */}
          {data.by_signal_type_summary && Object.keys(data.by_signal_type_summary).length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>By Signal Type</div>
              {Object.entries(data.by_signal_type_summary)
                .sort(([, a], [, b]) => (b.win_rate_pct ?? 0) - (a.win_rate_pct ?? 0))
                .map(([type, d]) => {
                  const wr = d.win_rate_pct ?? 0
                  const ev = d.ev_dollar
                  const color = wr >= 60 ? T.green : wr >= 50 ? T.amber : T.red
                  return (
                    <div key={type} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 110, fontSize: 11, color: T.text2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {SIGNAL_TYPE_LABELS[type] ?? type}
                      </span>
                      <MiniBar pct={wr} color={color} />
                      <span style={{ width: 40, fontSize: 12, fontFamily: T.mono, textAlign: "right", color }}>{wr}%</span>
                      <span style={{ width: 52, fontSize: 11, fontFamily: T.mono, textAlign: "right", color: ev != null && ev >= 0 ? T.green : T.red }}>
                        {ev != null ? `${ev >= 0 ? "+" : ""}$${ev.toFixed(2)}` : "—"}
                      </span>
                      <span style={{ width: 28, fontSize: 11, color: T.text3, textAlign: "right" }}>{d.signals}</span>
                    </div>
                  )
                })}
            </div>
          )}

          {/* Score band — does higher score = higher win rate? */}
          {data.by_score_band && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>By Score Band</div>
              <div style={{ display: "flex", gap: 6 }}>
                {Object.entries(data.by_score_band).map(([band, d]) => {
                  const wr = d.win_rate_pct
                  const color = wr != null && wr >= 60 ? T.green : wr != null && wr >= 50 ? T.amber : T.red
                  return (
                    <div key={band} style={{
                      flex: 1, background: T.surface2, border: `1px solid ${T.border}`,
                      borderRadius: 8, padding: "8px 10px", textAlign: "center",
                    }}>
                      <div style={{ fontSize: 10, color: T.text3, marginBottom: 4 }}>Score {band}</div>
                      <div style={{ fontSize: 16, fontWeight: 700, fontFamily: T.mono, color }}>
                        {wr != null ? `${wr}%` : "—"}
                      </div>
                      <div style={{ fontSize: 10, color: T.text3, marginTop: 2 }}>n={d.signals}</div>
                      <div style={{ fontSize: 10, fontFamily: T.mono, color: d.ev_dollar != null && d.ev_dollar >= 0 ? T.green : T.red, marginTop: 1 }}>
                        {d.ev_dollar != null ? `${d.ev_dollar >= 0 ? "+" : ""}$${d.ev_dollar.toFixed(2)}` : "—"}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Signal type heatmap — EV by cell (#28) */}
          {data.by_signal_type && Object.keys(data.by_signal_type).length > 0 && (
            <SignalHeatmap bySignalType={data.by_signal_type} />
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
