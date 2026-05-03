import { T } from "../../theme"
import type { DividendHealth, MoatResult } from "../../types"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>{children}</div>
)

const Stat = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div style={{ background: T.surface2, borderRadius: 8, padding: "9px 12px", border: `1px solid ${T.border}` }}>
    <Label>{label}</Label>
    <div style={{ fontSize: 15, fontWeight: 500, fontFamily: T.mono, color: color || T.text }}>{value}</div>
  </div>
)

function vColor(c: string) {
  if (c === "green")   return T.green
  if (c === "amber")   return T.amber
  if (c === "red")     return T.red
  return T.text2
}

export function DividendPanel({ data }: { data: DividendHealth }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>

  if (!data.pays_dividend) {
    return (
      <div style={{ color: T.text3, fontSize: 13, padding: "8px 0" }}>
        This stock does not currently pay a dividend.
      </div>
    )
  }

  const vc = vColor(data.verdict_color)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "8px 14px", borderRadius: 8,
        background: `${vc}18`, border: `1px solid ${vc}`,
      }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: vc }}>{data.verdict}</span>
        <span style={{ fontSize: 12, color: T.text2 }}>Dividend Safety Rating</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px,1fr))", gap: 8 }}>
        {data.dividend_yield_pct != null && <Stat label="Yield" value={`${data.dividend_yield_pct}%`} color={T.green} />}
        {data.payout_ratio_pct != null && (
          <Stat
            label="Payout Ratio"
            value={`${data.payout_ratio_pct}%`}
            color={data.payout_ratio_pct < 60 ? T.green : data.payout_ratio_pct < 80 ? T.amber : T.red}
          />
        )}
        {data.fcf_coverage != null && (
          <Stat
            label="FCF Coverage"
            value={`${data.fcf_coverage}x`}
            color={data.fcf_coverage >= 2 ? T.green : data.fcf_coverage >= 1 ? T.amber : T.red}
          />
        )}
        {data.div_cagr_3y_pct != null && <Stat label="3yr CAGR" value={`${data.div_cagr_3y_pct}%`} color={T.blue} />}
        {data.div_cagr_5y_pct != null && <Stat label="5yr CAGR" value={`${data.div_cagr_5y_pct}%`} color={T.blue} />}
        {data.consecutive_growth_years > 0 && (
          <Stat
            label="Growth Streak"
            value={`${data.consecutive_growth_years} yrs`}
            color={data.consecutive_growth_years >= 10 ? T.green : T.text2}
          />
        )}
      </div>

      <div>
        <Label>Safety Checks</Label>
        {Object.entries(data.checks || {}).map(([k, v]) => (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
            <span style={{ fontSize: 13, color: v ? T.green : T.red }}>{v ? "✓" : "✗"}</span>
            <span style={{ fontSize: 12, color: T.text2 }}>{k.replace(/_/g, " ")}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function MoatPanel({ data }: { data: MoatResult }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>
  const vc = vColor(data.moat_color)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          padding: "6px 16px", borderRadius: 8,
          background: `${vc}18`, border: `1px solid ${vc}`,
          fontSize: 14, fontWeight: 700, color: vc,
        }}>{data.moat_width} MOAT</div>
        <div style={{ fontSize: 22, fontWeight: 700, fontFamily: T.mono, color: vc }}>
          {data.score}<span style={{ fontSize: 12, color: T.text3, fontWeight: 400 }}>/{data.total}</span>
        </div>
        <span style={{ fontSize: 12, color: T.text2 }}>{data.summary}</span>
      </div>

      <div>
        {Object.entries(data.components || {}).map(([k, c]) => {
          const icon = c.pass === true ? "✓" : c.pass === false ? "✗" : "?"
          const color = c.pass === true ? T.green : c.pass === false ? T.red : T.text3
          return (
            <div key={k} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "7px 0", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 13, color, fontWeight: 600, width: 16, flexShrink: 0 }}>{icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
                  <span style={{ fontSize: 12, color: T.text }}>{c.label}</span>
                  <span style={{ fontSize: 12, fontFamily: T.mono, color: color }}>{c.value}</span>
                </div>
                <div style={{ fontSize: 11, color: T.text3 }}>{c.note}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
