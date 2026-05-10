import { useState } from "react"
import { useWatchlist } from "../hooks/useWatchlist"
import { useStore } from "../store"
import { SignalTag } from "../components/shared/SignalTag"
import { GapScannerCard } from "../components/research/GapScannerCard"
import { T, scoreStyle } from "../theme"

type Filter = "all" | "buy" | "sell"
type ViewMode = "table" | "heatmap"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>{children}</div>
)

function HeatmapView({ items }: { items: any[] }) {
  if (!items.length) return <div style={{ padding: "2rem", textAlign: "center", color: T.text3, fontSize: 13 }}>Watchlist is empty.</div>
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px,1fr))", gap: 8, padding: "16px 0" }}>
      {items.map(item => {
        const chg = item.last_score ? ((item.last_score - 50) / 50) : 0
        const pct = item.last_price ? chg * 5 : 0
        const isPos = pct >= 0
        const intensity = Math.min(Math.abs(pct) / 10, 1)
        const bg = isPos
          ? `rgba(16,185,129,${0.08 + intensity * 0.25})`
          : `rgba(239,68,68,${0.08 + intensity * 0.25})`
        const border = isPos
          ? `rgba(16,185,129,${0.3 + intensity * 0.5})`
          : `rgba(239,68,68,${0.3 + intensity * 0.5})`
        const textColor = isPos ? T.green : T.red
        const score = item.last_score
        return (
          <div key={item.ticker} style={{
            background: bg, border: `1px solid ${border}`, borderRadius: 10,
            padding: "12px 13px", textAlign: "center",
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: T.mono, color: textColor, marginBottom: 3 }}>
              {item.ticker}
            </div>
            {item.last_price && (
              <div style={{ fontSize: 12, fontFamily: T.mono, color: T.text, marginBottom: 3 }}>
                ${item.last_price.toFixed(2)}
              </div>
            )}
            {score != null && (
              <div style={{ fontSize: 11, color: textColor, fontFamily: T.mono }}>
                score: {score}
              </div>
            )}
            {item.last_signal && (
              <div style={{ fontSize: 9, color: textColor, marginTop: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                {item.last_signal}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function WatchlistPage() {
  const { watchlist, addTicker, removeTicker, refresh } = useWatchlist()
  const { alerts } = useStore()
  const [newTicker, setNewTicker] = useState("")
  const [addError, setAddError] = useState("")
  const [filter, setFilter] = useState<Filter>("all")
  const [viewMode, setViewMode] = useState<ViewMode>("table")

  const handleAdd = async () => {
    if (!newTicker.trim()) return
    const result = await addTicker(newTicker.trim())
    if (result.success) { setNewTicker(""); setAddError("") }
    else setAddError(result.error || "Failed to add")
  }

  const filtered = watchlist.filter(item => {
    if (filter === "buy")  return item.last_signal?.toLowerCase().includes("buy")
    if (filter === "sell") return item.last_signal?.toLowerCase().includes("sell") || item.last_signal?.toLowerCase().includes("avoid")
    return true
  })

  const tickers = watchlist.map(item => item.ticker)

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      <GapScannerCard tickers={tickers} />

      {/* Live alerts */}
      {alerts.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <Label>Live Alerts</Label>
          {alerts.slice(0, 3).map((alert) => (
            <div key={alert.id} style={{
              borderLeft: `3px solid ${alert.type.includes("buy") ? T.green : T.amber}`,
              background: alert.type.includes("buy") ? T.greenDim : T.amberDim,
              border: `1px solid ${alert.type.includes("buy") ? T.green : T.amber}`,
              borderRadius: 8, padding: "10px 14px", marginBottom: 8,
            }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: T.text }}>{alert.title}</div>
              <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>{alert.body}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div style={{
        display: "flex", borderBottom: `1px solid ${T.border}`,
        marginBottom: 16, gap: 0, alignItems: "center",
      }}>
        {(["all", "buy", "sell"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "7px 18px", fontSize: 13, border: "none", background: "transparent",
              cursor: "pointer", marginBottom: -1,
              borderBottom: filter === f ? `2px solid ${T.blue}` : "2px solid transparent",
              fontWeight: filter === f ? 500 : 400,
              color: filter === f ? T.text : T.text2,
              transition: "all 0.12s ease",
            }}
          >
            {f === "all" ? "All stocks" : f === "buy" ? "Buy signals" : "Sell signals"}
            {f === "all" && watchlist.length > 0 && (
              <span style={{
                marginLeft: 6, background: T.surface2, color: T.text2,
                borderRadius: 20, fontSize: 10, padding: "1px 6px", fontFamily: T.mono,
              }}>{watchlist.length}</span>
            )}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          {(["table", "heatmap"] as ViewMode[]).map(v => (
            <button
              key={v}
              onClick={() => setViewMode(v)}
              style={{
                fontSize: 11, color: viewMode === v ? T.text : T.text2,
                background: viewMode === v ? T.surface2 : "none",
                border: `1px solid ${viewMode === v ? T.borderBright : T.border}`,
                cursor: "pointer", borderRadius: 5, padding: "3px 10px",
                transition: "all 0.12s ease",
              }}
            >
              {v === "table" ? "≡ Table" : "▦ Heatmap"}
            </button>
          ))}
          <button
            onClick={refresh}
            style={{
              fontSize: 12, color: T.text2, background: "none",
              border: `1px solid ${T.border}`, cursor: "pointer", borderRadius: 6,
              padding: "4px 12px", transition: "all 0.12s ease",
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Heatmap view */}
      {viewMode === "heatmap" && <HeatmapView items={filtered} />}

      {/* Table */}
      {viewMode === "table" &&
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 16 }}>
        {/* Header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "10px 70px 1fr 90px 80px 80px 120px 34px",
          gap: 10, padding: "9px 16px",
          borderBottom: `1px solid ${T.border}`,
          background: T.surface2,
        }}>
          {["", "Ticker", "Company", "Price", "Score", "7d", "Signal", ""].map((h, i) => (
            <span key={i} style={{ fontSize: 10, color: T.text3, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {h}
            </span>
          ))}
        </div>

        {filtered.length === 0 && (
          <div style={{ padding: "2.5rem", textAlign: "center", color: T.text3, fontSize: 13 }}>
            {watchlist.length === 0
              ? "Watchlist is empty. Add a ticker below."
              : "No stocks match this filter."}
          </div>
        )}

        {filtered.map((item, idx) => {
          const hasAlert = alerts.some(a => a.ticker === item.ticker)
          const sc = item.last_score ? scoreStyle(item.last_score) : null
          return (
            <div
              key={item.ticker}
              style={{
                display: "grid",
                gridTemplateColumns: "10px 70px 1fr 90px 80px 80px 120px 34px",
                gap: 10, padding: "10px 16px",
                borderBottom: idx < filtered.length - 1 ? `1px solid ${T.border}` : "none",
                alignItems: "center",
                transition: "background 0.1s ease",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = T.surfaceHover)}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              {/* Status dot */}
              <div style={{ position: "relative", width: 8, height: 8 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: hasAlert ? T.red : sc ? sc.text : T.text3,
                }} />
                {hasAlert && (
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: T.red, position: "absolute", top: 0, left: 0,
                    animation: "pulse-ring 1.5s ease-out infinite",
                  }} />
                )}
              </div>

              <span style={{ fontSize: 13, fontWeight: 600, fontFamily: T.mono, color: T.text }}>{item.ticker}</span>
              <span style={{ fontSize: 12, color: T.text2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.company_name || "—"}
              </span>
              <span style={{ fontSize: 13, fontFamily: T.mono, color: T.text }}>
                {item.last_price ? `$${item.last_price.toFixed(2)}` : "—"}
              </span>

              {/* Score with mini bar */}
              <div>
                {item.last_score ? (
                  <div>
                    <div style={{ fontSize: 12, fontFamily: T.mono, fontWeight: 600, color: sc!.text, marginBottom: 3 }}>
                      {item.last_score}<span style={{ fontSize: 10, color: T.text3 }}>/100</span>
                    </div>
                    <div style={{ height: 3, background: T.border, borderRadius: 2, overflow: "hidden" }}>
                      <div style={{
                        width: `${item.last_score}%`, height: "100%",
                        background: sc!.text, borderRadius: 2,
                      }} />
                    </div>
                  </div>
                ) : <span style={{ fontSize: 12, color: T.text3 }}>—</span>}
              </div>

              <span style={{ fontSize: 12, color: T.text3, fontFamily: T.mono }}>—</span>

              <div>
                {item.last_signal
                  ? <SignalTag signal={item.last_signal} size="sm" />
                  : <span style={{ fontSize: 11, color: T.text3 }}>Pending…</span>}
              </div>

              <button
                onClick={() => removeTicker(item.ticker)}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: T.text3, fontSize: 18, lineHeight: 1, padding: "0 2px",
                  transition: "color 0.12s ease",
                }}
                onMouseEnter={e => (e.currentTarget.style.color = T.red)}
                onMouseLeave={e => (e.currentTarget.style.color = T.text3)}
              >×</button>
            </div>
          )
        })}

        {/* Add row */}
        <div style={{
          padding: "10px 16px", borderTop: `1px solid ${T.border}`,
          display: "flex", gap: 8, background: T.surface2,
        }}>
          <div style={{
            flex: 1, display: "flex", alignItems: "center",
            background: T.surface, border: `1px solid ${T.border}`, borderRadius: 7,
            padding: "0 10px",
          }}>
            <span style={{ color: T.text3, fontFamily: T.mono, fontSize: 13, marginRight: 7 }}>+</span>
            <input
              value={newTicker}
              onChange={e => { setNewTicker(e.target.value.toUpperCase()); setAddError("") }}
              onKeyDown={e => e.key === "Enter" && handleAdd()}
              placeholder="Add ticker… META, TSLA"
              style={{
                flex: 1, background: "transparent", border: "none", outline: "none",
                color: T.text, fontSize: 13, fontFamily: T.mono, padding: "7px 0", caretColor: T.blue,
              }}
            />
          </div>
          <button
            onClick={handleAdd}
            style={{
              padding: "7px 16px", fontSize: 13, fontWeight: 500, border: "none",
              borderRadius: 7, background: T.blue, color: "#fff", cursor: "pointer",
            }}
          >
            Add
          </button>
        </div>
        {addError && (
          <div style={{ padding: "4px 16px 10px", fontSize: 12, color: T.red }}>{addError}</div>
        )}
      </div>}

      <div style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>
        Signals refresh every 5 min · Score 0–100 convergence across technical + fundamental signals
      </div>
    </div>
  )
}
