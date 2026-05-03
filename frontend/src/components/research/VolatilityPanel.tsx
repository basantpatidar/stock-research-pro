import { T } from "../../theme"
import type { VolatilityForecast, RegimeResult } from "../../types"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>
    {children}
  </div>
)

const Pill = ({ label, color }: { label: string; color: string }) => (
  <span style={{
    fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 12,
    background: `${color}22`, color, border: `1px solid ${color}`,
    letterSpacing: "0.06em",
  }}>{label}</span>
)

function colorFor(c: string): string {
  if (c === "green")   return T.green
  if (c === "amber")   return T.amber
  if (c === "red")     return T.red
  if (c === "blue")    return T.blue
  if (c === "purple")  return T.purple
  return T.text2
}

export function VolatilityPanel({ data }: { data: VolatilityForecast }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>

  const regimeColor = colorFor(data.vol_regime_color)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Pill label={data.vol_regime} color={regimeColor} />
        <span style={{ fontSize: 12, color: T.text2 }}>{data.vol_regime_tip}</span>
        <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>model: {data.model}</span>
      </div>

      {/* Vol stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
        {[
          { label: "Annualized Vol", value: `${data.annualized_vol_pct}%`, color: regimeColor },
          { label: "Realized 20d", value: `${data.realized_vol_20d_pct}%` },
          { label: "Realized 60d", value: `${data.realized_vol_60d_pct}%` },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: T.surface2, borderRadius: 8, padding: "10px 12px", border: `1px solid ${T.border}` }}>
            <Label>{label}</Label>
            <div style={{ fontSize: 16, fontWeight: 500, fontFamily: T.mono, color: color || T.text }}>{value}</div>
          </div>
        ))}
      </div>

      {/* 5-day forecast */}
      {data.forecasts?.length > 0 && (
        <div>
          <Label>5-Day Expected Range Forecast</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {data.forecasts.map((f) => (
              <div key={f.day} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "7px 10px", background: T.surface2,
                borderRadius: 6, border: `1px solid ${T.border}`,
              }}>
                <span style={{ fontSize: 11, color: T.text3, width: 32, fontFamily: T.mono }}>D+{f.day}</span>
                <span style={{ fontSize: 12, fontFamily: T.mono, color: T.red }}>
                  ${f.expected_range_low.toFixed(2)}
                </span>
                <div style={{ flex: 1, height: 2, background: T.border, borderRadius: 1 }}>
                  <div style={{ height: "100%", background: `linear-gradient(90deg, ${T.red}, ${T.green})`, borderRadius: 1 }} />
                </div>
                <span style={{ fontSize: 12, fontFamily: T.mono, color: T.green }}>
                  ${f.expected_range_high.toFixed(2)}
                </span>
                <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono, width: 44, textAlign: "right" }}>
                  ±{f.daily_vol_pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function RegimePanel({ data }: { data: RegimeResult }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>
  const c = colorFor(data.regime_color)
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Pill label={data.regime} color={c} />
        <span style={{ fontSize: 12, color: T.text2 }}>{data.description}</span>
        <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>
          {data.confidence_pct}% confidence
        </span>
      </div>

      <div style={{ background: T.surface2, borderRadius: 8, padding: "10px 13px", border: `1px solid ${T.border}` }}>
        <Label>Recommended Strategy</Label>
        <div style={{ fontSize: 12, color: T.text, lineHeight: 1.5 }}>{data.recommended_strategy}</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
        {[
          { label: "ADX Proxy", value: data.adx_proxy.toFixed(0) },
          { label: "Return 20d", value: `${data.return_20d_pct}%`, color: data.return_20d_pct >= 0 ? T.green : T.red },
          { label: "Return 60d", value: `${data.return_60d_pct}%`, color: data.return_60d_pct >= 0 ? T.green : T.red },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: T.surface2, borderRadius: 8, padding: "9px 11px", border: `1px solid ${T.border}` }}>
            <Label>{label}</Label>
            <div style={{ fontSize: 15, fontWeight: 500, fontFamily: T.mono, color: color || T.text }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
