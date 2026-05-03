import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T, chgColor } from "../theme"

interface Mover {
  ticker: string
  company: string
  price: number
  change_7d_pct: number
  market_cap_b: number
  sector: string
}

interface DashboardState {
  environment: any
  sectors: any[]
  fearGreed: any
  calendar: any
  breadth: any
  movers: Mover[]
  loading: boolean
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 15px" }}>
      <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600, fontFamily: T.mono, color: color || T.text }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: T.text3, marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

function MoverRow({ m }: { m: Mover }) {
  const c = m.change_7d_pct >= 0 ? T.green : T.red
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: `1px solid ${T.border}` }}>
      <div style={{ width: 54, fontFamily: T.mono, fontWeight: 600, fontSize: 13, color: T.blue, flexShrink: 0 }}>{m.ticker}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.company}</div>
        <div style={{ fontSize: 10, color: T.text3 }}>{m.sector}</div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: T.text }}>${m.price.toFixed(2)}</div>
        <div style={{ fontSize: 11, fontFamily: T.mono, color: c, fontWeight: 600 }}>
          {m.change_7d_pct >= 0 ? "+" : ""}{m.change_7d_pct.toFixed(1)}%
        </div>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const [state, setState] = useState<DashboardState>({
    environment: null, sectors: [], fearGreed: null,
    calendar: null, breadth: null, movers: [], loading: false,
  })

  const fetchAll = async () => {
    setState(s => ({ ...s, loading: true }))
    try {
      const [macroRes, screenerRes] = await Promise.all([
        api.get("/macro/all"),
        api.post("/screener/run", {
          min_market_cap_b: 5,
          min_volume: 1_000_000,
          min_price_drop_pct: -100,
          sector: "all",
          max_pe: 1000,
        }),
      ])
      const movers: Mover[] = (screenerRes.data.results || [])
        .sort((a: Mover, b: Mover) => Math.abs(b.change_7d_pct) - Math.abs(a.change_7d_pct))
        .slice(0, 15)
      setState({
        environment: macroRes.data.environment,
        sectors: macroRes.data.sectors?.sectors || [],
        fearGreed: macroRes.data.fear_greed ?? null,
        calendar: macroRes.data.calendar ?? null,
        breadth: macroRes.data.breadth ?? null,
        movers,
        loading: false,
      })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }

  useEffect(() => { fetchAll() }, [])

  const { environment: env, sectors, fearGreed, calendar, breadth, movers, loading } = state

  const gainers = movers.filter(m => m.change_7d_pct > 0).slice(0, 7)
  const losers  = movers.filter(m => m.change_7d_pct < 0).slice(0, 7)

  const fgColor = fearGreed
    ? fearGreed.color === "green" ? T.green
    : fearGreed.color === "red"   ? T.red
    : fearGreed.color === "amber" ? T.amber : T.text2
    : T.text2

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "1.5rem 1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Market Dashboard</div>
          <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>Market pulse · Top movers · Upcoming catalysts</div>
        </div>
        <button
          onClick={fetchAll} disabled={loading}
          style={{ fontSize: 12, color: T.text2, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: "6px 14px", cursor: loading ? "not-allowed" : "pointer" }}
        >
          {loading ? "Loading…" : "↻ Refresh"}
        </button>
      </div>

      {/* Market pulse row */}
      {env && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>Market Pulse</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px,1fr))", gap: 8 }}>
            {[
              { label: "S&P 500",     data: env.sp500,       key: "sp500" },
              { label: "Nasdaq",      data: env.nasdaq,      key: "nasdaq" },
              { label: "VIX",         data: env.vix,         key: "vix" },
              { label: "Gold",        data: env.gold,        key: "gold" },
              { label: "Oil (WTI)",   data: env.oil_wti,     key: "oil_wti" },
              { label: "10Y Yield",   data: env.treasury_10y,key: "treasury_10y" },
            ].filter(x => x.data && !(x.data as any).error).map(({ label, data }) => {
              const d = data as any
              const chg = d.change_7d_pct ?? 0
              return (
                <StatCard
                  key={label}
                  label={label}
                  value={String(d.current)}
                  sub={`${chg >= 0 ? "+" : ""}${chg.toFixed(2)}% (7d)`}
                  color={chg >= 0 ? T.green : T.red}
                />
              )
            })}
            {fearGreed && (
              <StatCard label="Fear & Greed" value={String(fearGreed.value)} sub={fearGreed.classification} color={fgColor} />
            )}
            {breadth && !breadth.error && (
              <StatCard
                label="Breadth 50d"
                value={`${breadth.pct_above_50d}%`}
                sub={breadth.verdict}
                color={breadth.pct_above_50d >= 60 ? T.green : breadth.pct_above_50d >= 40 ? T.amber : T.red}
              />
            )}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
        {/* Top Gainers */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.green, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            ▲ Top Gainers (7d)
          </div>
          {gainers.length === 0 ? (
            <div style={{ fontSize: 12, color: T.text3 }}>No data</div>
          ) : (
            gainers.map(m => <MoverRow key={m.ticker} m={m} />)
          )}
        </div>

        {/* Top Losers */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.red, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            ▼ Top Losers (7d)
          </div>
          {losers.length === 0 ? (
            <div style={{ fontSize: 12, color: T.text3 }}>No data</div>
          ) : (
            losers.map(m => <MoverRow key={m.ticker} m={m} />)
          )}
        </div>
      </div>

      {/* Sector heatmap */}
      {sectors.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Sector Rotation — 5d
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
            {sectors.map((s: any) => {
              const pct = s.change_5d_pct ?? 0
              const col = pct >= 2 ? T.green : pct >= 0 ? "#4ade80" : pct >= -2 ? T.amber : T.red
              return (
                <div key={s.sector} style={{ background: `${col}14`, border: `1px solid ${col}40`, borderRadius: 7, padding: "8px 10px", textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: col, fontWeight: 500, marginBottom: 3 }}>{s.sector}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, fontFamily: T.mono, color: col }}>
                    {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Upcoming economic events */}
      {calendar?.events?.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Upcoming Catalysts
          </div>
          {calendar.events.slice(0, 6).map((evt: any, i: number) => {
            const ic = evt.impact === "high" ? T.red : T.amber
            const dayLabel = evt.days_until === 0 ? "TODAY" : evt.days_until === 1 ? "TOMORROW" : `${evt.days_until}d`
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0", borderBottom: i < 5 ? `1px solid ${T.border}` : "none" }}>
                <span style={{ fontSize: 10, fontFamily: T.mono, color: evt.days_until <= 1 ? T.amber : T.text3, width: 70, flexShrink: 0 }}>{dayLabel}</span>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: ic, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: T.text, flex: 1 }}>{evt.name}</span>
                <span style={{ fontSize: 9, fontWeight: 700, padding: "1px 7px", borderRadius: 3, background: `${ic}20`, color: ic, border: `1px solid ${ic}40`, fontFamily: T.mono }}>
                  {evt.impact.toUpperCase()}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
