import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T, chgColor, chgDim } from "../theme"
import type { MacroEnvironment, SectorData, GeoEvent, FREDMacroData, FREDIndicator, FREDCrossAsset } from "../types"

interface MacroState {
  environment: MacroEnvironment | null
  sectors: SectorData[]
  geoEvents: GeoEvent[]
  fred: FREDMacroData | null
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

// ── FRED sub-components ───────────────────────────────────────────────────────

function FREDRow({ ind }: { ind: FREDIndicator }) {
  if (!ind || ind.error === "unavailable") return null
  const chgSign = (ind.change_7d ?? 0) >= 0 ? "+" : ""
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "9px 0",
      borderBottom: `1px solid ${T.border}`,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: T.text2, marginBottom: 2 }}>{ind.label}</div>
        <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.3 }}>{ind.signal}</div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 600, color: ind.color }}>
          {ind.current != null ? `${ind.current}${ind.unit}` : "—"}
        </div>
        {ind.change_7d != null && (
          <div style={{ fontSize: 10, fontFamily: T.mono, color: (ind.change_7d ?? 0) >= 0 ? T.green : T.red }}>
            {chgSign}{ind.change_7d.toFixed(3)}
          </div>
        )}
      </div>
      <span style={{
        fontSize: 9, fontWeight: 700, fontFamily: T.mono,
        padding: "2px 7px", borderRadius: 3,
        background: ind.color + "20",
        color: ind.color,
        border: `1px solid ${ind.color}40`,
        letterSpacing: "0.05em",
        flexShrink: 0,
        minWidth: 48,
        textAlign: "center",
      }}>
        {ind.verdict}
      </span>
    </div>
  )
}

function FREDCrossRow({ ca }: { ca: FREDCrossAsset }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "9px 0",
      borderBottom: `1px solid ${T.border}`,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: T.text2, marginBottom: 2 }}>{ca.label}</div>
        <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.3 }}>{ca.signal}</div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 600, color: ca.color }}>
          {ca.current}
        </div>
        {ca.change_7d != null && (
          <div style={{ fontSize: 10, fontFamily: T.mono, color: ca.change_7d >= 0 ? T.green : T.red }}>
            {ca.change_7d >= 0 ? "+" : ""}{ca.change_7d.toFixed(3)} 7d
          </div>
        )}
      </div>
      <span style={{
        fontSize: 9, fontWeight: 700, fontFamily: T.mono,
        padding: "2px 7px", borderRadius: 3,
        background: ca.color + "20", color: ca.color,
        border: `1px solid ${ca.color}40`,
        letterSpacing: "0.05em", flexShrink: 0,
        minWidth: 48, textAlign: "center",
      }}>
        {ca.verdict}
      </span>
    </div>
  )
}

function FREDSection({ fred }: { fred: FREDMacroData }) {
  if (fred.error) {
    if (fred.setup_url) {
      return (
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12,
        }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Credit &amp; Rates Dashboard (FRED)
          </div>
          <div style={{ fontSize: 13, color: T.amber, marginBottom: 6 }}>
            FRED_API_KEY not configured — credit spread and rates data unavailable.
          </div>
          <div style={{ fontSize: 12, color: T.text3 }}>
            Get a free key at{" "}
            <span style={{ color: T.blue, fontFamily: T.mono }}>
              fred.stlouisfed.org/docs/api/api_key.html
            </span>
            {" "}then set <code style={{ fontFamily: T.mono, background: T.surface2, padding: "1px 5px", borderRadius: 3 }}>FRED_API_KEY</code> in your .env
          </div>
        </div>
      )
    }
    return null
  }

  const compositeColor =
    fred.composite_verdict === "BUY"  ? T.green :
    fred.composite_verdict === "SELL" ? T.red :
    fred.composite_verdict === "AVOID"? "#ff2222" : T.amber

  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12,
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Credit &amp; Rates Dashboard (FRED)
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 10, color: T.text3 }}>{fred.composite_summary}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, fontFamily: T.mono,
            padding: "2px 9px", borderRadius: 3,
            background: compositeColor + "20", color: compositeColor,
            border: `1px solid ${compositeColor}40`,
          }}>
            {fred.composite_verdict}
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>

        {/* Credit Spreads */}
        <div>
          <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, paddingBottom: 4, borderBottom: `1px solid ${T.border}` }}>
            Credit Spreads
          </div>
          <FREDRow ind={fred.credit_spreads.hy_spread} />
          <FREDRow ind={fred.credit_spreads.ig_spread} />
        </div>

        {/* Yield Curves */}
        <div>
          <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, paddingBottom: 4, borderBottom: `1px solid ${T.border}` }}>
            Yield Curves
          </div>
          <FREDRow ind={fred.rates.yield_curve_2s10s} />
          <FREDRow ind={fred.rates.yield_curve_3m10y} />
        </div>

        {/* Interest Rates */}
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, paddingBottom: 4, borderBottom: `1px solid ${T.border}` }}>
            Interest Rates
          </div>
          <FREDRow ind={fred.rates.real_yield_10y} />
          <FREDRow ind={fred.rates.breakeven_10y} />
          <FREDRow ind={fred.rates.sofr} />
        </div>

        {/* Liquidity & Cross-Asset */}
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, paddingBottom: 4, borderBottom: `1px solid ${T.border}` }}>
            Liquidity &amp; Cross-Asset
          </div>
          <FREDRow ind={fred.liquidity.m2} />
          {fred.cross_asset.dxy && <FREDCrossRow ca={fred.cross_asset.dxy} />}
          {fred.cross_asset.copper_gold_ratio && <FREDCrossRow ca={fred.cross_asset.copper_gold_ratio} />}
        </div>

      </div>

      <div style={{ fontSize: 9, color: T.text3, marginTop: 12 }}>
        Source: St. Louis Fed FRED API · Updated daily · HY/IG spread = OAS in % (×100 = bps)
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function MacroPage() {
  const [state, setState] = useState<MacroState>({ environment: null, sectors: [], geoEvents: [], fred: null, loading: false })

  const fetchMacro = async () => {
    setState(s => ({ ...s, loading: true }))
    try {
      const res = await api.get("/macro/all")
      setState({
        environment: res.data.environment,
        sectors: res.data.sectors?.sectors || [],
        geoEvents: res.data.geopolitical?.all_events || [],
        fred: res.data.fred ?? null,
        loading: false,
      })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }

  useEffect(() => { fetchMacro() }, [])

  const { environment: env, sectors, geoEvents, fred, loading } = state

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

      {/* FRED Credit & Rates Dashboard */}
      {fred && <FREDSection fred={fred} />}

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
