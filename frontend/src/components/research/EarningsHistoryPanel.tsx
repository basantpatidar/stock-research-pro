import { useState } from "react"
import { T } from "../../theme"

interface EarningsEntry {
  date: string
  eps_estimate: number | null
  eps_actual: number | null
  surprise: number | null
  surprise_pct: number | null
  beat: boolean | null
  revenue_actual: number | null
}

interface Props {
  earnings: {
    next_earnings_date: string | null
    earnings_history: EarningsEntry[]
    beat_count: number
    miss_count: number
    beat_rate_pct: number | null
  }
}


function fmtEps(val: number | null): string {
  if (val == null) return "—"
  const abs = Math.abs(val).toFixed(2)
  return val >= 0 ? `$${abs}` : `-$${abs}`
}

function fmtSurpriseDollar(val: number | null): string {
  if (val == null) return "—"
  const abs = Math.abs(val).toFixed(2)
  return `${val >= 0 ? "+" : "-"}$${abs}`
}

function fmtSurprisePct(val: number | null): string {
  if (val == null) return "—"
  return `${val >= 0 ? "+" : ""}${val.toFixed(1)}%`
}

function fmtRevenue(val: number | null): string {
  if (val == null) return "—"
  if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`
  return `$${val.toFixed(0)}`
}

function relativeLabel(idx: number): string {
  if (idx === 0) return "Latest"
  if (idx === 1) return "1 qtr ago"
  return `${idx} qtrs ago`
}

function isDatePast(dateStr: string | null): boolean {
  if (!dateStr) return false
  return new Date(dateStr.slice(0, 10)) < new Date(new Date().toISOString().slice(0, 10))
}

export function EarningsHistoryPanel({ earnings }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  // Sort newest-first so index 0 = most recent quarter
  const rows = [...earnings.earnings_history]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 5)
  const total = earnings.beat_count + earnings.miss_count
  const nextDatePast = isDatePast(earnings.next_earnings_date)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

      {/* ── Summary bar ──────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexWrap: "wrap", gap: 8, paddingBottom: 4,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em" }}>
            Streak
          </span>
          <div style={{ display: "flex", gap: 5 }}>
            {rows.map((e, i) => (
              <div key={i} style={{
                width: 11, height: 11, borderRadius: "50%", flexShrink: 0,
                background: e.beat === true ? T.green : e.beat === false ? T.red : T.text3,
                boxShadow: e.beat === true
                  ? `0 0 7px ${T.green}90`
                  : e.beat === false
                    ? `0 0 7px ${T.red}90`
                    : "none",
              }} />
            ))}
          </div>
          {total > 0 && (
            <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono }}>
              {earnings.beat_count}/{total} Beats
              {earnings.beat_rate_pct != null && (
                <span style={{
                  marginLeft: 5,
                  color: earnings.beat_rate_pct >= 70 ? T.green
                    : earnings.beat_rate_pct >= 50 ? T.amber
                    : T.red,
                }}>
                  ({earnings.beat_rate_pct.toFixed(0)}%)
                </span>
              )}
            </span>
          )}
        </div>
        {earnings.next_earnings_date && (
          <div style={{
            fontSize: 11, color: T.text2, fontFamily: T.mono,
            padding: "3px 10px", borderRadius: 5,
            background: nextDatePast ? T.surface2 : T.blueDim,
            border: `1px solid ${nextDatePast ? T.border : T.blue}`,
          }}>
            {nextDatePast ? "Reported: " : "Next: "}
            <span style={{ color: nextDatePast ? T.amber : T.blue }}>
              {earnings.next_earnings_date.slice(0, 10)}
            </span>
          </div>
        )}
      </div>

      {/* ── Quarter cards ─────────────────────────────────────────────── */}
      {rows.map((e, i) => {
        const isOpen = expandedIdx === i
        const beatColor = e.beat === true ? T.green : e.beat === false ? T.red : T.text3
        const beatBg    = e.beat === true ? T.greenDim : e.beat === false ? T.redDim : T.surface2
        const beatLabel = e.beat === true ? "BEAT" : e.beat === false ? "MISS" : "—"
        const quarter   = relativeLabel(i)
        const shortDate = e.date.length >= 10 ? e.date.slice(5, 10).replace("-", "/") : e.date

        return (
          <div key={i} style={{
            background: isOpen ? T.surface2 : T.surface,
            border: `1px solid ${isOpen ? T.borderBright : T.border}`,
            borderRadius: 8,
            overflow: "hidden",
            transition: "background 0.15s ease, border-color 0.15s ease",
          }}>

            {/* Collapsed header row */}
            <button
              onClick={() => setExpandedIdx(isOpen ? null : i)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 10,
                padding: "9px 12px", background: "transparent", border: "none",
                cursor: "pointer", textAlign: "left",
              }}
            >
              {/* Quarter badge */}
              <div style={{
                fontSize: 11, fontWeight: 700, fontFamily: T.mono, color: T.text,
                background: T.surface2, border: `1px solid ${T.border}`,
                borderRadius: 5, padding: "2px 8px",
                flexShrink: 0, minWidth: 62, textAlign: "center",
              }}>
                {quarter}
              </div>

              {/* Report date */}
              <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono, flexShrink: 0 }}>
                {shortDate}
              </span>

              <div style={{ flex: 1 }} />

              {/* EPS actual */}
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{ fontSize: 9, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em" }}>EPS</div>
                <div style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 600, color: T.text }}>
                  {fmtEps(e.eps_actual)}
                </div>
              </div>

              {/* Beat / Miss pill */}
              <div style={{
                fontSize: 10, fontWeight: 700, fontFamily: T.mono, letterSpacing: "0.06em",
                color: beatColor, background: beatBg,
                padding: "3px 8px", borderRadius: 5, flexShrink: 0,
              }}>
                {beatLabel}
              </div>

              {/* Surprise pct */}
              {e.surprise_pct != null ? (
                <div style={{
                  fontSize: 12, fontFamily: T.mono, fontWeight: 600,
                  color: beatColor, flexShrink: 0, minWidth: 52, textAlign: "right",
                }}>
                  {fmtSurprisePct(e.surprise_pct)}
                </div>
              ) : (
                <div style={{ minWidth: 52 }} />
              )}

              {/* Chevron */}
              <div style={{
                fontSize: 15, color: T.text3, flexShrink: 0,
                transition: "transform 0.2s ease",
                transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                lineHeight: 1,
              }}>
                ›
              </div>
            </button>

            {/* Expanded detail */}
            {isOpen && (
              <div style={{
                padding: "10px 12px 12px",
                borderTop: `1px solid ${T.border}`,
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 10,
              }}>
                {/* EPS detail card */}
                <div style={{
                  background: T.surface, borderRadius: 7, padding: "10px 12px",
                  border: `1px solid ${T.border}`,
                }}>
                  <div style={{
                    fontSize: 10, color: T.text3, textTransform: "uppercase",
                    letterSpacing: "0.07em", marginBottom: 8, fontWeight: 600,
                  }}>
                    EPS Detail
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {[
                      { label: "Estimate",   val: fmtEps(e.eps_estimate),         color: T.text  },
                      { label: "Actual",     val: fmtEps(e.eps_actual),           color: beatColor },
                      { label: "Surprise",   val: fmtSurpriseDollar(e.surprise),  color: beatColor },
                      { label: "Surprise %", val: fmtSurprisePct(e.surprise_pct), color: beatColor },
                    ].map(({ label, val, color }) => (
                      <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <span style={{ fontSize: 11, color: T.text2 }}>{label}</span>
                        <span style={{ fontSize: 12, fontFamily: T.mono, fontWeight: 500, color }}>{val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Revenue card */}
                <div style={{
                  background: T.surface, borderRadius: 7, padding: "10px 12px",
                  border: `1px solid ${T.border}`,
                }}>
                  <div style={{
                    fontSize: 10, color: T.text3, textTransform: "uppercase",
                    letterSpacing: "0.07em", marginBottom: 8, fontWeight: 600,
                  }}>
                    Revenue
                  </div>
                  {e.revenue_actual != null ? (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <span style={{ fontSize: 11, color: T.text2 }}>Actual</span>
                      <span style={{ fontSize: 14, fontFamily: T.mono, fontWeight: 600, color: T.text }}>
                        {fmtRevenue(e.revenue_actual)}
                      </span>
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: T.text3, paddingTop: 2 }}>Not available</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
