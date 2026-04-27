import { useState } from "react"
import { useScreener } from "../hooks/useScreener"
import { useWatchlist } from "../hooks/useWatchlist"

const SECTORS = ["all", "Technology", "Healthcare", "Financials", "Energy", "Consumer Discretionary", "Industrials", "Communication Services"]

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
    setAddedTickers((s) => new Set([...s, ticker]))
  }

  const oppColor = (change: number) => {
    if (change <= -15) return { bg: "#d1fae5", color: "#065f46", label: "Buy now" }
    if (change <= -10) return { bg: "#dcfce7", color: "#14532d", label: "Buy — 1 week" }
    if (change <= -5) return { bg: "#ecfdf5", color: "#166534", label: "Monitor" }
    return { bg: "#f3f4f6", color: "#374151", label: "Neutral" }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "1.5rem 1rem" }}>

      {/* Filters */}
      <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 12 }}>Screener filters</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
          {[
            { label: "Market cap (min)", key: "min_market_cap_b", options: [[100, "$100B+"], [50, "$50B+"], [10, "$10B+"], [1, "$1B+"]] },
            { label: "Daily volume (min)", key: "min_volume", options: [[1_000_000, "1M+ shares"], [500_000, "500K+ shares"], [100_000, "100K+ shares"]] },
            { label: "Price drop trigger (7d)", key: "min_price_drop_pct", options: [[5, "−5%+"], [10, "−10%+"], [15, "−15%+"], [20, "−20%+"]] },
            { label: "Max P/E ratio", key: "max_pe", options: [[0, "Any"], [20, "Under 20x"], [30, "Under 30x"], [50, "Under 50x"]] },
          ].map(({ label, key, options }) => (
            <div key={key} style={{ background: "#f9fafb", borderRadius: 8, padding: "10px 12px" }}>
              <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>{label}</div>
              <select
                value={(filters as any)[key]}
                onChange={(e) => setFilters({ ...filters, [key]: Number(e.target.value) })}
                style={{ width: "100%", padding: "5px 8px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, background: "#fff" }}
              >
                {options.map(([val, lbl]) => (
                  <option key={val} value={val}>{lbl}</option>
                ))}
              </select>
            </div>
          ))}
          <div style={{ background: "#f9fafb", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>Sector</div>
            <select
              value={filters.sector}
              onChange={(e) => setFilters({ ...filters, sector: e.target.value })}
              style={{ width: "100%", padding: "5px 8px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, background: "#fff" }}
            >
              {SECTORS.map((s) => <option key={s} value={s}>{s === "all" ? "All sectors" : s}</option>)}
            </select>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => runScreener()}
            disabled={loading}
            style={{ padding: "7px 20px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 8, background: loading ? "#f3f4f6" : "#111", color: loading ? "#9ca3af" : "#fff", cursor: loading ? "not-allowed" : "pointer" }}
          >
            {loading ? "Scanning..." : "Run screener"}
          </button>
          <button
            onClick={() => setSaveModalOpen(true)}
            style={{ padding: "7px 14px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 8, background: "transparent", cursor: "pointer", color: "#374151" }}
          >
            Save preset
          </button>
          <button
            onClick={fetchPresets}
            style={{ padding: "7px 14px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 8, background: "transparent", cursor: "pointer", color: "#374151" }}
          >
            Load preset
          </button>
        </div>
      </div>

      {error && <div style={{ background: "#fee2e2", color: "#991b1b", borderRadius: 8, padding: "10px 14px", fontSize: 13, marginBottom: 12 }}>{error}</div>}

      {/* Results */}
      {results.length > 0 && (
        <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #e5e7eb", fontSize: 13 }}>
            <strong>{results.length}</strong> stocks match your filters
          </div>

          {/* Header */}
          <div style={{ display: "grid", gridTemplateColumns: "56px 1fr 70px 70px 60px 100px 100px", gap: 10, padding: "8px 16px", borderBottom: "0.5px solid #e5e7eb" }}>
            {["Ticker", "Company", "Mkt cap", "Volume", "7d chg", "Opportunity", ""].map((h, i) => (
              <span key={i} style={{ fontSize: 11, color: "#9ca3af", fontWeight: 500 }}>{h}</span>
            ))}
          </div>

          {results.map((r) => {
            const opp = oppColor(r.change_7d_pct)
            const added = addedTickers.has(r.ticker)
            return (
              <div key={r.ticker} style={{ display: "grid", gridTemplateColumns: "56px 1fr 70px 70px 60px 100px 100px", gap: 10, padding: "10px 16px", borderBottom: "0.5px solid #f9fafb", alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{r.ticker}</span>
                <span style={{ fontSize: 12, color: "#6b7280", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.company}</span>
                <span style={{ fontSize: 12, color: "#6b7280" }}>${r.market_cap_b}B</span>
                <span style={{ fontSize: 12, color: "#6b7280" }}>{(r.avg_volume / 1_000_000).toFixed(1)}M</span>
                <span style={{ fontSize: 12, color: "#dc2626", fontWeight: 500 }}>{r.change_7d_pct.toFixed(1)}%</span>
                <span style={{ display: "inline-block", fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 20, background: opp.bg, color: opp.color }}>{opp.label}</span>
                <button
                  onClick={() => handleAddToWatchlist(r.ticker)}
                  disabled={added}
                  style={{ fontSize: 11, padding: "3px 10px", border: "0.5px solid #d1d5db", borderRadius: 6, background: added ? "#f3f4f6" : "transparent", cursor: added ? "default" : "pointer", color: added ? "#9ca3af" : "#374151" }}
                >
                  {added ? "Added ✓" : "+ Watchlist"}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {results.length === 0 && !loading && (
        <div style={{ background: "#f9fafb", borderRadius: 12, padding: "2rem", textAlign: "center", color: "#9ca3af", fontSize: 14 }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>🔍</div>
          <div>Run the screener to find opportunities matching your filters</div>
        </div>
      )}

      {/* Save preset modal */}
      {saveModalOpen && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: "1.5rem", width: 360 }}>
            <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 14 }}>Save screener preset</div>
            <input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="Preset name, e.g. Large cap dips"
              style={{ width: "100%", padding: "8px 10px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, marginBottom: 10, boxSizing: "border-box" }}
            />
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#374151", marginBottom: 14, cursor: "pointer" }}>
              <input type="checkbox" checked={autoMonitor} onChange={(e) => setAutoMonitor(e.target.checked)} />
              Auto-monitor (runs every 15 minutes in background)
            </label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setSaveModalOpen(false)} style={{ padding: "7px 14px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, background: "transparent", cursor: "pointer" }}>Cancel</button>
              <button onClick={handleSavePreset} style={{ padding: "7px 14px", fontSize: 13, border: "none", borderRadius: 6, background: "#111", color: "#fff", cursor: "pointer" }}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
