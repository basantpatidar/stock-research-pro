import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T } from "../theme"
import { DipScannerCard } from "../components/DipScannerCard"
import { ScannerPerformanceCard } from "../components/ScannerPerformanceCard"

type Period = "1D" | "1W" | "1M" | "3M"

const PERIOD_FIELD: Record<Period, string> = {
  "1D": "change_1d_pct",
  "1W": "change_7d_pct",
  "1M": "change_1m_pct",
  "3M": "change_3m_pct",
}

const PERIOD_LABEL: Record<Period, string> = {
  "1D": "1 Day",
  "1W": "1 Week",
  "1M": "1 Month",
  "3M": "3 Months",
}

interface Mover {
  ticker: string
  company: string
  price: number
  change_1d_pct: number
  change_7d_pct: number
  change_1m_pct: number
  change_3m_pct: number
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

function PeriodToggle({ period, onChange }: { period: Period; onChange: (p: Period) => void }) {
  return (
    <div style={{ display: "flex", gap: 2, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: 3 }}>
      {(["1D", "1W", "1M", "3M"] as Period[]).map(p => (
        <button
          key={p}
          onClick={() => onChange(p)}
          style={{
            fontSize: 12, fontWeight: period === p ? 600 : 400,
            color: period === p ? T.text : T.text2,
            background: period === p ? T.surface : "transparent",
            border: period === p ? `1px solid ${T.borderBright}` : "1px solid transparent",
            borderRadius: 5, padding: "4px 12px", cursor: "pointer",
            transition: "all 0.12s ease",
          }}
        >
          {p}
        </button>
      ))}
    </div>
  )
}

function MoverRow({ m, field, periodLabel }: { m: Mover; field: string; periodLabel: string }) {
  const val: number = (m as any)[field] ?? 0
  const c = val >= 0 ? T.green : T.red
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
          {val >= 0 ? "+" : ""}{val.toFixed(1)}% <span style={{ color: T.text3, fontWeight: 400 }}>({periodLabel})</span>
        </div>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const [period, setPeriod] = useState<Period>("1W")
  const [state, setState] = useState<DashboardState>({
    environment: null, sectors: [], fearGreed: null,
    calendar: null, breadth: null, movers: [], loading: false,
  })

  const field = PERIOD_FIELD[period]
  const periodLabel = PERIOD_LABEL[period]

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
      setState({
        environment: macroRes.data.environment,
        sectors: macroRes.data.sectors?.sectors || [],
        fearGreed: macroRes.data.fear_greed ?? null,
        calendar: macroRes.data.calendar ?? null,
        breadth: macroRes.data.breadth ?? null,
        movers: screenerRes.data.results || [],
        loading: false,
      })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }

  useEffect(() => { fetchAll() }, [])

  const { environment: env, sectors, fearGreed, calendar, breadth, movers, loading } = state

  const sorted = [...movers].sort((a, b) => Math.abs((b as any)[field] ?? 0) - Math.abs((a as any)[field] ?? 0))
  const gainers = sorted.filter(m => ((m as any)[field] ?? 0) > 0).slice(0, 7)
  const losers  = sorted.filter(m => ((m as any)[field] ?? 0) < 0).slice(0, 7)

  const fgColor = fearGreed
    ? fearGreed.color === "green" ? T.green
    : fearGreed.color === "red"   ? T.red
    : fearGreed.color === "amber" ? T.amber : T.text2
    : T.text2

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "1.5rem 1.25rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Market Dashboard</div>
          <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>Market pulse · Top movers · Upcoming catalysts</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <PeriodToggle period={period} onChange={setPeriod} />
          <button
            onClick={fetchAll} disabled={loading}
            style={{ fontSize: 12, color: T.text2, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: "6px 14px", cursor: loading ? "not-allowed" : "pointer" }}
          >
            {loading ? "Loading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Market pulse */}
      {env && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>
            Market Pulse <span style={{ color: T.text3, fontWeight: 400 }}>· {periodLabel}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px,1fr))", gap: 8 }}>
            {[
              { label: "S&P 500",   data: env.sp500 },
              { label: "Nasdaq",    data: env.nasdaq },
              { label: "VIX",       data: env.vix },
              { label: "Gold",      data: env.gold },
              { label: "Oil (WTI)", data: env.oil_wti },
              { label: "10Y Yield", data: env.treasury_10y },
            ].filter(x => x.data && !(x.data as any).error).map(({ label, data }) => {
              const d = data as any
              const chg: number = d[field] ?? d.change_7d_pct ?? 0
              return (
                <StatCard
                  key={label}
                  label={label}
                  value={String(d.current)}
                  sub={`${chg >= 0 ? "+" : ""}${chg.toFixed(2)}% (${period})`}
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

      {/* Daily Target Trade Scanner */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
        <DipScannerCard />
        <ScannerPerformanceCard />
      </div>

      {/* Top Gainers / Losers */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.green, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            ▲ Top Gainers <span style={{ color: T.text3, fontWeight: 400, textTransform: "none" }}>({periodLabel})</span>
          </div>
          {gainers.length === 0
            ? <div style={{ fontSize: 12, color: T.text3 }}>{loading ? "Loading…" : "No data"}</div>
            : gainers.map(m => <MoverRow key={m.ticker} m={m} field={field} periodLabel={period} />)}
        </div>

        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.red, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            ▼ Top Losers <span style={{ color: T.text3, fontWeight: 400, textTransform: "none" }}>({periodLabel})</span>
          </div>
          {losers.length === 0
            ? <div style={{ fontSize: 12, color: T.text3 }}>{loading ? "Loading…" : "No data"}</div>
            : losers.map(m => <MoverRow key={m.ticker} m={m} field={field} periodLabel={period} />)}
        </div>
      </div>

      {/* Sector Rotation */}
      {sectors.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Sector Rotation <span style={{ color: T.text3, fontWeight: 400, textTransform: "none" }}>· {periodLabel}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
            {[...sectors].sort((a, b) => ((b as any)[field] ?? 0) - ((a as any)[field] ?? 0)).map((s: any) => {
              const pct: number = (s as any)[field] ?? s.change_5d_pct ?? 0
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
