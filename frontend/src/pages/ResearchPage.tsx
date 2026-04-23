import { useState, useCallback } from "react"
import { api } from "../services/api"
import { useSSE } from "../hooks/useSSE"
import { useStore } from "../store"
import { ModeToggle } from "../components/shared/ModeToggle"
import { PriceChart } from "../components/research/PriceChart"
import { SignalScore } from "../components/research/SignalScore"
import { NewsPanel } from "../components/research/NewsPanel"
import { StreamPanel } from "../components/research/StreamPanel"
import type { PriceData, TechnicalData, AnalystData, EarningsData, ConvergenceScore } from "../types"

interface ResearchState {
  price: PriceData | null
  technicals: TechnicalData | null
  analyst: AnalystData | null
  earnings: EarningsData | null
  news: any | null
  convergence: ConvergenceScore | null
  loading: boolean
  error: string | null
}

const MetricCard = ({ label, value, sub, valueColor }: { label: string; value: string; sub?: string; valueColor?: string }) => (
  <div style={{ background: "#f9fafb", borderRadius: 8, padding: "10px 14px" }}>
    <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 20, fontWeight: 500, color: valueColor || "#111" }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
  </div>
)

export function ResearchPage() {
  const [ticker, setTicker] = useState("")
  const [state, setState] = useState<ResearchState>({ price: null, technicals: null, analyst: null, earnings: null, news: null, convergence: null, loading: false, error: null })
  const { mode } = useStore()
  const { startResearch } = useSSE()

  const runResearch = useCallback(async (t: string) => {
    if (!t.trim()) return
    const sym = t.toUpperCase().trim()
    setState(s => ({ ...s, loading: true, error: null, price: null, technicals: null, analyst: null, earnings: null, news: null, convergence: null }))
    startResearch(sym, mode)

    try {
      const res = await api.get(`/research/data?ticker=${sym}`)
      const d = res.data
      setState(s => ({
        ...s,
        loading: false,
        price: d.price?.error ? null : d.price,
        technicals: d.technicals?.error ? null : d.technicals,
        analyst: d.analyst?.error ? null : d.analyst,
        earnings: d.earnings?.error ? null : d.earnings,
        news: d.news?.error ? null : d.news,
      }))
    } catch (e: any) {
      setState(s => ({ ...s, loading: false, error: e.response?.data?.detail || e.message }))
    }
  }, [mode, startResearch])

  const fmt = (n: number | null | undefined, prefix = "", suffix = "") =>
    n != null ? `${prefix}${n.toLocaleString()}${suffix}` : "—"

  const { price, analyst, earnings, technicals, news, convergence, loading, error } = state

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "1.5rem 1rem" }}>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: "1.25rem", alignItems: "center", flexWrap: "wrap" }}>
        <input
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === "Enter" && runResearch(ticker)}
          placeholder="Search ticker or company... e.g. GOOGL"
          style={{ flex: 1, minWidth: 200, padding: "8px 12px", fontSize: 14, border: "0.5px solid #d1d5db", borderRadius: 8, outline: "none" }}
        />
        <button
          onClick={() => runResearch(ticker)}
          disabled={loading}
          style={{ padding: "8px 20px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 8, background: loading ? "#f3f4f6" : "#111", color: loading ? "#9ca3af" : "#fff", cursor: loading ? "not-allowed" : "pointer" }}
        >
          {loading ? "Researching..." : "Research ↗"}
        </button>
        <ModeToggle />
      </div>

      {error && (
        <div style={{ background: "#fee2e2", color: "#991b1b", borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {/* Stream panel — shows agent thinking */}
      <StreamPanel />

      {/* Demo data when no research run yet */}
      {!price && !loading && (
        <div style={{ background: "#f9fafb", borderRadius: 12, padding: "2rem", textAlign: "center", color: "#6b7280", fontSize: 14 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>📈</div>
          <div style={{ fontWeight: 500, color: "#374151", marginBottom: 4 }}>Search a stock to begin</div>
          <div style={{ fontSize: 13 }}>Try AAPL, GOOGL, AMZN, NVDA, MSFT</div>
        </div>
      )}

      {/* Price header */}
      {price && (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: "1rem", flexWrap: "wrap" }}>
            <span style={{ fontSize: 22, fontWeight: 500 }}>{price.ticker}</span>
            <span style={{ fontSize: 13, color: "#6b7280" }}>{price.company_name}</span>
            <span style={{ fontSize: 20, fontWeight: 500 }}>${price.current_price.toLocaleString()}</span>
            <span style={{
              fontSize: 13, fontWeight: 500, padding: "2px 8px", borderRadius: 20,
              background: price.change_pct_7d >= 0 ? "#dcfce7" : "#fee2e2",
              color: price.change_pct_7d >= 0 ? "#166534" : "#991b1b",
            }}>
              {price.change_pct_7d >= 0 ? "▲" : "▼"} {Math.abs(price.change_pct_7d).toFixed(1)}% (7d)
            </span>
          </div>

          {/* Metric cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
            <MetricCard label="Day open" value={`$${price.day_open}`} />
            <MetricCard label="Day high" value={`$${price.day_high}`} valueColor="#16a34a" />
            <MetricCard label="Day low" value={`$${price.day_low}`} valueColor="#dc2626" />
            <MetricCard label="Volume" value={(price.volume / 1_000_000).toFixed(1) + "M"} sub={`Avg: ${(price.avg_volume / 1_000_000).toFixed(1)}M`} />
          </div>

          {/* Price chart */}
          <div style={{ marginBottom: 12 }}>
            <PriceChart data={price} />
          </div>

          {/* Three column panel */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {convergence && <SignalScore data={convergence} />}

            {analyst && (
              <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem" }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>
                  Analyst consensus
                  {analyst.consensus && (
                    <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 400, color: "#6b7280" }}>({analyst.consensus})</span>
                  )}
                </div>
                {analyst.num_analysts && (
                  <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 8 }}>{analyst.num_analysts} analysts</div>
                )}
                {analyst.recent_rating_changes?.slice(0, 3).map((rc: any, i: number) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#6b7280", padding: "3px 0", borderBottom: "0.5px solid #f3f4f6" }}>
                    <span>{rc.firm}</span>
                    <span style={{ color: rc.action === "up" ? "#16a34a" : rc.action === "down" ? "#dc2626" : "#6b7280", fontWeight: 500 }}>
                      {rc.from_grade ? `${rc.from_grade} → ` : ""}{rc.to_grade}
                    </span>
                  </div>
                ))}
                {analyst.price_target && (
                  <div style={{ borderTop: "0.5px solid #f3f4f6", marginTop: 8, paddingTop: 8 }}>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>Price target</div>
                    <div style={{ fontSize: 16, fontWeight: 500 }}>
                      ${analyst.price_target.toFixed(2)}
                      {analyst.upside_pct != null && (
                        <span style={{ fontSize: 12, color: analyst.upside_pct >= 0 ? "#16a34a" : "#dc2626", marginLeft: 6 }}>
                          {analyst.upside_pct >= 0 ? "+" : ""}{analyst.upside_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* News + earnings row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {news?.news && <NewsPanel news={news.news} />}
            {earnings && (
              <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem" }}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Earnings history</div>
                {earnings.next_earnings_date && (
                  <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
                    Next earnings: <strong style={{ color: "#111" }}>{earnings.next_earnings_date}</strong>
                  </div>
                )}
                {earnings.earnings_history.slice(0, 5).map((e, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "0.5px solid #f3f4f6", fontSize: 12 }}>
                    <span style={{ color: "#6b7280" }}>{e.date?.slice(0, 7)}</span>
                    <span style={{ color: e.beat ? "#16a34a" : e.beat === false ? "#dc2626" : "#9ca3af", fontWeight: 500 }}>
                      {e.beat ? "Beat ▲" : e.beat === false ? "Miss ▼" : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
