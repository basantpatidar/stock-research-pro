import { useEffect, useState } from "react"
import { api } from "../services/api"
import { T } from "../theme"

export function McfScannerCard() {
  const [state, setState] = useState<any>(null)
  const [analytics, setAnalytics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [stateRes, analyticsRes] = await Promise.all([
        api.get("/mcf-scanner/state"),
        api.get("/mcf-scanner/analytics"),
      ])
      setState(stateRes.data)
      setAnalytics(analyticsRes.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setLoading(true)
    try {
      await api.post("/mcf-scanner/force-run")
      await fetchData()
    } catch (err) {
      console.error(err)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 60000) // Poll every minute
    return () => clearInterval(interval)
  }, [])

  if (!state || !analytics) {
    return (
      <div style={{ background: T.surface, padding: 20, borderRadius: 12, border: `1px solid ${T.border}` }}>
        <div style={{ color: T.text2, fontSize: 14 }}>{loading ? "Loading MCF Scanner..." : "No data"}</div>
      </div>
    )
  }

  const { weather, tide, timestamp } = state

  const weatherColor = weather.status === "pass" ? T.green : weather.status === "fail" ? T.red : T.amber
  const tideColor = tide?.status === "pass" ? T.green : tide?.status === "fail" ? T.red : T.amber

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Market Context Funnel</div>
          <div style={{ fontSize: 12, color: T.text3, marginTop: 4 }}>Last scan: {timestamp ? new Date(timestamp).toLocaleTimeString() : "Never"}</div>
        </div>
        <button onClick={handleRefresh} disabled={loading} style={{ background: T.surface2, border: `1px solid ${T.border}`, color: T.text2, padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
          {loading ? "Scanning..." : "Force Scan & Refresh"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 15, marginBottom: 20 }}>
        {/* Layer 1 */}
        <div style={{ border: `1px solid ${weatherColor}40`, background: `${weatherColor}10`, padding: 15, borderRadius: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: weatherColor, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Layer 1: Weather</div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
            <span style={{ fontSize: 13, color: T.text2 }}>SPY Trend</span>
            <span style={{ fontSize: 13, color: T.text, fontWeight: 500, textTransform: "capitalize" }}>{weather.spy_trend}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, color: T.text2 }}>VIX</span>
            <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{weather.vix}</span>
          </div>
        </div>

        {/* Layer 2 */}
        <div style={{ border: `1px solid ${tideColor}40`, background: `${tideColor}10`, padding: 15, borderRadius: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: tideColor, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Layer 2: Tide</div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
            <span style={{ fontSize: 13, color: T.text2 }}>Correlated Selling</span>
            <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{tide?.correlated_selling ? "Yes" : "No"} ({tide?.down_count}/4)</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, color: T.text2 }}>Momentum Fading</span>
            <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{tide?.momentum_fading ? "Yes" : "No"} ({tide?.fading_count}/4)</span>
          </div>
        </div>
      </div>

      {/* Analytics Summary */}
      <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 15, marginTop: 15 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 10 }}>Performance (Target 1%)</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
          <div>
            <div style={{ fontSize: 11, color: T.text3 }}>Win Rate</div>
            <div style={{ fontSize: 16, fontFamily: T.mono, fontWeight: 600, color: analytics.win_rate_pct >= 50 ? T.green : T.red }}>
              {analytics.win_rate_pct !== null ? `${analytics.win_rate_pct}%` : "--"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: T.text3 }}>Trades (W/L)</div>
            <div style={{ fontSize: 16, fontFamily: T.mono, fontWeight: 600, color: T.text }}>
              {analytics.wins} / {analytics.losses}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: T.text3 }}>Expected Value</div>
            <div style={{ fontSize: 16, fontFamily: T.mono, fontWeight: 600, color: analytics.expected_value_dollar > 0 ? T.green : T.red }}>
              {analytics.expected_value_dollar !== null ? `$${analytics.expected_value_dollar}` : "--"}
            </div>
          </div>
        </div>
      </div>
      
      {/* Recent Alerts */}
      <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 10 }}>Recent Setups</div>
          {analytics.recent_alerts?.length === 0 ? (
            <div style={{ fontSize: 12, color: T.text3 }}>No recent MCF alerts.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {analytics.recent_alerts?.slice(0, 5).map((a: any, i: number) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: T.surface2, borderRadius: 6, border: `1px solid ${T.border}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 600, color: T.blue }}>{a.ticker}</span>
                    <span style={{ fontSize: 11, color: T.text3 }}>{new Date(a.entry_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: a.status === "win" ? T.green : a.status === "loss" ? T.red : T.amber, fontWeight: 600, textTransform: "uppercase" }}>
                      {a.status}
                    </div>
                    {a.actual_pnl_pct && (
                      <div style={{ fontSize: 11, fontFamily: T.mono, color: T.text2 }}>
                        {a.actual_pnl_pct > 0 ? "+" : ""}{a.actual_pnl_pct}%
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}
