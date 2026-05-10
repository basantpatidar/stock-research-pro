import type { PreTradeScore } from "../../types"
import { T } from "../../theme"

interface Props {
  data: PreTradeScore
}

const VERDICT_COLOR: Record<string, string> = {
  green: T.green,
  amber: T.amber,
  red:   T.red,
}

const VERDICT_DIM: Record<string, string> = {
  green: "#22cc6620",
  amber: "#ffaa0020",
  red:   "#ff444420",
}

export function PreTradeScorecard({ data }: Props) {
  const accent = VERDICT_COLOR[data.verdict_color] ?? T.text2
  const dim    = VERDICT_DIM[data.verdict_color]   ?? T.surface2

  return (
    <div style={{
      background: T.surface, border: `1px solid ${accent}`,
      borderRadius: 12, padding: "12px 16px",
      display: "flex", flexDirection: "column", gap: 10,
    }}>
      {/* Header row — verdict + score */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          background: dim, border: `1px solid ${accent}`,
          borderRadius: 8, padding: "6px 14px",
        }}>
          <span style={{
            fontSize: 16, fontWeight: 700, fontFamily: T.mono,
            letterSpacing: "0.08em", color: accent,
          }}>
            {data.verdict}
          </span>
          <span style={{
            fontSize: 22, fontWeight: 700, fontFamily: T.mono, color: accent,
          }}>
            {data.score}<span style={{ fontSize: 14, color: T.text3, fontWeight: 400 }}>/{data.total}</span>
          </span>
        </div>
        <span style={{ fontSize: 11, color: T.text3, fontFamily: T.mono }}>
          Pre-Trade Checklist
        </span>
      </div>

      {/* Checklist grid — 2 columns */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: "5px 12px",
      }}>
        {data.checks.map((c) => {
          const dotColor = c.pass === true ? T.green : c.pass === false ? T.red : T.text3
          return (
            <div
              key={c.label}
              title={c.tip || c.value}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <span style={{
                width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                background: dotColor,
                boxShadow: c.pass === true ? `0 0 4px ${T.green}` : undefined,
              }} />
              <span style={{ fontSize: 11, color: T.text2, flexShrink: 0 }}>{c.label}</span>
              <span style={{
                fontSize: 10, fontFamily: T.mono,
                color: c.pass === null ? T.text3 : dotColor,
                marginLeft: "auto", whiteSpace: "nowrap",
              }}>
                {c.value}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
