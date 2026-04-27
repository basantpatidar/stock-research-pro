import { useState } from "react"
import { useWatchlist } from "../hooks/useWatchlist"
import { useStore } from "../store"
import { SignalTag } from "../components/shared/SignalTag"

export function WatchlistPage() {
  const { watchlist, addTicker, removeTicker, refresh } = useWatchlist()
  const { alerts } = useStore()
  const [newTicker, setNewTicker] = useState("")
  const [addError, setAddError] = useState("")
  const [filter, setFilter] = useState<"all" | "buy" | "sell">("all")

  const handleAdd = async () => {
    if (!newTicker.trim()) return
    const result = await addTicker(newTicker.trim())
    if (result.success) {
      setNewTicker("")
      setAddError("")
    } else {
      setAddError(result.error || "Failed to add")
    }
  }

  const filtered = watchlist.filter((item) => {
    if (filter === "buy") return item.last_signal?.toLowerCase().includes("buy")
    if (filter === "sell") return item.last_signal?.toLowerCase().includes("sell") || item.last_signal?.toLowerCase().includes("avoid")
    return true
  })

  const scoreColor = (score: number | null) => {
    if (!score) return "#9ca3af"
    if (score >= 70) return "#16a34a"
    if (score >= 50) return "#d97706"
    return "#dc2626"
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "1.5rem 1rem" }}>

      {/* Active alerts */}
      {alerts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Live alerts
          </div>
          {alerts.slice(0, 3).map((alert) => (
            <div key={alert.id} style={{
              borderLeft: `3px solid ${alert.type.includes("buy") ? "#16a34a" : "#d97706"}`,
              background: alert.type.includes("buy") ? "#f0fdf4" : "#fffbeb",
              borderRadius: 8, padding: "10px 14px", marginBottom: 8,
            }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#111" }}>{alert.title}</div>
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{alert.body}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "0.5px solid #e5e7eb", marginBottom: 16, gap: 0 }}>
        {(["all", "buy", "sell"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "6px 16px", fontSize: 13, border: "none", background: "transparent",
              cursor: "pointer", borderBottom: filter === f ? "2px solid #111" : "2px solid transparent",
              fontWeight: filter === f ? 500 : 400, color: filter === f ? "#111" : "#6b7280",
              marginBottom: -1,
            }}
          >
            {f === "all" ? "All stocks" : f === "buy" ? "Buy signals" : "Sell signals"}
          </button>
        ))}
        <button onClick={refresh} style={{ marginLeft: "auto", fontSize: 12, color: "#6b7280", background: "none", border: "none", cursor: "pointer" }}>
          ↻ Refresh
        </button>
      </div>

      {/* Watchlist table */}
      <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, overflow: "hidden", marginBottom: 16 }}>
        {/* Header */}
        <div style={{ display: "grid", gridTemplateColumns: "8px 60px 1fr 80px 70px 110px 32px", gap: 10, padding: "8px 16px", borderBottom: "0.5px solid #e5e7eb", alignItems: "center" }}>
          {["", "Ticker", "Company", "Price", "7d chg", "Signal", ""].map((h, i) => (
            <span key={i} style={{ fontSize: 11, color: "#9ca3af", fontWeight: 500 }}>{h}</span>
          ))}
        </div>

        {filtered.length === 0 && (
          <div style={{ padding: "2rem", textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
            {watchlist.length === 0 ? "No stocks in watchlist yet. Add one below." : "No stocks match this filter."}
          </div>
        )}

        {filtered.map((item) => {
          const hasAlert = alerts.some((a) => a.ticker === item.ticker)
          return (
            <div
              key={item.ticker}
              style={{
                display: "grid", gridTemplateColumns: "8px 60px 1fr 80px 70px 110px 32px",
                gap: 10, padding: "10px 16px", borderBottom: "0.5px solid #f9fafb",
                alignItems: "center",
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: hasAlert ? "#dc2626" : item.last_score && item.last_score >= 70 ? "#16a34a" : "#e5e7eb" }} />
              <span style={{ fontSize: 13, fontWeight: 500 }}>{item.ticker}</span>
              <span style={{ fontSize: 12, color: "#6b7280", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.company_name || "—"}</span>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{item.last_price ? `$${item.last_price.toFixed(2)}` : "—"}</span>
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                {item.last_score ? <span style={{ color: scoreColor(item.last_score), fontWeight: 500 }}>{item.last_score}/100</span> : "—"}
              </span>
              <div>{item.last_signal ? <SignalTag signal={item.last_signal} size="sm" /> : <span style={{ fontSize: 11, color: "#9ca3af" }}>Pending...</span>}</div>
              <button
                onClick={() => removeTicker(item.ticker)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#d1d5db", fontSize: 16 }}
              >×</button>
            </div>
          )
        })}

        {/* Add row */}
        <div style={{ padding: "10px 16px", borderTop: "0.5px solid #f3f4f6", display: "flex", gap: 8 }}>
          <input
            value={newTicker}
            onChange={(e) => { setNewTicker(e.target.value.toUpperCase()); setAddError("") }}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Add ticker... e.g. META"
            style={{ flex: 1, padding: "6px 10px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, outline: "none" }}
          />
          <button onClick={handleAdd} style={{ padding: "6px 14px", fontSize: 13, border: "0.5px solid #d1d5db", borderRadius: 6, background: "#111", color: "#fff", cursor: "pointer" }}>
            + Add
          </button>
        </div>
        {addError && <div style={{ padding: "4px 16px 8px", fontSize: 12, color: "#dc2626" }}>{addError}</div>}
      </div>

      <div style={{ fontSize: 12, color: "#9ca3af" }}>
        Signals refresh every 5 minutes in the background. Score is 0–100 convergence across technical + fundamental signals.
      </div>
    </div>
  )
}
