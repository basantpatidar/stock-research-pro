import { T } from "../../theme"
import type { EDGARFundamentals, YearValue } from "../../types"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>{children}</div>
)

function Sparkline({ series, color }: { series: YearValue[]; color: string }) {
  if (!series || series.length < 2) return null
  const vals = series.map(e => e.value)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const W = 120, H = 36, pad = 4

  const pts = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (W - pad * 2)
    const y = H - pad - ((v - min) / range) * (H - pad * 2)
    return `${x},${y}`
  }).join(" ")

  const lastVal = vals[vals.length - 1]
  const prevVal = vals[vals.length - 2]
  const lineColor = lastVal >= prevVal ? T.green : T.red

  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinejoin="round" />
      <circle
        cx={parseFloat(pts.split(" ").pop()!.split(",")[0])}
        cy={parseFloat(pts.split(" ").pop()!.split(",")[1])}
        r={2.5}
        fill={lineColor}
      />
    </svg>
  )
}

function MetricRow({ label, series, color }: { label: string; series: YearValue[]; color?: string }) {
  if (!series || series.length === 0) return null
  const latest = series[series.length - 1]
  const isNeg = latest.value < 0
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "8px 0", borderBottom: `1px solid ${T.border}`,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: T.text2 }}>{label}</div>
        <div style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: isNeg ? T.red : (color || T.text) }}>
          {isNeg ? "-" : ""}${Math.abs(latest.value).toFixed(1)}B
          <span style={{ fontSize: 10, color: T.text3, marginLeft: 4 }}>({latest.year})</span>
        </div>
      </div>
      <Sparkline series={series} color={color || T.blue} />
    </div>
  )
}

export default function EDGARFundamentalsPanel({ data }: { data: EDGARFundamentals }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: T.text2 }}>{data.entity_name}</div>
        <div style={{ fontSize: 10, color: T.text3 }}>
          {data.years_available} years · {data.source}
        </div>
      </div>

      <MetricRow label="Revenue"          series={data.revenue_b}          color={T.green} />
      <MetricRow label="Net Income"        series={data.net_income_b}       color={T.blue} />
      <MetricRow label="Operating Income"  series={data.operating_income_b} color={T.purple} />
      <MetricRow label="Free Cash Flow"    series={data.fcf_b}              color={T.amber} />
      <MetricRow label="Total Debt"        series={data.total_debt_b}       color={T.red} />
    </div>
  )
}
