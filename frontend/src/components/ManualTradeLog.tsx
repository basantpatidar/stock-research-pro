import { useState } from "react"
import { T } from "../theme"

const STORAGE_KEY = "srp_manual_trades"
const TARGET_KEY  = "dts_weekly_target"
const DEFAULT_TARGET = 150

interface TradeEntry {
  id: string
  ticker: string
  pnl: number        // positive = win, negative = loss
  note: string
  timestamp: string
  week: string       // "2026-W19" — used to filter to current week
}

function currentWeekKey(): string {
  const now = new Date()
  const jan1 = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now.getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7)
  return `${now.getFullYear()}-W${week}`
}

function loadTrades(): TradeEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveTrades(entries: TradeEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  if (isToday) return formatTime(iso)
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + formatTime(iso)
}

export function ManualTradeLog() {
  const [trades, setTrades]       = useState<TradeEntry[]>(() => loadTrades())
  const [showForm, setShowForm]   = useState(false)
  const [ticker, setTicker]       = useState("")
  const [pnlInput, setPnlInput]   = useState("")
  const [note, setNote]           = useState("")
  const [showAll, setShowAll]     = useState(false)

  const weekKey = currentWeekKey()
  const target = parseFloat(localStorage.getItem(TARGET_KEY) || String(DEFAULT_TARGET))

  const thisWeek = trades.filter(t => t.week === weekKey)
  const total    = thisWeek.reduce((s, t) => s + t.pnl, 0)
  const wins     = thisWeek.filter(t => t.pnl > 0).length
  const losses   = thisWeek.filter(t => t.pnl < 0).length
  const pct      = target > 0 ? Math.min((total / target) * 100, 100) : 0
  const targetHit = total >= target
  const barColor  = targetHit ? T.green : total > 0 ? T.blue : total < 0 ? T.red : T.text3

  const addTrade = () => {
    const pnl = parseFloat(pnlInput)
    if (isNaN(pnl) || pnl === 0) return
    const entry: TradeEntry = {
      id: `${Date.now()}`,
      ticker: ticker.toUpperCase().trim() || "—",
      pnl,
      note: note.trim(),
      timestamp: new Date().toISOString(),
      week: weekKey,
    }
    const updated = [entry, ...trades]
    saveTrades(updated)
    setTrades(updated)
    setTicker("")
    setPnlInput("")
    setNote("")
    setShowForm(false)
  }

  const remove = (id: string) => {
    const updated = trades.filter(t => t.id !== id)
    saveTrades(updated)
    setTrades(updated)
  }

  const displayed = showAll ? thisWeek : thisWeek.slice(0, 5)

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${targetHit ? T.green + "66" : T.border}`,
      borderRadius: 10,
      padding: "12px 16px",
      marginBottom: 16,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", whiteSpace: "nowrap" }}>
          Actual Trades
        </div>

        {/* Progress bar */}
        <div style={{ flex: 1, minWidth: 100, height: 8, background: T.surface2, borderRadius: 4, overflow: "hidden" }}>
          <div style={{
            width: `${Math.max(pct, 0)}%`,
            height: "100%", background: barColor,
            borderRadius: 4, transition: "width 0.4s ease",
          }} />
        </div>

        {/* Total */}
        <div style={{ fontFamily: T.mono, fontWeight: 700, fontSize: 14, color: barColor, whiteSpace: "nowrap" }}>
          {total >= 0 ? "+" : ""}${total.toFixed(2)}
        </div>

        <div style={{ fontSize: 11, color: T.text3 }}>
          of <span style={{ color: T.text2 }}>${target}</span>
        </div>

        {thisWeek.length > 0 && (
          <div style={{ fontSize: 11, color: T.text3, whiteSpace: "nowrap" }}>{wins}W / {losses}L</div>
        )}

        {targetHit && (
          <div style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px",
            background: "rgba(16,185,129,0.15)", color: T.green,
            border: `1px solid rgba(16,185,129,0.3)`, borderRadius: 4,
          }}>TARGET HIT</div>
        )}

        <button
          onClick={() => { setShowForm(f => !f); setTicker(""); setPnlInput(""); setNote("") }}
          style={{
            fontSize: 11, padding: "4px 10px", marginLeft: "auto",
            background: showForm ? T.surface2 : T.blue,
            color: showForm ? T.text2 : "#fff",
            border: `1px solid ${showForm ? T.border : T.blue}`,
            borderRadius: 5, cursor: "pointer", whiteSpace: "nowrap",
          }}
        >
          {showForm ? "Cancel" : "+ Log Trade"}
        </button>
      </div>

      {/* Log form */}
      {showForm && (
        <div style={{
          display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap",
          background: T.surface2, border: `1px solid ${T.border}`,
          borderRadius: 8, padding: "10px 12px", marginBottom: 10,
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <label style={{ fontSize: 10, color: T.text3 }}>Ticker</label>
            <input
              value={ticker}
              onChange={e => setTicker(e.target.value)}
              placeholder="SPY"
              maxLength={6}
              style={{
                width: 60, fontSize: 13, fontFamily: T.mono, fontWeight: 600,
                background: T.surface, border: `1px solid ${T.border}`,
                color: T.text, borderRadius: 5, padding: "5px 7px", outline: "none",
              }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <label style={{ fontSize: 10, color: T.text3 }}>P&L $ (+ win / − loss)</label>
            <input
              value={pnlInput}
              onChange={e => setPnlInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addTrade()}
              placeholder="+12.40 or -5.00"
              type="number"
              style={{
                width: 120, fontSize: 13, fontFamily: T.mono,
                background: T.surface, border: `1px solid ${T.border}`,
                color: T.text, borderRadius: 5, padding: "5px 7px", outline: "none",
              }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1, minWidth: 100 }}>
            <label style={{ fontSize: 10, color: T.text3 }}>Note (optional)</label>
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addTrade()}
              placeholder="e.g. took half position"
              style={{
                fontSize: 12, background: T.surface, border: `1px solid ${T.border}`,
                color: T.text, borderRadius: 5, padding: "5px 7px", outline: "none", width: "100%",
              }}
            />
          </div>
          <button
            onClick={addTrade}
            disabled={!pnlInput || isNaN(parseFloat(pnlInput))}
            style={{
              fontSize: 12, fontWeight: 600, padding: "6px 14px",
              background: pnlInput && !isNaN(parseFloat(pnlInput)) ? T.green : T.surface2,
              color: pnlInput && !isNaN(parseFloat(pnlInput)) ? "#000" : T.text3,
              border: "none", borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap",
            }}
          >
            Add
          </button>
        </div>
      )}

      {/* Trade list */}
      {thisWeek.length === 0 ? (
        <div style={{ fontSize: 11, color: T.text3, textAlign: "center", padding: "6px 0" }}>
          No trades logged this week — hit "+ Log Trade" after each actual trade
        </div>
      ) : (
        <>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {displayed.map(t => {
              const won = t.pnl > 0
              const c   = won ? T.green : T.red
              return (
                <div key={t.id} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "5px 0", borderBottom: `1px solid ${T.border}`,
                  fontSize: 12,
                }}>
                  <span style={{ color: c, width: 12, flexShrink: 0 }}>{won ? "✓" : "✗"}</span>
                  <span style={{ fontFamily: T.mono, fontWeight: 600, color: T.blue, width: 38 }}>{t.ticker}</span>
                  <span style={{ fontFamily: T.mono, fontWeight: 700, color: c, width: 64 }}>
                    {won ? "+" : ""}${t.pnl.toFixed(2)}
                  </span>
                  {t.note && (
                    <span style={{ fontSize: 11, color: T.text3, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.note}
                    </span>
                  )}
                  <span style={{ fontSize: 10, color: T.text3, marginLeft: "auto", whiteSpace: "nowrap" }}>
                    {formatDate(t.timestamp)}
                  </span>
                  <button
                    onClick={() => remove(t.id)}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: T.text3, fontSize: 14, padding: "0 2px", lineHeight: 1,
                      flexShrink: 0,
                    }}
                    title="Remove"
                  >×</button>
                </div>
              )
            })}
          </div>

          {thisWeek.length > 5 && (
            <button
              onClick={() => setShowAll(a => !a)}
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 11, color: T.text3, marginTop: 6, padding: 0,
              }}
            >
              {showAll ? "Show less ▲" : `Show all ${thisWeek.length} trades ▼`}
            </button>
          )}
        </>
      )}
    </div>
  )
}
