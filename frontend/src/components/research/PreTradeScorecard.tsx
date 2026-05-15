import type { PreTradeScore, PreTradeCheck } from "../../types"
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

const VERDICT_LEAD: Record<string, string> = {
  PROCEED: "Setup is clean — entry is justified.",
  CAUTION: "Mixed setup — entry is possible but smaller size is wise.",
  AVOID:   "Setup is too weak — skip this trade.",
}

/**
 * Plain-English explanation of the score. Synthesises the checks into two
 * lines (what's working / what's missing) so the user doesn't have to read
 * 8 dots and reverse-engineer the recommendation themselves.
 *
 * Opus idea #22 — same data, narrative form.
 */
function buildExplanation(score: PreTradeScore): { lead: string; positives: PreTradeCheck[]; negatives: PreTradeCheck[] } {
  const lead = VERDICT_LEAD[score.verdict] ?? `Score ${score.score} of ${score.total}.`
  const positives = score.checks.filter((c) => c.pass === true)
  const negatives = score.checks.filter((c) => c.pass === false)
  return { lead, positives, negatives }
}

function ChecklistSummary({ score }: { score: PreTradeScore }) {
  const { lead, positives, negatives } = buildExplanation(score)
  const accent = VERDICT_COLOR[score.verdict_color] ?? T.text2

  if (score.checks.length === 0) return null

  return (
    <div style={{
      background: T.surface2, borderLeft: `3px solid ${accent}`,
      padding: "8px 12px", borderRadius: 4,
      fontSize: 12, color: T.text, lineHeight: 1.5,
    }}>
      <div style={{ marginBottom: positives.length || negatives.length ? 4 : 0 }}>{lead}</div>
      {positives.length > 0 && (
        <div style={{ color: T.text2 }}>
          <span style={{ color: T.green, fontWeight: 600 }}>Working:</span>{" "}
          {positives.map((p) => p.label.toLowerCase()).join(", ")}.
        </div>
      )}
      {negatives.length > 0 && (
        <div style={{ color: T.text2 }}>
          <span style={{ color: T.red, fontWeight: 600 }}>Missing:</span>{" "}
          {negatives.map((n) => `${n.label.toLowerCase()} (${n.value})`).join(", ")}.
        </div>
      )}
    </div>
  )
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

      {/* Plain-English summary — what's working, what's missing, bottom line */}
      <ChecklistSummary score={data} />

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
