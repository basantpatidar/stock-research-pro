import { useState } from "react"
import { useScreener } from "../hooks/useScreener"
import { useWatchlist } from "../hooks/useWatchlist"
import { T, chgColor } from "../theme"
import type { ScreenerFilters } from "../types"

const SECTORS = ["all", "Technology", "Healthcare", "Financials", "Energy", "Consumer Discretionary", "Industrials", "Communication Services"]

const oppStyle = (change: number) => {
  if (change <= -15) return { bg: T.greenDim,  color: T.green,  label: "Buy now",     border: T.green }
  if (change <= -10) return { bg: "rgba(16,185,129,0.07)", color: "#34d399", label: "Buy — 1wk", border: "#34d399" }
  if (change <= -5)  return { bg: T.amberDim,  color: T.amber,  label: "Monitor",     border: T.amber }
  return                    { bg: T.surface2,  color: T.text2,  label: "Neutral",     border: T.borderBright }
}

const FilterSelect = ({
  label, value, options, onChange
}: {
  label: string
  value: number | string
  options: [number | string, string][]
  onChange: (v: number | string) => void
}) => (
  <div style={{ background: T.surface2, borderRadius: 8, padding: "10px 13px", border: `1px solid ${T.border}` }}>
    <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
      {label}
    </div>
    <select
      value={value}
      onChange={e => onChange(typeof value === "number" ? Number(e.target.value) : e.target.value)}
      style={{
        width: "100%", padding: "6px 8px", fontSize: 13,
        border: `1px solid ${T.border}`, borderRadius: 6,
        background: T.surface, color: T.text, outline: "none",
        cursor: "pointer",
      }}
    >
      {options.map(([val, lbl]) => <option key={String(val)} value={val}>{lbl}</option>)}
    </select>
  </div>
)

export function ScreenerPage() {
  const { filters, setFilters, results, loading, error, runScreener, savePreset, fetchPresets, presets } = useScreener()
  const { addTicker } = useWatchlist()
  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [presetName, setPresetName] = useState("")
  const [autoMonitor, setAutoMonitor] = useState(false)
  const [addedTickers, setAddedTickers] = useState<Set<string>>(new Set())

  const handleSavePreset = async () => {
    if (!presetName.trim()) return
    await savePreset(presetName, autoMonitor)
    setSaveModalOpen(false)
    setPresetName("")
  }

  const handleAddToWatchlist = async (ticker: string) => {
    await addTicker(ticker)
    setAddedTickers(s => new Set([...s, ticker]))
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      {/* Page header */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Stock Screener</div>
        <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>Filter large-cap stocks by fundamentals &amp; momentum</div>
      </div>

      {/* Filters panel */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
          <FilterSelect
            label="Market cap (min)"
            value={filters.min_market_cap_b}
            options={[[100, "$100B+"], [50, "$50B+"], [10, "$10B+"], [1, "$1B+"]]}
            onChange={v => setFilters({ ...filters, min_market_cap_b: v as number })}
          />
          <FilterSelect
            label="Daily volume (min)"
            value={filters.min_volume}
            options={[[1_000_000, "1M+ shares"], [500_000, "500K+"], [100_000, "100K+"]]}
            onChange={v => setFilters({ ...filters, min_volume: v as number })}
          />
          <FilterSelect
            label="Price drop trigger (7d)"
            value={filters.min_price_drop_pct}
            options={[[5, "−5%+"], [10, "−10%+"], [15, "−15%+"], [20, "−20%+"]]}
            onChange={v => setFilters({ ...filters, min_price_drop_pct: v as number })}
          />
          <FilterSelect
            label="Max P/E ratio"
            value={filters.max_pe}
            options={[[0, "Any"], [20, "Under 20×"], [30, "Under 30×"], [50, "Under 50×"]]}
            onChange={v => setFilters({ ...filters, max_pe: v as number })}
          />
          <FilterSelect
            label="Sector"
            value={filters.sector}
            options={SECTORS.map(s => [s, s === "all" ? "All sectors" : s])}
            onChange={v => setFilters({ ...filters, sector: v as string })}
          />
          <FilterSelect
            label="Universe"
            value={filters.universe ?? "sp500"}
            options={[
              ["sp500", "S&P 500 (~150)"],
              ["nasdaq100", "NASDAQ-100 (~40)"],
              ["etfs", "Major ETFs (~24)"],
              ["mega", "Mega-cap ($200B+)"],
              ["legacy", "Legacy 30"],
            ]}
            onChange={v => setFilters({ ...filters, universe: v as ScreenerFilters["universe"] })}
          />
          <FilterSelect
            label="Limit"
            value={filters.limit ?? 50}
            options={[[20, "Top 20"], [50, "Top 50"], [100, "Top 100"], [150, "Top 150"]]}
            onChange={v => setFilters({ ...filters, limit: v as number })}
          />
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={() => runScreener()}
            disabled={loading}
            style={{
              padding: "8px 22px", fontSize: 13, fontWeight: 500, border: "none",
              borderRadius: 8, cursor: loading ? "not-allowed" : "pointer",
              background: loading ? T.surface2 : T.blue,
              color: loading ? T.text2 : "#fff",
              boxShadow: loading ? "none" : T.blueGlow,
              transition: "all 0.15s ease",
            }}
          >
            {loading ? "Scanning…" : "Run Screener →"}
          </button>
          <button
            onClick={() => setSaveModalOpen(true)}
            style={{
              padding: "8px 14px", fontSize: 13, border: `1px solid ${T.border}`,
              borderRadius: 8, background: "transparent", cursor: "pointer", color: T.text2,
              transition: "all 0.12s ease",
            }}
          >
            Save preset
          </button>
          <button
            onClick={fetchPresets}
            style={{
              padding: "8px 14px", fontSize: 13, border: `1px solid ${T.border}`,
              borderRadius: 8, background: "transparent", cursor: "pointer", color: T.text2,
            }}
          >
            Load preset
          </button>
          {presets.length > 0 && (
            <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>
              {presets.length} saved presets
            </span>
          )}
        </div>
      </div>

      {error && (
        <div style={{
          background: T.redDim, color: T.red, border: `1px solid ${T.red}`,
          borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 12,
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="animate-in" style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{
            padding: "10px 16px", borderBottom: `1px solid ${T.border}`,
            background: T.surface2, fontSize: 13, color: T.text2,
          }}>
            <span style={{ fontFamily: T.mono, fontWeight: 600, color: T.blue }}>{results.length}</span>
            <span style={{ marginLeft: 5 }}>stocks match your filters</span>
          </div>

          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "64px 1fr 80px 70px 64px 100px 110px",
            gap: 10, padding: "8px 16px", borderBottom: `1px solid ${T.border}`,
            background: T.surface2,
          }}>
            {["Ticker", "Company", "Mkt Cap", "Volume", "7d", "Opportunity", ""].map((h, i) => (
              <span key={i} style={{ fontSize: 10, color: T.text3, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                {h}
              </span>
            ))}
          </div>

          {results.map((r, idx) => {
            const opp = oppStyle(r.change_7d_pct)
            const added = addedTickers.has(r.ticker)
            return (
              <div
                key={r.ticker}
                style={{
                  display: "grid",
                  gridTemplateColumns: "64px 1fr 80px 70px 64px 100px 110px",
                  gap: 10, padding: "10px 16px",
                  borderBottom: idx < results.length - 1 ? `1px solid ${T.border}` : "none",
                  alignItems: "center",
                  transition: "background 0.1s ease",
                }}
                onMouseEnter={e => (e.currentTarget.style.background = T.surfaceHover)}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <span style={{ fontSize: 13, fontWeight: 600, fontFamily: T.mono, color: T.text }}>{r.ticker}</span>
                <span style={{ fontSize: 12, color: T.text2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.company}</span>
                <span style={{ fontSize: 12, fontFamily: T.mono, color: T.text2 }}>${r.market_cap_b}B</span>
                <span style={{ fontSize: 12, fontFamily: T.mono, color: T.text2 }}>{(r.avg_volume / 1_000_000).toFixed(1)}M</span>
                <span style={{ fontSize: 12, fontFamily: T.mono, fontWeight: 600, color: chgColor(r.change_7d_pct) }}>
                  {r.change_7d_pct >= 0 ? "+" : ""}{r.change_7d_pct.toFixed(1)}%
                </span>
                <span style={{
                  display: "inline-block", fontSize: 10, fontWeight: 600, padding: "3px 8px",
                  borderRadius: 20, background: opp.bg, color: opp.color,
                  border: `1px solid ${opp.border}`, letterSpacing: "0.02em",
                }}>
                  {opp.label}
                </span>
                <button
                  onClick={() => handleAddToWatchlist(r.ticker)}
                  disabled={added}
                  style={{
                    fontSize: 11, padding: "4px 10px", border: `1px solid ${added ? T.border : T.borderBright}`,
                    borderRadius: 6, cursor: added ? "default" : "pointer",
                    background: added ? T.surface2 : "transparent",
                    color: added ? T.text3 : T.text2,
                    transition: "all 0.12s ease",
                  }}
                >
                  {added ? "✓ Added" : "+ Watchlist"}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {results.length === 0 && !loading && (
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 14, padding: "3rem 2rem", textAlign: "center",
        }}>
          <div style={{ fontSize: 28, color: T.text3, fontFamily: T.mono, marginBottom: 10 }}>⊛</div>
          <div style={{ color: T.text, fontWeight: 500, marginBottom: 6 }}>Run the screener to find opportunities</div>
          <div style={{ color: T.text2, fontSize: 13 }}>Adjust filters above and click "Run Screener"</div>
        </div>
      )}

      {/* Save preset modal */}
      {saveModalOpen && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200,
          backdropFilter: "blur(4px)",
        }}>
          <div className="animate-in" style={{
            background: T.surface2, border: `1px solid ${T.borderBright}`,
            borderRadius: 14, padding: "1.5rem", width: 380,
            boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
          }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 16 }}>
              Save screener preset
            </div>
            <input
              value={presetName}
              onChange={e => setPresetName(e.target.value)}
              placeholder="Preset name, e.g. Large cap dips"
              style={{
                width: "100%", padding: "8px 11px", fontSize: 13,
                border: `1px solid ${T.border}`, borderRadius: 7,
                background: T.surface, color: T.text, outline: "none",
                marginBottom: 12, boxSizing: "border-box", caretColor: T.blue,
              }}
            />
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: T.text2, marginBottom: 18, cursor: "pointer" }}>
              <input type="checkbox" checked={autoMonitor} onChange={e => setAutoMonitor(e.target.checked)}
                style={{ accentColor: T.blue }} />
              Auto-monitor (runs every 15 minutes)
            </label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                onClick={() => setSaveModalOpen(false)}
                style={{
                  padding: "7px 16px", fontSize: 13, border: `1px solid ${T.border}`,
                  borderRadius: 7, background: "transparent", cursor: "pointer", color: T.text2,
                }}
              >Cancel</button>
              <button
                onClick={handleSavePreset}
                style={{
                  padding: "7px 16px", fontSize: 13, border: "none",
                  borderRadius: 7, background: T.blue, color: "#fff", cursor: "pointer",
                  fontWeight: 500,
                }}
              >Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
