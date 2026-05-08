import { useState, useEffect } from "react"
import { api } from "../services/api"
import { T } from "../theme"

const STORAGE_KEY = "dts_weekly_target"
const DEFAULT_TARGET = 150

interface WeeklyData {
  week_start: string
  total_pnl_dollar: number
  wins: number
  losses: number
  trade_count: number
  by_day: Record<string, number>
}

export function WeeklyTargetBar() {
  const [target, setTarget] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? parseFloat(saved) : DEFAULT_TARGET
  })
  const [editing, setEditing] = useState(false)
  const [data, setData] = useState<WeeklyData | null>(null)

  useEffect(() => {
    api.get("/dip-scanner/weekly")
      .then(res => setData(res.data))
      .catch(() => {})
  }, [])

  const handleTargetChange = (val: number) => {
    setTarget(val)
    localStorage.setItem(STORAGE_KEY, String(val))
  }

  const pnl = data?.total_pnl_dollar ?? 0
  const pct = target > 0 ? Math.min((pnl / target) * 100, 100) : 0
  const targetHit = pnl >= target
  const barColor = targetHit ? T.green : pnl > 0 ? T.blue : pnl < 0 ? T.red : T.text3
  const trades = data?.trade_count ?? 0
  const wins = data?.wins ?? 0

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${targetHit ? T.green : T.border}`,
      borderRadius: 10,
      padding: "12px 16px",
      marginBottom: 16,
      transition: "border-color 0.2s",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        {/* Label */}
        <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", whiteSpace: "nowrap" }}>
          Week Target
        </div>

        {/* Progress bar */}
        <div style={{ flex: 1, minWidth: 120, height: 8, background: T.surface2, borderRadius: 4, overflow: "hidden" }}>
          <div style={{
            width: `${Math.max(pct, pnl < 0 ? 0 : 0)}%`,
            height: "100%", background: barColor,
            borderRadius: 4, transition: "width 0.4s ease",
          }} />
        </div>

        {/* P&L */}
        <div style={{ fontFamily: T.mono, fontWeight: 700, fontSize: 14, color: barColor, whiteSpace: "nowrap" }}>
          {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
        </div>

        {/* Target — editable */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: T.text3, whiteSpace: "nowrap" }}>
          <span>of</span>
          {editing ? (
            <input
              autoFocus
              type="number"
              value={target}
              onChange={e => handleTargetChange(parseFloat(e.target.value) || DEFAULT_TARGET)}
              onBlur={() => setEditing(false)}
              onKeyDown={e => e.key === "Enter" && setEditing(false)}
              style={{
                width: 60, fontSize: 12, fontFamily: T.mono,
                background: T.surface2, border: `1px solid ${T.borderBright}`,
                color: T.text, borderRadius: 4, padding: "1px 5px", outline: "none",
              }}
            />
          ) : (
            <span
              onClick={() => setEditing(true)}
              style={{ cursor: "pointer", color: T.text2, borderBottom: `1px dashed ${T.text3}` }}
            >
              ${target}
            </span>
          )}
        </div>

        {/* Trade count */}
        {trades > 0 && (
          <div style={{ fontSize: 11, color: T.text3, whiteSpace: "nowrap" }}>
            {wins}W/{trades - wins}L
          </div>
        )}

        {/* Target hit badge */}
        {targetHit && (
          <div style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px",
            background: "rgba(16,185,129,0.15)", color: T.green,
            border: `1px solid rgba(16,185,129,0.3)`, borderRadius: 4,
            whiteSpace: "nowrap",
          }}>
            TARGET HIT
          </div>
        )}
      </div>

      {/* Day-by-day breakdown */}
      {data && Object.keys(data.by_day).length > 0 && (
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          {days.map(day => {
            const val = data.by_day[day]
            if (val === undefined) return null
            const c = val > 0 ? T.green : val < 0 ? T.red : T.text3
            return (
              <div key={day} style={{ textAlign: "center", flex: 1 }}>
                <div style={{ fontSize: 9, color: T.text3, marginBottom: 2 }}>{day}</div>
                <div style={{ fontSize: 11, fontFamily: T.mono, fontWeight: 600, color: c }}>
                  {val >= 0 ? "+" : ""}${val.toFixed(0)}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
