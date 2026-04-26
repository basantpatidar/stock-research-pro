import { useState, useEffect } from "react"
import { api } from "../services/api"
import type { MacroEnvironment, SectorData, GeoEvent } from "../types"

interface MacroState {
  environment: MacroEnvironment | null
  sectors: SectorData[]
  geoEvents: GeoEvent[]
  loading: boolean
}

const heatColor = (change: number) => {
  if (change >= 5)  return { bg: "#d1fae5", color: "#065f46" }
  if (change >= 1)  return { bg: "#dcfce7", color: "#166534" }
  if (change >= -1) return { bg: "#f3f4f6", color: "#374151" }
  if (change >= -5) return { bg: "#fef3c7", color: "#92400e" }
  if (change >= -10) return { bg: "#fee2e2", color: "#991b1b" }
  return { bg: "#fecaca", color: "#7f1d1d" }
}

const sevColor = (s: string) => {
  if (s === "critical") return { dot: "#dc2626", bg: "#fee2e2" }
  if (s === "high") return { dot: "#d97706", bg: "#fef3c7" }
  return { dot: "#6b7280", bg: "#f3f4f6" }
}

export function MacroPage() {
  const [state, setState] = useState<MacroState>({ environment: null, sectors: [], geoEvents: [], loading: false })

  const fetchMacro = async () => {
    setState(s => ({ ...s, loading: true }))
    try {
      const res = await api.get("/macro/all")
      setState({
        environment: res.data.environment,
        sectors: res.data.sectors?.sectors || [],
        geoEvents: res.data.geopolitical?.all_events || [],
        loading: false,
      })
    } catch (e) {
      setState(s => ({ ...s, loading: false }))
    }
  }

  useEffect(() => { fetchMacro() }, [])

  const { environment: env, sectors, geoEvents, loading } = state

  const envBg = env?.environment?.includes("RISK-OFF") ? "#fee2e2"
    : env?.environment?.includes("RISK-ON") ? "#d1fae5"
    : "#f3f4f6"
  const envColor = env?.environment?.includes("RISK-OFF") ? "#991b1b"
    : env?.environment?.includes("RISK-ON") ? "#065f46"
    : "#374151"

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "1.5rem 1rem" }}>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 500, margin: 0 }}>Macro &amp; geopolitical environment</h2>
        <button onClick={fetchMacro} disabled={loading} style={{ fontSize: 12, color: "#6b7280", background: "none", border: "0.5px solid #d1d5db", borderRadius: 6, padding: "5px 12px", cursor: "pointer" }}>
          {loading ? "Loading..." : "↻ Refresh"}
        </button>
      </div>

      {/* Environment banner */}
      {env && (
        <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <span style={{ background: envBg, color: envColor, fontWeight: 500, fontSize: 13, padding: "4px 12px", borderRadius: 20 }}>
              {env.environment}
            </span>
            <span style={{ fontSize: 12, color: "#6b7280" }}>{env.trading_recommendation}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            {[
              { label: "VIX", data: env.vix },
              { label: "S&P 500", data: env.sp500 },
              { label: "Oil (WTI)", data: env.oil_wti },
              { label: "Gold", data: env.gold },
              { label: "Nasdaq", data: env.nasdaq },
              { label: "10Y Treasury", data: env.treasury_10y },
            ].filter(x => x.data && !("error" in x.data)).map(({ label, data }) => (
              <div key={label} style={{ background: "#f9fafb", borderRadius: 8, padding: "8px 12px" }}>
                <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 15, fontWeight: 500 }}>{(data as any).current}</div>
                <div style={{
                  fontSize: 11, fontWeight: 500,
                  color: (data as any).change_7d_pct >= 0 ? "#16a34a" : "#dc2626",
                }}>
                  {(data as any).change_7d_pct >= 0 ? "+" : ""}{(data as any).change_7d_pct?.toFixed(1)}% (7d)
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sector heatmap */}
      {sectors.length > 0 && (
        <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Sector heatmap — 5 day performance</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
            {sectors.map((s) => {
              const c = heatColor(s.change_5d_pct)
              return (
                <div key={s.sector} style={{ background: c.bg, borderRadius: 8, padding: "8px 10px", textAlign: "center" }}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: c.color, lineHeight: 1.3 }}>{s.sector}</div>
                  <div style={{ fontSize: 14, fontWeight: 500, color: c.color, marginTop: 4 }}>
                    {s.change_5d_pct >= 0 ? "+" : ""}{s.change_5d_pct.toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 8 }}>Green = outperforming · Red = most impacted</div>
        </div>
      )}

      {/* Geopolitical events */}
      {geoEvents.length > 0 && (
        <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Active geopolitical events</div>
          {geoEvents.map((e, i) => {
            const c = sevColor(e.severity)
            return (
              <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < geoEvents.length - 1 ? "0.5px solid #f3f4f6" : "none", alignItems: "flex-start" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: c.dot, flexShrink: 0, marginTop: 4 }} />
                <div style={{ flex: 1 }}>
                  <a href={e.url} target="_blank" rel="noreferrer" style={{ fontSize: 13, fontWeight: 500, color: "#111", textDecoration: "none" }}>
                    {e.title}
                  </a>
                  <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>{e.source} · {e.published}</div>
                  {e.impacted_sectors.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 5 }}>
                      {e.impacted_sectors.map((sec) => (
                        <span key={sec} style={{ fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 3, background: c.bg, color: c.dot }}>{sec}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {!env && !loading && (
        <div style={{ background: "#f9fafb", borderRadius: 12, padding: "2rem", textAlign: "center", color: "#9ca3af", fontSize: 14 }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>🌍</div>
          <div>Click refresh to load macro environment data</div>
        </div>
      )}
    </div>
  )
}
