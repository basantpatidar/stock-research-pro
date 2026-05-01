import { useState, useCallback, useEffect } from "react"
import { useStore } from "../store"
import { useSSE } from "../hooks/useSSE"
import { researchV2 } from "../services/researchV2"
import { ModeToggle } from "../components/shared/ModeToggle"
import { ExpandablePanel } from "../components/shared/ExpandablePanel"
import { PriceChart } from "../components/research/PriceChart"
import { SignalScore } from "../components/research/SignalScore"
import { NewsPanel } from "../components/research/NewsPanel"
import { StreamPanel } from "../components/research/StreamPanel"
import { InvestorPersonasPanel } from "../components/research/InvestorPersonasPanel"
import { EarningsHistoryPanel } from "../components/research/EarningsHistoryPanel"
import EarningsQualityPanel from "../components/research/EarningsQualityPanel"
import { BullBearPanel, BacktesterPanel, CongressionalPanel, EarningsTranscriptPanel, PaperTradePanel } from "../components/research/Tier3Panels"
import { T, chgColor, chgDim } from "../theme"
import type { Tier1Response, PriceData, TechnicalData } from "../types"

type PanelEntry = { loading: boolean; data: any; error: string | null }

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
  <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 6, padding: "5px 10px" }}>
    <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>{label}</div>
    <div style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: color || T.text }}>{value}</div>
  </div>
)

function Tier2Content({ tool, data }: { tool: string; data: any }) {
  if (!data) return null

  if (tool === "get_earnings_quality")
    return <EarningsQualityPanel data={data} />

  if (tool === "get_convergence_score" && data.convergence_score != null)
    return <SignalScore data={data} />

  if (tool === "get_sentiment") {
    const bull = data.bullish_pct ?? data.bullish ?? 0
    const bear = data.bearish_pct ?? data.bearish ?? 0
    return (
      <div>
        {[{ label: "Bullish", pct: bull, color: T.green }, { label: "Bearish", pct: bear, color: T.red }].map(({ label, pct, color }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: T.text2, width: 55 }}>{label}</span>
            <div style={{ flex: 1, height: 6, background: T.border, borderRadius: 3, overflow: "hidden" }}>
              <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.6s ease" }} />
            </div>
            <span style={{ fontSize: 12, fontFamily: T.mono, color, width: 40, textAlign: "right" }}>{pct.toFixed(0)}%</span>
          </div>
        ))}
        {data.summary && <div style={{ fontSize: 12, color: T.text2, marginTop: 8 }}>{data.summary}</div>}
      </div>
    )
  }

  if (tool === "get_price_forecast") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {data.forecast && <div style={{ fontSize: 13, color: T.text, lineHeight: 1.55 }}>{data.forecast}</div>}
        {data.targets && (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {Object.entries(data.targets).map(([k, v]: [string, any]) => (
              <div key={k} style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 6, padding: "6px 10px" }}>
                <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.05em" }}>{k}</div>
                <div style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 500, color: T.text }}>{v}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (tool === "get_risk_reward") {
    const rr = data.risk_reward_ratio ?? data.rr_ratio
    const rrColor = rr != null ? (rr >= 2 ? T.green : rr >= 1 ? T.amber : T.red) : T.text2
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8 }}>
        {rr != null && <StatCard label="R/R Ratio" value={`${rr.toFixed(2)}:1`} color={rrColor} />}
        {data.entry_price  != null && <StatCard label="Entry"     value={`$${data.entry_price.toFixed(2)}`} />}
        {data.stop_loss    != null && <StatCard label="Stop Loss" value={`$${data.stop_loss.toFixed(2)}`}   color={T.red} />}
        {data.target_price != null && <StatCard label="Target"    value={`$${data.target_price.toFixed(2)}`} color={T.green} />}
      </div>
    )
  }

  return (
    <pre style={{ fontSize: 11, color: T.text2, fontFamily: T.mono, whiteSpace: "pre-wrap", margin: 0 }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export function ResearchPage() {
  const [ticker, setTicker] = useState("")
  const [tier1, setTier1] = useState<Tier1Response | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [panels, setPanels] = useState<Record<string, PanelEntry>>({})

  const { mode, execMode, addTokens, lastTicker, setLastTicker } = useStore()
  const { startResearch } = useSSE()

  // Restore last ticker on mount
  useEffect(() => {
    if (lastTicker) {
      setTicker(lastTicker)
      runSearch(lastTicker)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const runSearch = useCallback(async (t: string) => {
    if (!t.trim()) return
    const sym = t.toUpperCase().trim()
    setLoading(true)
    setError(null)
    setTier1(null)
    setPanels({})
    setLastTicker(sym)
    startResearch(sym, mode)

    try {
      const data = await researchV2.tier1(sym, mode, execMode)
      setTier1(data)
      setLoading(false)
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
      setLoading(false)
    }
  }, [mode, execMode, startResearch])

  const loadPanel = useCallback(async (tool: string, tier: 2 | 3 = 2) => {
    let shouldFetch = false
    setPanels(prev => {
      if (prev[tool]?.data || prev[tool]?.loading) return prev
      shouldFetch = true
      return { ...prev, [tool]: { loading: true, data: null, error: null } }
    })
    if (!shouldFetch || !tier1) return

    const extraParams: Record<string, unknown> = {}
    if (tool === "get_news_impact") {
      const pdata = tier1.price as any
      if (pdata?.company_name) extraParams.company_name = pdata.company_name
    }

    try {
      const res = tier === 3
        ? await researchV2.tier3(tier1.ticker, tool, mode)
        : await researchV2.tier2(tier1.ticker, tool, mode, execMode, extraParams)
      addTokens(res.tokens_used ?? 0)
      setPanels(prev => ({ ...prev, [tool]: { loading: false, data: res.result, error: null } }))
    } catch (e: any) {
      const msg = (e as any).response?.data?.detail || (e as any).message || "Request failed"
      setPanels(prev => ({ ...prev, [tool]: { loading: false, data: null, error: msg } }))
    }
  }, [tier1, mode, execMode, addTokens])

  const price      = tier1?.price      && !("error" in tier1.price)      ? tier1.price      as PriceData     : null
  const technicals = tier1?.technicals && !("error" in tier1.technicals) ? tier1.technicals as TechnicalData : null
  const analyst    = tier1?.analyst    && !("error" in tier1.analyst)    ? tier1.analyst    as any            : null
  const earnings   = tier1?.earnings   && !("error" in tier1.earnings)   ? tier1.earnings   as any            : null
  const newsData   = tier1?.news       && !("error" in tier1.news)       ? (tier1.news as any).news as any[]  : null

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <div style={{
          flex: 1, minWidth: 240, display: "flex", alignItems: "center",
          background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "0 12px",
        }}>
          <span style={{ color: T.text3, fontFamily: T.mono, fontSize: 14, marginRight: 8, flexShrink: 0 }}>$</span>
          <input
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && runSearch(ticker)}
            placeholder="Search ticker… AAPL, NVDA, GOOGL"
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: T.text, fontSize: 14, fontFamily: T.mono, padding: "9px 0", caretColor: T.blue,
            }}
          />
        </div>
        <button
          onClick={() => runSearch(ticker)}
          disabled={loading}
          style={{
            padding: "9px 22px", fontSize: 13, fontWeight: 500, border: "none", borderRadius: 8,
            cursor: loading ? "not-allowed" : "pointer",
            background: loading ? T.surface2 : T.blue,
            color: loading ? T.text2 : "#fff",
            boxShadow: loading ? "none" : T.blueGlow,
            transition: "all 0.15s ease",
          }}
        >
          {loading ? "Analyzing…" : "Research →"}
        </button>
        <ModeToggle />
      </div>

      {error && (
        <div style={{ background: T.redDim, color: T.red, border: `1px solid ${T.red}`, borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <StreamPanel />

      {/* Empty state */}
      {!tier1 && !loading && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, padding: "3rem 2rem", textAlign: "center" }}>
          <div style={{ fontFamily: T.mono, fontSize: 28, color: T.text3, marginBottom: 12 }}>$_</div>
          <div style={{ fontWeight: 500, color: T.text, marginBottom: 6 }}>Search a stock to begin</div>
          <div style={{ fontSize: 13, color: T.text2 }}>
            Try{" "}
            {["AAPL", "NVDA", "GOOGL", "AMZN", "TSLA"].map((t, i) => (
              <span key={t}>
                <button onClick={() => { setTicker(t); runSearch(t) }} style={{ background: "none", border: "none", cursor: "pointer", color: T.blue, fontFamily: T.mono, fontSize: 13, fontWeight: 500, textDecoration: "underline", textDecorationColor: T.blueDim, padding: "0 2px" }}>
                  {t}
                </button>
                {i < 4 && <span style={{ color: T.text3 }}>, </span>}
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
            <span style={{ fontSize: 22, fontWeight: 600, fontFamily: T.mono, color: T.text }}>${price.current_price.toLocaleString()}</span>
            {/* Session badge — only shown outside regular hours */}
            {price.market_state && !["REGULAR", "CLOSED"].includes(price.market_state) && (
              <span style={{
                fontSize: 10, fontWeight: 600, fontFamily: T.mono, letterSpacing: "0.06em",
                padding: "2px 7px", borderRadius: 4,
                background: T.surface2, border: `1px solid ${T.amber}`, color: T.amber,
              }}>
                {["PRE", "PREPRE"].includes(price.market_state) ? "PRE-MKT" : "AFTER-HRS"}
              </span>
            )}
            {/* Extended-hours change vs regular close */}
            {price.extended_change_pct != null && (
              <span style={{
                fontSize: 12, fontWeight: 500, fontFamily: T.mono,
                color: chgColor(price.extended_change_pct),
              }}>
                {price.extended_change_pct >= 0 ? "▲" : "▼"} {Math.abs(price.extended_change_pct).toFixed(2)}% from close
              </span>
            )}
            <span style={{
              fontSize: 13, fontWeight: 500, padding: "3px 10px", borderRadius: 20,
              background: chgDim(price.change_pct_7d), color: chgColor(price.change_pct_7d),
              border: `1px solid ${chgColor(price.change_pct_7d)}`, fontFamily: T.mono,
            }}>
              {price.change_pct_7d >= 0 ? "▲" : "▼"} {Math.abs(price.change_pct_7d).toFixed(2)}% 7d
            </span>
            {tier1?.cached && (
              <span style={{ fontSize: 10, color: T.text3, fontFamily: T.mono, padding: "2px 7px", background: T.surface2, borderRadius: 4, border: `1px solid ${T.border}` }}>
                cached
              </span>
            )}
          </div>

          {/* OHLCV */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
            <StatCard label="Open"   value={`$${price.day_open}`} />
            <StatCard label="High"   value={`$${price.day_high}`}  color={T.green} />
            <StatCard label="Low"    value={`$${price.day_low}`}   color={T.red} />
            <StatCard label="Volume" value={(price.volume / 1_000_000).toFixed(2) + "M"} sub={`Avg ${(price.avg_volume / 1_000_000).toFixed(1)}M`} />
          </div>

          {/* Technicals pills */}
          {technicals && (
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              {technicals.rsi_14 != null && (
                <TechPill label="RSI 14" value={technicals.rsi_14.toFixed(1)} color={technicals.rsi_14 > 70 ? T.red : technicals.rsi_14 < 30 ? T.green : T.text} />
              )}
              {technicals.macd?.signal != null && (
                <TechPill label="MACD Signal" value={technicals.macd.signal.toFixed(3)} color={technicals.macd.signal > 0 ? T.green : T.red} />
              )}
              {technicals.moving_averages?.ma_50d != null && (
                <TechPill label="MA 50d" value={`$${technicals.moving_averages.ma_50d.toFixed(0)}`} />
              )}
              {technicals.moving_averages?.ma_200d != null && (
                <TechPill label="MA 200d" value={`$${technicals.moving_averages.ma_200d.toFixed(0)}`} />
              )}
              {technicals.vwap_20d != null && (
                <TechPill label="VWAP 20d" value={`$${technicals.vwap_20d.toFixed(2)}`} color={price.current_price > technicals.vwap_20d ? T.green : T.red} />
              )}
            </div>
          )}

          {/* Price chart */}
          <div style={{ marginBottom: 12 }}><PriceChart data={price} /></div>

          {/* News (Tier 1 — fetched with price, always visible) */}
          <div style={{ marginBottom: 12 }}>
            {newsData && newsData.length > 0 && (
              <ExpandablePanel title="News" tier={1} autoExpand>
                <NewsPanel news={newsData} />
              </ExpandablePanel>
            )}
            {tier1?.news && "error" in tier1.news && (
              <div style={{ fontSize: 12, color: T.text3, padding: "6px 10px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8 }}>
                News unavailable — {(tier1.news as any).error}
              </div>
            )}
          </div>

          {/* Analyst + Earnings (Tier 1 — always visible) */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {analyst && (
              <ExpandablePanel title="Analyst Consensus" tier={1} autoExpand>
                <div style={{ fontSize: 12, color: T.text2, marginBottom: 10 }}>
                  {analyst.consensus} · <span style={{ fontFamily: T.mono }}>{analyst.num_analysts} analysts</span>
                </div>
                {analyst.total_ratings > 0 && (() => {
                  const rc = analyst.rating_counts
                  const tot = analyst.total_ratings
                  return [
                    { label: "Buy",  count: rc.strong_buy + rc.buy, color: T.green },
                    { label: "Hold", count: rc.hold,                color: T.amber },
                    { label: "Sell", count: rc.sell + rc.strong_sell, color: T.red },
                  ].map(({ label, count, color }) => {
                    const pct = Math.round((count / tot) * 100)
                    return (
                      <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                        <span style={{ fontSize: 11, color: T.text2, width: 28 }}>{label}</span>
                        <div style={{ flex: 1, height: 6, background: T.border, borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3 }} />
                        </div>
                        <span style={{ fontSize: 11, fontFamily: T.mono, width: 36, textAlign: "right", color }}>{count}</span>
                      </div>
                    )
                  })
                })()}
                {analyst.price_target && (
                  <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 8, paddingTop: 8 }}>
                    <Label>Price Target</Label>
                    <span style={{ fontSize: 16, fontWeight: 600, fontFamily: T.mono, color: T.text }}>${analyst.price_target.toFixed(2)}</span>
                    {analyst.upside_pct != null && (
                      <span style={{ marginLeft: 8, fontSize: 12, fontFamily: T.mono, color: analyst.upside_pct >= 0 ? T.green : T.red }}>
                        {analyst.upside_pct >= 0 ? "+" : ""}{analyst.upside_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                )}
              </ExpandablePanel>
            )}

            {earnings && (
              <ExpandablePanel title="Earnings History" tier={1} autoExpand>
                <EarningsHistoryPanel earnings={earnings} />
              </ExpandablePanel>
            )}
          </div>

          {/* ── Tier 2 panels ────────────────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {[
              { tool: "get_earnings_quality",  title: "Earnings Quality",   tokens: 0 },
              { tool: "get_sentiment",         title: "Market Sentiment",   tokens: 500 },
              { tool: "get_convergence_score", title: "Signal Convergence", tokens: 700 },
              { tool: "get_price_forecast",    title: "Price Forecast",     tokens: 800 },
              { tool: "get_risk_reward",       title: "Risk / Reward",      tokens: 500 },
            ].map(({ tool, title, tokens }) => {
              const p = panels[tool]
              return (
                <ExpandablePanel
                  key={tool} title={title} tier={2}
                  estimatedTokens={tokens}
                  loading={p?.loading ?? false}
                  error={p?.error ?? null}
                  onExpand={() => loadPanel(tool, 2)}
                  autoExpand={execMode === "deep"}
                >
                  <Tier2Content tool={tool} data={p?.data} />
                </ExpandablePanel>
              )
            })}
          </div>

          {/* ── Tier 3 panels ────────────────────────────────────────────── */}
          <div style={{ marginBottom: 4 }}>
            <div style={{ fontSize: 11, color: T.text3, fontFamily: T.mono, marginBottom: 8, letterSpacing: "0.05em" }}>
              DEEP ANALYSIS — click to run (uses 800–6K tokens each)
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { tool: "investor_personas",           title: "Investor Personas",   tokens: 5000, Component: InvestorPersonasPanel },
                { tool: "bull_bear_debate",            title: "Bull vs Bear Debate", tokens: 6000, Component: BullBearPanel },
                { tool: "run_backtest",                title: "Strategy Backtester", tokens: 0,    Component: BacktesterPanel },
                { tool: "analyze_earnings_transcript", title: "Earnings Transcript", tokens: 4000, Component: EarningsTranscriptPanel },
                { tool: "analyze_paper_trade",         title: "Paper Trade Coach",   tokens: 800,  Component: PaperTradePanel },
              ].map(({ tool, title, tokens, Component }) => {
                const p = panels[tool]
                return (
                  <ExpandablePanel
                    key={tool} title={title} tier={3}
                    estimatedTokens={tokens || undefined}
                    loading={p?.loading ?? false}
                    error={p?.error ?? null}
                    onExpand={() => loadPanel(tool, 3)}
                  >
                    <Component data={p?.data} />
                  </ExpandablePanel>
                )
              })}

              {/* Congressional uses tier1 data if available, tier3 otherwise */}
              {tier1?.congressional && !("error" in tier1.congressional) ? (
                <ExpandablePanel title="Congressional Trades" tier={1} autoExpand={false}>
                  <CongressionalPanel data={tier1.congressional} />
                </ExpandablePanel>
              ) : (
                <ExpandablePanel
                  title="Congressional Trades" tier={3}
                  loading={panels["get_congressional_trades"]?.loading ?? false}
                  error={panels["get_congressional_trades"]?.error ?? null}
                  onExpand={() => loadPanel("get_congressional_trades", 3)}
                >
                  <CongressionalPanel data={panels["get_congressional_trades"]?.data} />
                </ExpandablePanel>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
