import { useState } from "react"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import type { PriceData } from "../../types"

const PERIODS = ["1d", "7D", "1M", "3M", "1Y"] as const

interface Props {
  data: PriceData
  onPeriodChange?: (period: string) => void
}

export function PriceChart({ data, onPeriodChange }: Props) {
  const [activePeriod, setActivePeriod] = useState("7D")

  const isPositive = data.change_pct_7d >= 0
  const chartColor = isPositive ? "#16a34a" : "#dc2626"

  const handlePeriod = (p: string) => {
    setActivePeriod(p)
    onPeriodChange?.(p)
  }

  const formatDate = (d: string) => {
    const date = new Date(d)
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }

  return (
    <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>Price history</span>
        <div style={{ display: "flex", gap: 4 }}>
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => handlePeriod(p)}
              style={{
                padding: "3px 9px",
                fontSize: 11,
                borderRadius: 20,
                border: activePeriod === p ? "0.5px solid #6b7280" : "0.5px solid #e5e7eb",
                background: activePeriod === p ? "#f3f4f6" : "transparent",
                cursor: "pointer",
                fontWeight: activePeriod === p ? 500 : 400,
                color: activePeriod === p ? "#111" : "#6b7280",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data.price_history} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={chartColor} stopOpacity={0.15} />
              <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            formatter={(val: number) => [`$${val.toFixed(2)}`, "Price"]}
            labelFormatter={(l) => formatDate(l as string)}
            contentStyle={{ fontSize: 12, borderRadius: 6, border: "0.5px solid #e5e7eb" }}
          />
          <Area type="monotone" dataKey="close" stroke={chartColor} strokeWidth={1.5} fill="url(#priceGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
