import type { ConvergenceScore } from "../../types"
import { T, scoreStyle } from "../../theme"

interface Props { data: ConvergenceScore }

const SIZE = 88
const R = 34
const CIRC = 2 * Math.PI * R

export function SignalScore({ data }: Props) {
  const s = scoreStyle(data.convergence_score)
  const progress = (data.convergence_score / 100) * CIRC
  const offset = CIRC - progress

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderRadius: 12,
      padding: "1rem 1.25rem",
      boxShadow: s.glow,
    }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Signal Score
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 14 }}>
        {/* SVG arc gauge */}
        <div style={{ flexShrink: 0 }}>
          <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} style={{ transform: "rotate(-90deg)" }}>
            <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke={T.border} strokeWidth={6} />
            <circle
              cx={SIZE / 2} cy={SIZE / 2} r={R}
              fill="none"
              stroke={s.border}
              strokeWidth={6}
              strokeDasharray={`${progress} ${CIRC}`}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 0.8s ease, stroke 0.4s ease" }}
            />
          </svg>
          <div style={{
            position: "relative",
            top: -(SIZE / 2 + 14),
            textAlign: "center",
            height: 0,
            pointerEvents: "none",
          }}>
            <span style={{
              fontFamily: T.mono, fontSize: 20, fontWeight: 600,
              color: s.text, lineHeight: 1,
            }}>{data.convergence_score}</span>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: s.text, marginBottom: 2 }}>{data.label}</div>
          <div style={{ fontSize: 11, color: T.text2 }}>
            <span style={{ color: T.green }}>{data.bullish_signals} bull</span>
            {" · "}
            <span style={{ color: T.red }}>{data.bearish_signals} bear</span>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3 }}>
        {data.signals.map((sig, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
              background: sig.direction === "bullish" ? T.green : sig.direction === "bearish" ? T.red : T.text3,
            }} />
            <span style={{ fontSize: 11, color: T.text2, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sig.signal}</span>
            <span style={{
              fontSize: 11, fontFamily: T.mono, fontWeight: 500, flexShrink: 0,
              color: sig.direction === "bullish" ? T.green : sig.direction === "bearish" ? T.red : T.text3,
            }}>
              {sig.points > 0 ? "+" : ""}{sig.points}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
