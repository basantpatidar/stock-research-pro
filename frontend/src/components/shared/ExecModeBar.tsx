import { useStore } from "../../store"
import { T } from "../../theme"
import type { ExecMode } from "../../types"

const MODES: { value: ExecMode; label: string; sub: string; tokens: string }[] = [
  { value: "saver",  label: "Saver",  sub: "Rule-based, 0 tokens",    tokens: "0" },
  { value: "normal", label: "Normal", sub: "Click to expand panels",  tokens: "~2.5K" },
  { value: "deep",   label: "Deep",   sub: "All panels auto-run",     tokens: "~15K" },
]

const TOKEN_WARNING = 25_000

export function ExecModeBar() {
  const { execMode, setExecMode, tokenCount } = useStore()

  const pct = Math.min(100, Math.round((tokenCount / TOKEN_WARNING) * 100))
  const barColor = pct >= 80 ? T.red : pct >= 50 ? T.amber : T.green

  return (
    <div style={{
      background: T.surface,
      borderBottom: `1px solid ${T.border}`,
      padding: "8px 1.5rem",
      display: "flex",
      alignItems: "center",
      gap: 16,
      flexWrap: "wrap",
    }}>
      {/* Mode buttons */}
      <div style={{ display: "flex", gap: 0, background: T.surface2, borderRadius: 8, border: `1px solid ${T.border}`, overflow: "hidden" }}>
        {MODES.map((m, i) => (
          <button
            key={m.value}
            onClick={() => setExecMode(m.value)}
            title={`${m.sub} · ${m.tokens} tokens/search`}
            style={{
              padding: "5px 14px",
              fontSize: 12,
              fontWeight: execMode === m.value ? 600 : 400,
              border: "none",
              borderRight: i < MODES.length - 1 ? `1px solid ${T.border}` : "none",
              cursor: "pointer",
              background: execMode === m.value
                ? m.value === "saver" ? T.greenDim
                : m.value === "deep"  ? T.purpleDim
                : T.blueDim
                : "transparent",
              color: execMode === m.value
                ? m.value === "saver" ? T.green
                : m.value === "deep"  ? T.purple
                : T.blue
                : T.text2,
              transition: "all 0.12s ease",
              letterSpacing: "0.02em",
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Token counter */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
        <span style={{ fontSize: 11, color: T.text2 }}>Session tokens</span>
        <div style={{ width: 80, height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            width: `${pct}%`, height: "100%",
            background: barColor, borderRadius: 2,
            transition: "width 0.4s ease, background 0.3s ease",
          }} />
        </div>
        <span style={{
          fontSize: 11, fontFamily: T.mono, fontWeight: 500,
          color: pct >= 80 ? T.red : pct >= 50 ? T.amber : T.text2,
        }}>
          {tokenCount >= 1000 ? `${(tokenCount / 1000).toFixed(1)}K` : tokenCount}
        </span>
        {pct >= 80 && (
          <span style={{ fontSize: 10, color: T.red, fontWeight: 500 }}>⚠ high</span>
        )}
      </div>
    </div>
  )
}
