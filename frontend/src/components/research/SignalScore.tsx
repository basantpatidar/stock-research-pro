import type { ConvergenceScore } from "../../types"

interface Props { data: ConvergenceScore }

const scoreColor = (score: number) => {
  if (score >= 70) return { text: "#065f46", bg: "#d1fae5", ring: "#16a34a" }
  if (score >= 50) return { text: "#92400e", bg: "#fef3c7", ring: "#d97706" }
  return { text: "#991b1b", bg: "#fee2e2", ring: "#dc2626" }
}

export function SignalScore({ data }: Props) {
  const c = scoreColor(data.convergence_score)

  return (
    <div style={{ background: "#fff", border: `2px solid ${c.ring}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Signal convergence score</div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 12 }}>
        <div style={{
          width: 64, height: 64, borderRadius: "50%",
          background: c.bg, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <span style={{ fontSize: 22, fontWeight: 500, color: c.text, lineHeight: 1 }}>{data.convergence_score}</span>
          <span style={{ fontSize: 10, color: c.text }}>/100</span>
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: c.text }}>{data.label}</div>
          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
            {data.bullish_signals} bullish · {data.bearish_signals} bearish signals
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
        {data.signals.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <div style={{
              width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
              background: s.direction === "bullish" ? "#16a34a" : s.direction === "bearish" ? "#dc2626" : "#9ca3af",
            }} />
            <span style={{ color: "#6b7280", flex: 1 }}>{s.signal}</span>
            <span style={{
              fontWeight: 500,
              color: s.direction === "bullish" ? "#15803d" : s.direction === "bearish" ? "#b91c1c" : "#6b7280",
              marginLeft: "auto",
            }}>{s.points > 0 ? "+" : ""}{s.points}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
