import { useState, useMemo } from "react"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
import type { PriceData } from "../../types"
import { T } from "../../theme"

const PERIODS = ["1d", "1W", "1M", "3M", "6M", "1Y"] as const
type Period = typeof PERIODS[number]

// Days of daily-candle history to show per period (unused for 1d which uses intraday)
const PERIOD_DAYS: Record<Exclude<Period, "1d">, number> = {
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
}

interface Props {
  data: PriceData
}

const CustomTooltip = ({ active, payload, label, intraday }: any) => {
  if (!active || !payload?.length) return null
  const d = new Date(label)
  const dateLabel = intraday
    ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
  return (
    <div style={{
      background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: "8px 12px", fontSize: 12,
    }}>
      <div style={{ color: T.text2, marginBottom: 3, fontFamily: T.mono }}>{dateLabel}</div>
      <div style={{ color: T.text, fontFamily: T.mono, fontWeight: 500 }}>
        ${Number(payload[0].value).toFixed(2)}
      </div>
    </div>
  )
}

export function PriceChart({ data }: Props) {
  const [activePeriod, setActivePeriod] = useState<Period>("1d")
  const isPositive = data.change_pct_7d >= 0
  const lineColor = isPositive ? T.green : T.red
  const gradId = `pg-${isPositive ? "g" : "r"}`
  const isIntraday = activePeriod === "1d"

  const chartData = useMemo(() => {
    if (isIntraday) return data.intraday_history ?? []
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - PERIOD_DAYS[activePeriod as Exclude<Period, "1d">])
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return (data.price_history ?? []).filter(p => p.date >= cutoffStr)
  }, [data.price_history, data.intraday_history, activePeriod, isIntraday])

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Price History
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setActivePeriod(p)}
              style={{
                padding: "3px 10px", fontSize: 11, borderRadius: 20, cursor: "pointer",
                border: `1px solid ${activePeriod === p ? T.blue : T.border}`,
                background: activePeriod === p ? T.blueDim : "transparent",
                fontWeight: activePeriod === p ? 500 : 400,
                color: activePeriod === p ? T.blue : T.text2,
                fontFamily: T.mono,
                transition: "all 0.12s ease",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={lineColor} stopOpacity={0.2} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => isIntraday
              ? new Date(d).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
              : new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" })
            }
            tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip content={<CustomTooltip intraday={isIntraday} />} />
          <Area
            type="monotone" dataKey="close"
            stroke={lineColor} strokeWidth={1.5}
            fill={`url(#${gradId})`} dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
