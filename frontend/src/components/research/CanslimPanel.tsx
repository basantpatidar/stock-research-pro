import { T } from "../../theme"
import type { CanslimResult, VCPResult } from "../../types"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>{children}</div>
)

function verdictColor(c: string) {
  if (c === "green") return T.green
  if (c === "amber") return T.amber
  return T.red
}

function CriterionRow({ letter, criterion }: { letter: string; criterion: { pass: boolean | null; label: string; detail: string } }) {
  const icon = criterion.pass === true ? "✓" : criterion.pass === false ? "✗" : "?"
  const color = criterion.pass === true ? T.green : criterion.pass === false ? T.red : T.text3
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      padding: "7px 0", borderBottom: `1px solid ${T.border}`,
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: 4, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: `${color}22`, border: `1px solid ${color}`,
        fontSize: 11, fontWeight: 600, color, fontFamily: T.mono,
      }}>{letter}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: T.text, fontWeight: 500 }}>{criterion.label}</span>
          <span style={{ fontSize: 12, color, fontWeight: 600 }}>{icon}</span>
        </div>
        <div style={{ fontSize: 11, color: T.text3, marginTop: 1 }}>{criterion.detail}</div>
      </div>
    </div>
  )
}

export function CanslimPanel({ data }: { data: CanslimResult }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>
  const vc = verdictColor(data.verdict_color)
  const letters = ["C", "A", "N", "S", "L", "I", "M"]
  const keys = Object.keys(data.criteria)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          padding: "6px 14px", borderRadius: 8,
          background: `${vc}18`, border: `1px solid ${vc}`,
          fontSize: 13, fontWeight: 600, color: vc,
        }}>{data.verdict}</div>
        <div style={{ fontSize: 24, fontWeight: 700, fontFamily: T.mono, color: vc }}>
          {data.score}<span style={{ fontSize: 13, color: T.text3, fontWeight: 400 }}>/{data.total}</span>
        </div>
        <div style={{ fontSize: 11, color: T.text3 }}>criteria met</div>
      </div>
      <div>
        {keys.map((k, i) => (
          <CriterionRow key={k} letter={letters[i] || "?"} criterion={data.criteria[k]} />
        ))}
      </div>
    </div>
  )
}

export function VCPPanel({ data }: { data: VCPResult }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>
  const vc = verdictColor(data.verdict_color)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          padding: "6px 14px", borderRadius: 8,
          background: `${vc}18`, border: `1px solid ${vc}`,
          fontSize: 13, fontWeight: 600, color: vc,
        }}>{data.verdict}</div>
        <div style={{
          padding: "4px 10px", borderRadius: 6, fontSize: 13,
          fontWeight: 700, background: T.surface2, border: `1px solid ${T.border}`,
          color: vc, fontFamily: T.mono,
        }}>Grade: {data.setup_quality}</div>
        <div style={{ fontSize: 11, color: T.text3 }}>{data.criteria_passed}/{data.criteria_total} criteria</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(110px,1fr))", gap: 7 }}>
        {[
          { label: "Current", value: `$${data.current_price}` },
          { label: "50d MA", value: `$${data.ma50}` },
          { label: "150d MA", value: data.ma150 != null ? `$${data.ma150}` : "—" },
          { label: "200d MA", value: data.ma200 != null ? `$${data.ma200}` : "—" },
          { label: "52w High", value: `$${data.high_52w}` },
          { label: "52w Low", value: `$${data.low_52w}` },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: T.surface2, borderRadius: 7, padding: "8px 10px", border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: T.text }}>{value}</div>
          </div>
        ))}
      </div>

      <div>
        {Object.entries(data.criteria).map(([k, c]) => {
          const icon = c.pass === true ? "✓" : c.pass === false ? "✗" : "?"
          const color = c.pass === true ? T.green : c.pass === false ? T.red : T.text3
          return (
            <div key={k} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 13, color, fontWeight: 600, width: 16, flexShrink: 0 }}>{icon}</span>
              <div>
                <div style={{ fontSize: 12, color: T.text }}>{c.label}</div>
                <div style={{ fontSize: 11, color: T.text3 }}>{c.detail}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
