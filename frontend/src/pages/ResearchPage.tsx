import { useState, useCallback } from "react"
import { api } from "../services/api"
import { useStore } from "../store"
import { useSSE } from "../hooks/useSSE"
import { ModeToggle } from "../components/shared/ModeToggle"
import { PriceChart } from "../components/research/PriceChart"
import { SignalScore } from "../components/research/SignalScore"
import { NewsPanel } from "../components/research/NewsPanel"
import { StreamPanel } from "../components/research/StreamPanel"
import { T, chgColor, chgDim } from "../theme"
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

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3, fontWeight: 500 }}>
    {children}
  </div>
)

const StatCard = ({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) => (
  <div style={{ background: T.surface2, borderRadius: 8, padding: "10px 13px", border: `1px solid ${T.border}` }}>
    <Label>{label}</Label>
    <div style={{ fontSize: 18, fontWeight: 500, color: color || T.text, fontFamily: T.mono }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: T.text3, marginTop: 2, fontFamily: T.mono }}>{sub}</div>}
  </div>
)

const TechPill = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div style={{
    background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 6,
    padding: "5px 10px", display: "flex", flexDirection: "column", gap: 2,
  }}>
    <span style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
    <span style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: color || T.text }}>{value}</span>
  </div>
)

export function ResearchPage() {
  const [ticker, setTicker] = useState("")
  const [state, setState] = useState<ResearchState>({
    price: null, technicals: null, analyst: null,
    earnings: null, news: null, convergence: null, loading: false, error: null,
  })
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
      const priceData = d.price?.error ? null : d.price
      const errors = [d.price, d.technicals, d.analyst, d.earnings, d.news]
        .filter((x: any) => x?.error).map((x: any) => x.error)
      setState(s => ({
        ...s, loading: false,
        error: !priceData && errors.length > 0 ? errors[0] : null,
        price: priceData,
        technicals: d.technicals?.error ? null : d.technicals,
        analyst: d.analyst?.error ? null : d.analyst,
        earnings: d.earnings?.error ? null : d.earnings,
        news: d.news?.error ? null : d.news,
      }))
    } catch (e: any) {
      setState(s => ({ ...s, loading: false, error: e.response?.data?.detail || e.message }))
    }
  }, [mode, startResearch])

  const { price, analyst, earnings, technicals, news, convergence, loading, error } = state

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <div style={{
          flex: 1, minWidth: 240, display: "flex", alignItems: "center",
          background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8,
          padding: "0 12px",
          transition: "border-color 0.15s",
        }}>
          <span style={{ color: T.text3, fontFamily: T.mono, fontSize: 14, marginRight: 8, flexShrink: 0 }}>$</span>
          <input
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && runResearch(ticker)}
            placeholder="Search ticker… AAPL, NVDA, GOOGL"
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: T.text, fontSize: 14, fontFamily: T.mono, padding: "9px 0",
              caretColor: T.blue,
            }}
          />
        </div>
        <button
          onClick={() => runResearch(ticker)}
          disabled={loading}
          style={{
            padding: "9px 22px", fontSize: 13, fontWeight: 500,
            border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer",
            background: loading ? T.surface2 : T.blue,
            color: loading ? T.text2 : "#fff",
            transition: "all 0.15s ease",
            boxShadow: loading ? "none" : `0 0 16px ${T.blueDim}`,
          }}
        >
          {loading ? "Analyzing…" : "Research →"}
        </button>
        <ModeToggle />
      </div>

      {error && (
        <div style={{
          background: T.redDim, color: T.red, border: `1px solid ${T.red}`,
          borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 12,
        }}>
          {error}
        </div>
      )}

      {/* Stream panel — agent reasoning */}
      <StreamPanel />

      {/* Empty state */}
      {!price && !loading && (
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 14, padding: "3rem 2rem", textAlign: "center",
        }}>
          <div style={{ fontFamily: T.mono, fontSize: 28, color: T.text3, marginBottom: 12 }}>$_</div>
          <div style={{ fontWeight: 500, color: T.text, marginBottom: 6 }}>Search a stock to begin</div>
          <div style={{ fontSize: 13, color: T.text2 }}>
            Try{" "}
            {["AAPL", "NVDA", "GOOGL", "AMZN", "TSLA"].map((t, i) => (
              <span key={t}>
                <button
                  onClick={() => { setTicker(t); runResearch(t) }}
                  style={{
                    background: "none", border: "none", cursor: "pointer", padding: "0 2px",
                    color: T.blue, fontFamily: T.mono, fontSize: 13, fontWeight: 500,
                    textDecoration: "underline", textDecorationColor: T.blueDim,
                  }}
                >{t}</button>
                {i < 4 ? <span style={{ color: T.text3 }}>, </span> : null}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main data view */}
      {price && (
        <div className="animate-in">
          {/* Ticker header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
            <span style={{ fontSize: 24, fontWeight: 600, fontFamily: T.mono, color: T.text }}>{price.ticker}</span>
            <span style={{ fontSize: 14, color: T.text2 }}>{price.company_name}</span>
            <span style={{ fontSize: 22, fontWeight: 600, fontFamily: T.mono, color: T.text }}>
              ${price.current_price.toLocaleString()}
            </span>
            <span style={{
              fontSize: 13, fontWeight: 500, padding: "3px 10px", borderRadius: 20,
              background: chgDim(price.change_pct_7d),
              color: chgColor(price.change_pct_7d),
              border: `1px solid ${chgColor(price.change_pct_7d)}`,
              fontFamily: T.mono,
            }}>
              {price.change_pct_7d >= 0 ? "▲" : "▼"} {Math.abs(price.change_pct_7d).toFixed(2)}% 7d
            </span>
          </div>

          {/* OHLCV stat cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
            <StatCard label="Open" value={`$${price.day_open}`} />
            <StatCard label="High" value={`$${price.day_high}`} color={T.green} />
            <StatCard label="Low"  value={`$${price.day_low}`}  color={T.red} />
            <StatCard
              label="Volume"
              value={(price.volume / 1_000_000).toFixed(2) + "M"}
              sub={`Avg ${(price.avg_volume / 1_000_000).toFixed(1)}M`}
            />
          </div>

          {/* Technicals row */}
          {technicals && !technicals.error && (
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              {technicals.rsi != null && (
                <TechPill
                  label="RSI"
                  value={technicals.rsi.toFixed(1)}
                  color={technicals.rsi > 70 ? T.red : technicals.rsi < 30 ? T.green : T.text}
                />
              )}
              {technicals.macd?.signal != null && (
                <TechPill
                  label="MACD Signal"
                  value={technicals.macd.signal.toFixed(3)}
                  color={technicals.macd.signal > 0 ? T.green : T.red}
                />
              )}
              {technicals.ma_50d != null && (
                <TechPill label="MA 50d" value={`$${technicals.ma_50d.toFixed(0)}`} />
              )}
              {technicals.ma_200d != null && (
                <TechPill label="MA 200d" value={`$${technicals.ma_200d.toFixed(0)}`} />
              )}
              {technicals.vwap != null && (
                <TechPill
                  label="VWAP"
                  value={`$${technicals.vwap.toFixed(2)}`}
                  color={price.current_price > technicals.vwap ? T.green : T.red}
                />
              )}
            </div>
          )}

          {/* Price chart */}
          <div style={{ marginBottom: 12 }}>
            <PriceChart data={price} />
          </div>

          {/* Signal + Analyst row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {convergence && <SignalScore data={convergence} />}

            {analyst && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
                  Analyst Consensus
                  {analyst.consensus && (
                    <span style={{ marginLeft: 8, color: T.blue, fontWeight: 400, textTransform: "none" }}>({analyst.consensus})</span>
                  )}
                </div>
                {analyst.num_analysts && (
                  <div style={{ fontSize: 11, color: T.text3, marginBottom: 12, fontFamily: T.mono }}>{analyst.num_analysts} analysts</div>
                )}

                {analyst.total_ratings > 0 && (() => {
                  const rc = analyst.rating_counts
                  const total = analyst.total_ratings
                  const bars = [
                    { label: "Buy",  count: rc.strong_buy + rc.buy,     color: T.green },
                    { label: "Hold", count: rc.hold,                    color: T.amber },
                    { label: "Sell", count: rc.sell + rc.strong_sell,   color: T.red },
                  ]
                  return (
                    <div style={{ marginBottom: 12 }}>
                      {bars.map(({ label, count, color }) => {
                        const pct = Math.round((count / total) * 100)
                        return (
                          <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                            <span style={{ fontSize: 11, color: T.text2, width: 28 }}>{label}</span>
                            <div style={{ flex: 1, height: 6, background: T.border, borderRadius: 3, overflow: "hidden" }}>
                              <div style={{
                                width: `${pct}%`, height: "100%", background: color, borderRadius: 3,
                                transition: "width 0.6s ease",
                              }} />
                            </div>
                            <span style={{ fontSize: 11, fontFamily: T.mono, width: 40, textAlign: "right", color }}>{count}</span>
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}

                {analyst.price_target && (
                  <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
                    <Label>Price Target</Label>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontSize: 18, fontWeight: 600, fontFamily: T.mono, color: T.text }}>
                        ${analyst.price_target.toFixed(2)}
                      </span>
                      {analyst.upside_pct != null && (
                        <span style={{
                          fontSize: 12, fontFamily: T.mono, fontWeight: 500,
                          color: analyst.upside_pct >= 0 ? T.green : T.red,
                        }}>
                          {analyst.upside_pct >= 0 ? "+" : ""}{analyst.upside_pct.toFixed(1)}% upside
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* News + Earnings row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {news?.news && <NewsPanel news={news.news} />}

            {earnings && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
                  Earnings History
                </div>
                {earnings.next_earnings_date && (
                  <div style={{
                    fontSize: 12, color: T.text2, marginBottom: 12, padding: "6px 10px",
                    background: T.blueDim, borderRadius: 6, border: `1px solid ${T.blue}`,
                  }}>
                    Next: <span style={{ color: T.blue, fontFamily: T.mono, fontWeight: 500 }}>{earnings.next_earnings_date}</span>
                  </div>
                )}
                {earnings.earnings_history.slice(0, 6).map((e: any, i: number) => (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "7px 0", borderBottom: i < 5 ? `1px solid ${T.border}` : "none",
                  }}>
                    <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono }}>{e.date?.slice(0, 7)}</span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, fontFamily: T.mono, padding: "2px 8px",
                      borderRadius: 4,
                      background: e.beat ? T.greenDim : e.beat === false ? T.redDim : T.surface2,
                      color: e.beat ? T.green : e.beat === false ? T.red : T.text3,
                    }}>
                      {e.beat ? "▲ Beat" : e.beat === false ? "▼ Miss" : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
