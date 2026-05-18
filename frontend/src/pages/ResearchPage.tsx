import { useState, useCallback, useEffect, useMemo } from "react"
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
import OptionsIntelligencePanel from "../components/research/OptionsIntelligencePanel"
import { MultiTimeframePanel } from "../components/research/MultiTimeframePanel"
import { PreTradeScorecard } from "../components/research/PreTradeScorecard"
import { PositionSizer } from "../components/research/PositionSizer"
import { SeasonalityPanel } from "../components/research/SeasonalityPanel"
import { BullBearPanel, BacktesterPanel, CongressionalPanel, EarningsTranscriptPanel, PaperTradePanel, RiskFactorPanel, GuruHoldingsPanel } from "../components/research/Tier3Panels"
import { VolatilityPanel, RegimePanel } from "../components/research/VolatilityPanel"
import { ValuationPanel } from "../components/research/ValuationPanel"
import EDGARFundamentalsPanel from "../components/research/EDGARFundamentalsPanel"
import { CanslimPanel, VCPPanel } from "../components/research/CanslimPanel"
import { DividendPanel, MoatPanel } from "../components/research/FundamentalsQualityPanels"
import { T, chgColor, chgDim } from "../theme"
import type { Tier1Response, PriceData, TechnicalData, TradeMode, PreTradeScore, SmartMoneyScore, NewsItem } from "../types"

type PanelEntry = { loading: boolean; data: any; error: string | null }

// Determines whether a panel should render for the current mode.
// A panel tagged with ["day_trade"] hides in long_term mode (and vice versa).
// "both" mode always shows everything.
const show = (panelModes: TradeMode[], current: TradeMode): boolean =>
  current === "both" || panelModes.includes(current)

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

  if (tool === "get_options_intelligence")
    return <OptionsIntelligencePanel data={data} />

  if (tool === "get_mtf_confluence")
    return <MultiTimeframePanel data={data} />

  if (tool === "get_seasonality" && data.months)
    return <SeasonalityPanel data={data} />

  if (tool === "get_volatility_forecast")
    return <VolatilityPanel data={data} />

  if (tool === "get_regime")
    return <RegimePanel data={data} />

  if (tool === "get_valuation")
    return <ValuationPanel data={data} />

  if (tool === "get_edgar_fundamentals")
    return <EDGARFundamentalsPanel data={data} />

  if (tool === "get_canslim_score")
    return <CanslimPanel data={data} />

  if (tool === "get_vcp_pattern")
    return <VCPPanel data={data} />

  if (tool === "get_dividend_health")
    return <DividendPanel data={data} />

  if (tool === "get_moat_score")
    return <MoatPanel data={data} />

  if (tool === "get_guru_holdings")
    return <GuruHoldingsPanel data={data} />

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

// ── Mode-aware panel definitions ──────────────────────────────────────────────

const TIER2_PANELS: { tool: string; title: string; tokens: number; modes: TradeMode[] }[] = [
  { tool: "get_mtf_confluence",        title: "MTF Confluence",         tokens: 0,   modes: ["day_trade"] },
  { tool: "get_options_intelligence",  title: "Options Intelligence",   tokens: 0,   modes: ["day_trade"] },
  { tool: "get_volatility_forecast",   title: "Volatility Forecast",    tokens: 0,   modes: ["day_trade"] },
  { tool: "get_regime",                title: "Regime Classifier",      tokens: 0,   modes: ["day_trade"] },
  { tool: "get_sentiment",             title: "Market Sentiment",       tokens: 500, modes: ["day_trade", "long_term"] },
  { tool: "get_risk_reward",           title: "Risk / Reward",          tokens: 500, modes: ["day_trade"] },
  { tool: "get_convergence_score",     title: "Signal Convergence",     tokens: 700, modes: ["day_trade", "long_term"] },
  { tool: "get_price_forecast",        title: "Price Forecast",         tokens: 800, modes: ["day_trade", "long_term"] },
  { tool: "get_seasonality",           title: "Seasonality",            tokens: 0,   modes: ["day_trade", "long_term"] },
  { tool: "get_earnings_quality",      title: "Earnings Quality",       tokens: 0,   modes: ["long_term"] },
  { tool: "get_valuation",             title: "DCF & Valuation",        tokens: 0,   modes: ["long_term"] },
  { tool: "get_edgar_fundamentals",    title: "EDGAR 8-Year Financials",tokens: 0,   modes: ["long_term"] },
  { tool: "get_canslim_score",         title: "CANSLIM Score",          tokens: 0,   modes: ["long_term"] },
  { tool: "get_vcp_pattern",           title: "Minervini VCP Setup",    tokens: 0,   modes: ["long_term", "day_trade"] },
  { tool: "get_dividend_health",       title: "Dividend Health",        tokens: 0,   modes: ["long_term"] },
  { tool: "get_moat_score",            title: "Economic Moat",          tokens: 0,   modes: ["long_term"] },
  { tool: "get_guru_holdings",         title: "Guru Holdings (13F)",    tokens: 0,   modes: ["long_term"] },
]

const TIER3_PANELS: { tool: string; title: string; tokens: number; modes: TradeMode[]; Component: any }[] = [
  { tool: "run_backtest",                title: "Strategy Backtester",     tokens: 0,    modes: ["day_trade"],               Component: BacktesterPanel },
  { tool: "bull_bear_debate",            title: "Bull vs Bear Debate",     tokens: 6000, modes: ["day_trade", "long_term"],  Component: BullBearPanel },
  { tool: "analyze_paper_trade",         title: "Paper Trade Coach",       tokens: 800,  modes: ["day_trade"],               Component: PaperTradePanel },
  { tool: "investor_personas",           title: "Investor Personas",       tokens: 5000, modes: ["long_term"],               Component: InvestorPersonasPanel },
  { tool: "analyze_earnings_transcript", title: "Earnings Transcript",     tokens: 4000, modes: ["long_term"],               Component: EarningsTranscriptPanel },
  { tool: "get_risk_factor_changes",     title: "10-K Risk Factor Changes",tokens: 2000, modes: ["long_term"],               Component: RiskFactorPanel },
]

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

  const price        = tier1?.price        && !("error" in tier1.price)        ? tier1.price        as PriceData & { rvol?: { rvol: number | null; signal: string; time_normalized: boolean } } : null
  const technicals   = tier1?.technicals   && !("error" in tier1.technicals)   ? tier1.technicals   as TechnicalData : null
  const analyst      = tier1?.analyst      && !("error" in tier1.analyst)      ? tier1.analyst      as any           : null
  const earnings     = tier1?.earnings     && !("error" in tier1.earnings)     ? tier1.earnings     as any           : null
  const fundamentals = tier1?.fundamentals && !("error" in tier1.fundamentals) ? tier1.fundamentals as any           : null
  const shortInt     = tier1?.short_interest && !("error" in tier1.short_interest) ? tier1.short_interest as any     : null
  const newsData        = tier1?.news && !("error" in tier1.news) ? (tier1.news as any).news as NewsItem[] : null
  const newsFiltered    = tier1?.news && !("error" in tier1.news) ? ((tier1.news as any).filtered_count as number ?? 0) : 0

  // Chart default period — 1d for day trading, 3M for long-term research
  const chartDefault = useMemo(() => {
    if (mode === "long_term") return "3M" as const
    return "1d" as const
  }, [mode])

  const modeLabel = mode === "day_trade" ? "Day Trade" : mode === "long_term" ? "Long Term" : null

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

          {/* Mode filter indicator — only when a filter is active */}
          {modeLabel && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8, marginBottom: 14,
              padding: "6px 12px", borderRadius: 8,
              background: T.surface, border: `1px solid ${T.border}`,
              fontSize: 11, color: T.text2,
            }}>
              <span style={{
                padding: "2px 8px", borderRadius: 4, fontWeight: 600,
                background: mode === "day_trade" ? T.blueDim : T.surface2,
                color: mode === "day_trade" ? T.blue : T.amber,
                border: `1px solid ${mode === "day_trade" ? T.blue : T.amber}`,
                fontFamily: T.mono, fontSize: 10, letterSpacing: "0.06em",
              }}>
                {modeLabel.toUpperCase()} VIEW
              </span>
              <span>Some panels are filtered for this mode.</span>
              <span style={{ color: T.text3 }}>Switch to <strong style={{ color: T.text2 }}>Both</strong> to see all panels.</span>
            </div>
          )}

          {/* Ticker header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
            <span style={{ fontSize: 24, fontWeight: 600, fontFamily: T.mono, color: T.text }}>{price.ticker}</span>
            <span style={{ fontSize: 14, color: T.text2 }}>{price.company_name}</span>
            <span style={{ fontSize: 22, fontWeight: 600, fontFamily: T.mono, color: T.text }}>${price.current_price.toLocaleString()}</span>
            {price.market_state && !["REGULAR", "CLOSED"].includes(price.market_state) && (
              <span style={{
                fontSize: 10, fontWeight: 600, fontFamily: T.mono, letterSpacing: "0.06em",
                padding: "2px 7px", borderRadius: 4,
                background: T.surface2, border: `1px solid ${T.amber}`, color: T.amber,
              }}>
                {["PRE", "PREPRE"].includes(price.market_state) ? "PRE-MKT" : "AFTER-HRS"}
              </span>
            )}
            {price.extended_change_pct != null && (
              <span style={{ fontSize: 12, fontWeight: 500, fontFamily: T.mono, color: chgColor(price.extended_change_pct) }}>
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

          {/* OHLCV + RVOL */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
            <StatCard label="Open"   value={`$${price.day_open}`} />
            <StatCard label="High"   value={`$${price.day_high}`}  color={T.green} />
            <StatCard label="Low"    value={`$${price.day_low}`}   color={T.red} />
            <StatCard
              label="Volume"
              value={(price.volume / 1_000_000).toFixed(2) + "M"}
              sub={`Avg ${(price.avg_volume / 1_000_000).toFixed(1)}M`}
            />
          </div>
          {/* RVOL badge — day trade view, during regular session */}
          {show(["day_trade"], mode) && price.rvol?.rvol != null && price.rvol.time_normalized && (() => {
            const rv = price.rvol!
            const rvColor = rv.signal === "EXTREME" ? T.red : rv.signal === "HIGH" ? T.amber : rv.signal === "NORMAL" ? T.green : T.text3
            return (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "5px 12px", borderRadius: 20,
                  background: `${rvColor}18`, border: `1px solid ${rvColor}`,
                }}>
                  <span style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em" }}>RVOL</span>
                  <span style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 700, color: rvColor }}>{rv.rvol!.toFixed(2)}x</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: rvColor, fontFamily: T.mono, letterSpacing: "0.06em" }}>{rv.signal}</span>
                </div>
                <span style={{ fontSize: 11, color: T.text3 }}>relative to avg volume at this time of day</span>
              </div>
            )
          })()}

          {/* Pre-Trade Scorecard — Day Trade only */}
          {show(["day_trade"], mode) && tier1?.pretrade_score && (
            <div style={{ marginBottom: 12 }}>
              <PreTradeScorecard data={tier1.pretrade_score as PreTradeScore} />
            </div>
          )}

          {/* Smart Money Score — both modes */}
          {tier1?.smart_money && (tier1.smart_money as SmartMoneyScore).signals.length > 0 && (() => {
            const sm = tier1.smart_money as SmartMoneyScore
            const vColor = sm.color === "green" ? T.green : sm.color === "red" ? T.red : T.text2
            return (
              <div style={{
                background: T.surface, border: `1px solid ${T.border}`,
                borderRadius: 10, padding: "10px 14px", marginBottom: 12,
                display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em" }}>Smart Money</span>
                  <span style={{
                    fontSize: 11, fontWeight: 700, fontFamily: T.mono,
                    padding: "2px 10px", borderRadius: 4,
                    background: vColor + "20", color: vColor,
                    border: `1px solid ${vColor}40`,
                  }}>
                    {sm.verdict}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {sm.signals.map((s, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                        background: s.direction === "bullish" ? T.green : T.red,
                        display: "inline-block",
                      }} />
                      <span style={{ fontSize: 11, color: T.text2 }}>{s.label}</span>
                      <span style={{ fontSize: 10, color: T.text3 }}>— {s.detail}</span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* Position Sizer — Day Trade + Both */}
          {show(["day_trade"], mode) && price && (
            <div style={{ marginBottom: 12 }}>
              <ExpandablePanel title="Position Sizer" tier={1} autoExpand>
                <PositionSizer currentPrice={price.current_price} />
              </ExpandablePanel>
            </div>
          )}

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
              {technicals.rs_rating != null && (
                <TechPill
                  label="RS Rating"
                  value={`${technicals.rs_rating}`}
                  color={technicals.rs_rating >= 80 ? T.green : technicals.rs_rating >= 60 ? T.amber : technicals.rs_rating >= 40 ? T.text2 : T.red}
                />
              )}
            </div>
          )}

          {/* Price chart — default period changes by mode */}
          <div style={{ marginBottom: 12 }}>
            <PriceChart data={price} defaultPeriod={chartDefault} />
          </div>

          {/* Short Interest — Day Trade only */}
          {show(["day_trade"], mode) && shortInt && (
            <div style={{ marginBottom: 12 }}>
              <ExpandablePanel title="Short Interest" tier={1} autoExpand>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 8 }}>
                  {shortInt.short_pct_of_float != null && (
                    <StatCard
                      label="Short Float %"
                      value={`${shortInt.short_pct_of_float.toFixed(1)}%`}
                      color={shortInt.short_pct_of_float > 20 ? T.red : shortInt.short_pct_of_float > 10 ? T.amber : T.green}
                    />
                  )}
                  {shortInt.days_to_cover != null && (
                    <StatCard label="Days to Cover" value={shortInt.days_to_cover.toFixed(1) + "d"} />
                  )}
                  {shortInt.change_vs_prior_month_pct != null && (
                    <StatCard
                      label="vs Prior Month"
                      value={`${shortInt.change_vs_prior_month_pct >= 0 ? "+" : ""}${shortInt.change_vs_prior_month_pct.toFixed(1)}%`}
                      color={shortInt.change_vs_prior_month_pct > 0 ? T.red : T.green}
                    />
                  )}
                  {shortInt.float_class && (
                    <StatCard
                      label="Float Class"
                      value={shortInt.float_class.toUpperCase()}
                      color={shortInt.float_class === "nano" ? T.red : shortInt.float_class === "micro" ? T.amber : T.text2}
                    />
                  )}
                  {shortInt.vol_ratio != null && (
                    <StatCard
                      label="Vol Ratio"
                      value={`${shortInt.vol_ratio.toFixed(1)}×`}
                      color={shortInt.vol_ratio > 2 ? T.green : T.text2}
                    />
                  )}
                  {shortInt.squeeze_score != null && (
                    <StatCard
                      label="Squeeze Score"
                      value={`${shortInt.squeeze_score}/100`}
                      color={shortInt.squeeze_score >= 65 ? T.red : shortInt.squeeze_score >= 45 ? T.amber : T.text2}
                    />
                  )}
                </div>
                {shortInt.squeeze_tier && (
                  <div style={{ fontSize: 11, color: T.amber, marginTop: 6, fontFamily: T.mono, fontWeight: 600 }}>
                    {shortInt.squeeze_tier}
                  </div>
                )}
                {shortInt.signal && (
                  <div style={{ fontSize: 11, color: T.text3, marginTop: 4, fontFamily: T.mono }}>
                    Signal: {shortInt.signal}
                  </div>
                )}
              </ExpandablePanel>
            </div>
          )}

          {/* News (T1 — always visible) */}
          <div style={{ marginBottom: 12 }}>
            {newsData && newsData.length > 0 && (
              <ExpandablePanel title="News" tier={1} autoExpand>
                <NewsPanel news={newsData} filteredCount={newsFiltered} />
              </ExpandablePanel>
            )}
            {tier1?.news && "error" in tier1.news && (
              <div style={{ fontSize: 12, color: T.text3, padding: "6px 10px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8 }}>
                News unavailable — {(tier1.news as any).error}
              </div>
            )}
          </div>

          {/* Analyst + Earnings — Long Term only */}
          {show(["long_term"], mode) && (analyst || earnings) && (
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
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                        <div>
                          <Label>Price Target (Mean)</Label>
                          <span style={{ fontSize: 16, fontWeight: 600, fontFamily: T.mono, color: T.text }}>${analyst.price_target.toFixed(2)}</span>
                          {analyst.upside_pct != null && (
                            <span style={{ marginLeft: 8, fontSize: 12, fontFamily: T.mono, color: analyst.upside_pct >= 0 ? T.green : T.red }}>
                              {analyst.upside_pct >= 0 ? "+" : ""}{analyst.upside_pct.toFixed(1)}% upside
                            </span>
                          )}
                        </div>
                        {analyst.target_low != null && analyst.target_high != null && (
                          <div style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>
                            range: <span style={{ color: T.red }}>${analyst.target_low.toFixed(0)}</span>
                            {" — "}
                            <span style={{ color: T.green }}>${analyst.target_high.toFixed(0)}</span>
                          </div>
                        )}
                        {analyst.target_trend && (
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 12,
                            background: analyst.target_trend === "RISING" ? T.greenDim : analyst.target_trend === "FALLING" ? T.redDim : T.surface2,
                            color: analyst.target_trend === "RISING" ? T.green : analyst.target_trend === "FALLING" ? T.red : T.text2,
                            border: `1px solid ${analyst.target_trend === "RISING" ? T.green : analyst.target_trend === "FALLING" ? T.red : T.border}`,
                          }}>
                            {analyst.target_trend === "RISING" ? "↑" : analyst.target_trend === "FALLING" ? "↓" : "→"} {analyst.target_trend}
                          </span>
                        )}
                      </div>
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
          )}

          {/* Fundamentals — Long Term only */}
          {show(["long_term"], mode) && fundamentals && (
            <div style={{ marginBottom: 12 }}>
              <ExpandablePanel title="Fundamentals" tier={1} autoExpand>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 8 }}>
                  {fundamentals.pe_ratio != null && <StatCard label="P/E (TTM)"   value={fundamentals.pe_ratio.toFixed(1)} />}
                  {fundamentals.forward_pe != null && <StatCard label="Forward P/E" value={fundamentals.forward_pe.toFixed(1)} />}
                  {fundamentals.profit_margin != null && (
                    <StatCard label="Net Margin" value={`${(fundamentals.profit_margin * 100).toFixed(1)}%`}
                      color={fundamentals.profit_margin > 0.15 ? T.green : fundamentals.profit_margin > 0 ? T.amber : T.red} />
                  )}
                  {fundamentals.debt_to_equity != null && (
                    <StatCard label="Debt/Equity" value={fundamentals.debt_to_equity.toFixed(2)}
                      color={fundamentals.debt_to_equity > 2 ? T.red : fundamentals.debt_to_equity > 1 ? T.amber : T.green} />
                  )}
                  {fundamentals.return_on_equity != null && (
                    <StatCard label="ROE" value={`${(fundamentals.return_on_equity * 100).toFixed(1)}%`}
                      color={fundamentals.return_on_equity > 0.15 ? T.green : fundamentals.return_on_equity > 0 ? T.amber : T.red} />
                  )}
                  {fundamentals.free_cash_flow != null && (
                    <StatCard label="Free Cash Flow"
                      value={Math.abs(fundamentals.free_cash_flow) > 1e9
                        ? `${(fundamentals.free_cash_flow / 1e9).toFixed(1)}B`
                        : `${(fundamentals.free_cash_flow / 1e6).toFixed(0)}M`}
                      color={fundamentals.free_cash_flow > 0 ? T.green : T.red} />
                  )}
                </div>
              </ExpandablePanel>
            </div>
          )}

          {/* ── Tier 2 panels (mode-filtered) ───────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {TIER2_PANELS.filter(p => show(p.modes, mode)).map(({ tool, title, tokens }) => {
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

          {/* ── Tier 3 panels (mode-filtered) ───────────────────────────── */}
          <div style={{ marginBottom: 4 }}>
            <div style={{ fontSize: 11, color: T.text3, fontFamily: T.mono, marginBottom: 8, letterSpacing: "0.05em" }}>
              DEEP ANALYSIS — click to run (uses 800–6K tokens each)
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {TIER3_PANELS.filter(p => show(p.modes, mode)).map(({ tool, title, tokens, Component }) => {
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

              {/* Congressional — Long Term only */}
              {show(["long_term"], mode) && (
                tier1?.congressional && !("error" in tier1.congressional) ? (
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
                )
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
