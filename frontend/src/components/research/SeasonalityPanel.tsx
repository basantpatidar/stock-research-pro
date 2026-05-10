import type { SeasonalityData, MonthData } from "../../types"
import { T } from "../../theme"

interface Props {
  data: SeasonalityData
}

function heatColor(avg: number | null): string {
  if (avg === null) return T.surface2
  if (avg >= 4)   return "#22cc6640"
  if (avg >= 2)   return "#22cc6625"
  if (avg >= 0.5) return "#22cc6612"
  if (avg >= -0.5) return "#ffffff08"
  if (avg >= -2)   return "#ff444415"
  if (avg >= -4)   return "#ff444428"
  return "#ff444440"
}

function textColor(avg: number | null): string {
  if (avg === null) return T.text3
  if (avg > 0.5)  return T.green
  if (avg < -0.5) return T.red
  return T.text2
}

function MonthCell({ m, isCurrent }: { m: MonthData; isCurrent: boolean }) {
  const winRate = m.total_years > 0 ? Math.round((m.positive_years / m.total_years) * 100) : null
  const avg = m.avg_return

  return (
    <div
      title={avg != null
        ? `Best: +${m.best_return}%  Worst: ${m.worst_return}%`
        : "No data"}
      style={{
        background: heatColor(avg),
        border: isCurrent
          ? `1.5px solid ${T.blue}`
          : `1px solid ${T.border}`,
        borderRadius: 8,
        padding: "8px 6px",
        textAlign: "center",
        position: "relative",
      }}
    >
      {isCurrent && (
        <div style={{
          position: "absolute", top: -7, left: "50%", transform: "translateX(-50%)",
          fontSize: 8, fontFamily: T.mono, color: T.blue,
          background: T.surface, padding: "0 4px", letterSpacing: "0.05em",
        }}>
          NOW
        </div>
      )}
      <div style={{ fontSize: 11, fontWeight: 600, color: T.text2, marginBottom: 4 }}>
        {m.month}
      </div>
      {avg != null ? (
        <>
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: T.mono, color: textColor(avg) }}>
            {avg >= 0 ? "+" : ""}{avg.toFixed(1)}%
          </div>
          <div style={{ fontSize: 10, color: T.text3, marginTop: 2, fontFamily: T.mono }}>
            {m.positive_years}/{m.total_years} yrs
          </div>
          {winRate !== null && (
            <div style={{
              fontSize: 9, marginTop: 3, fontFamily: T.mono,
              color: winRate >= 60 ? T.green : winRate <= 40 ? T.red : T.text3,
            }}>
              {winRate}% win
            </div>
          )}
        </>
      ) : (
        <div style={{ fontSize: 11, color: T.text3 }}>N/A</div>
      )}
    </div>
  )
}

export function SeasonalityPanel({ data }: Props) {
  const best  = data.best_month
  const worst = data.worst_month

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Summary row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 11, color: T.text3 }}>
          {data.years_of_data}y of data · {data.ticker}
        </span>
        {best && (
          <span style={{ fontSize: 11, fontFamily: T.mono, color: T.green }}>
            Best: {best.month} avg {best.avg_return! >= 0 ? "+" : ""}{best.avg_return!.toFixed(1)}%
          </span>
        )}
        {worst && (
          <span style={{ fontSize: 11, fontFamily: T.mono, color: T.red }}>
            Worst: {worst.month} avg {worst.avg_return!.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Monthly heatmap grid — 4 cols × 3 rows */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
        {data.months.map(m => (
          <MonthCell
            key={m.month_num}
            m={m}
            isCurrent={m.month_num === data.current_month}
          />
        ))}
      </div>

      <div style={{ fontSize: 10, color: T.text3 }}>
        Avg monthly return over {data.years_of_data} years. Hover for best/worst year. Current month highlighted in blue.
      </div>
    </div>
  )
}
