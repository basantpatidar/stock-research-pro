import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T, chgColor, chgDim } from "../theme"
import type { MacroEnvironment, SectorData, GeoEvent } from "../types"

interface MacroState {
  environment: MacroEnvironment | null
  sectors: SectorData[]
  geoEvents: GeoEvent[]
  loading: boolean
}

const heatStyle = (pct: number) => {
  if (pct >= 5)   return { bg: "rgba(16,185,129,0.25)", text: "#34d399", border: "#10b981" }
  if (pct >= 2)   return { bg: "rgba(16,185,129,0.14)", text: T.green,   border: T.green }
  if (pct >= -2)  return { bg: T.surface2,               text: T.text2,   border: T.border }
  if (pct >= -5)  return { bg: "rgba(245,158,11,0.12)", text: T.amber,   border: T.amber }
  if (pct >= -10) return { bg: "rgba(239,68,68,0.14)",  text: T.red,     border: T.red }
  return                 { bg: "rgba(239,68,68,0.25)",  text: "#fca5a5", border: T.red }
}

const sevStyle = (s: string) => {
  if (s === "critical") return { dot: T.red,   badge: T.redDim }
  if (s === "high")     return { dot: T.amber, badge: T.amberDim }
  return                       { dot: T.text3, badge: T.surface2 }
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
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }

  useEffect(() => { fetchMacro() }, [])

  const { environment: env, sectors, geoEvents, loading } = state

  const isRiskOff = env?.environment?.includes("RISK-OFF")
  const isRiskOn  = env?.environment?.includes("RISK-ON")
  const envBannerBg    = isRiskOff ? T.redDim   : isRiskOn ? T.greenDim : T.surface2
  const envBannerBord  = isRiskOff ? T.red       : isRiskOn ? T.green    : T.borderBright
  const envBannerColor = isRiskOff ? T.red       : isRiskOn ? T.green    : T.text2

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Macro Environment</div>
          <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>Global indicators, sector rotation &amp; geopolitical events</div>
        </div>
        <button
          onClick={fetchMacro}
          disabled={loading}
          style={{
            fontSize: 12, color: T.text2, background: T.surface2,
            border: `1px solid ${T.border}`, borderRadius: 7,
            padding: "6px 14px", cursor: loading ? "not-allowed" : "pointer",
            transition: "all 0.12s ease",
          }}
        >
          {loading ? "Loading…" : "↻ Refresh"}
        </button>
      </div>

      {/* Environment risk banner */}
      {env && (
        <div style={{
          background: envBannerBg, border: `1px solid ${envBannerBord}`,
          borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
            <span style={{
              background: envBannerBg, color: envBannerColor, fontWeight: 700,
              fontSize: 12, padding: "4px 12px", borderRadius: 20,
              border: `1px solid ${envBannerBord}`, letterSpacing: "0.06em",
              fontFamily: T.mono,
            }}>
              {env.environment}
            </span>
            <span style={{ fontSize: 13, color: T.text2 }}>{env.trading_recommendation}</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              { label: "VIX",         data: env.vix },
              { label: "S&P 500",     data: env.sp500 },
              { label: "Oil (WTI)",   data: env.oil_wti },
              { label: "Gold",        data: env.gold },
              { label: "Nasdaq",      data: env.nasdaq },
              { label: "10Y Treasury",data: env.treasury_10y },
            ].filter(x => x.data && !("error" in x.data)).map(({ label, data }) => {
              const d = data as any
              const chg = d.change_7d_pct
              return (
                <div key={label} style={{
                  background: T.surface, border: `1px solid ${T.border}`,
                  borderRadius: 8, padding: "10px 13px",
                }}>
                  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 17, fontWeight: 600, fontFamily: T.mono, color: T.text, marginBottom: 3 }}>
                    {d.current}
                  </div>
                  <div style={{
                    fontSize: 11, fontFamily: T.mono, fontWeight: 500,
                    color: chg >= 0 ? T.green : T.red,
                  }}>
                    {chg >= 0 ? "▲ +" : "▼ "}{chg?.toFixed(2)}% <span style={{ color: T.text3 }}>(7d)</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Sector heatmap */}
      {sectors.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
            Sector Heatmap — 5 Day Performance
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
            {sectors.map((s) => {
              const hs = heatStyle(s.change_5d_pct)
              return (
                <div key={s.sector} style={{
                  background: hs.bg, border: `1px solid ${hs.border}`,
                  borderRadius: 8, padding: "10px 10px", textAlign: "center",
                  transition: "transform 0.12s ease",
                  cursor: "default",
                }}>
                  <div style={{ fontSize: 11, fontWeight: 500, color: hs.text, lineHeight: 1.3, marginBottom: 5 }}>
                    {s.sector}
                  </div>
                  <div style={{
                    fontSize: 15, fontWeight: 700, fontFamily: T.mono, color: hs.text,
                  }}>
                    {s.change_5d_pct >= 0 ? "+" : ""}{s.change_5d_pct.toFixed(2)}%
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{ fontSize: 11, color: T.text3, marginTop: 10, fontFamily: T.mono }}>
            Green = outperforming · Red = underperforming · Based on 5-day ETF returns
          </div>
        </div>
      )}

      {/* Geopolitical events */}
      {geoEvents.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
            Active Geopolitical Events
          </div>
          {geoEvents.map((evt, i) => {
            const sv = sevStyle(evt.severity)
            return (
              <div key={i} style={{
                display: "flex", gap: 12,
                padding: "10px 0",
                borderBottom: i < geoEvents.length - 1 ? `1px solid ${T.border}` : "none",
                alignItems: "flex-start",
              }}>
                <div style={{ position: "relative", marginTop: 4, flexShrink: 0 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: sv.dot }} />
                  {evt.severity === "critical" && (
                    <div style={{
                      width: 8, height: 8, borderRadius: "50%", background: sv.dot,
                      position: "absolute", top: 0, left: 0,
                      animation: "pulse-ring 1.5s ease-out infinite",
                    }} />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <a
                    href={evt.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 13, fontWeight: 500, color: T.text,
                      textDecoration: "none", lineHeight: 1.4, display: "block", marginBottom: 4,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = T.blue)}
                    onMouseLeave={e => (e.currentTarget.style.color = T.text)}
                  >
                    {evt.title}
                  </a>
                  <div style={{ fontSize: 11, color: T.text3, marginBottom: evt.impacted_sectors?.length ? 6 : 0 }}>
                    {evt.source} · {evt.published}
                  </div>
                  {evt.impacted_sectors?.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {evt.impacted_sectors.map((sec: string) => (
                        <span key={sec} style={{
                          fontSize: 10, fontWeight: 500, padding: "2px 7px", borderRadius: 4,
                          background: sv.badge, color: sv.dot, border: `1px solid ${sv.dot}`,
                        }}>
                          {sec}
                        </span>
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
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 14, padding: "3rem 2rem", textAlign: "center",
        }}>
          <div style={{ fontSize: 28, color: T.text3, fontFamily: T.mono, marginBottom: 10 }}>🌐</div>
          <div style={{ color: T.text2, fontSize: 14 }}>Click refresh to load macro environment data</div>
        </div>
      )}
    </div>
  )
}
