import { useStore } from "../../store"
import { T } from "../../theme"
import type { TradeMode } from "../../types"

const MODES: { value: TradeMode; label: string }[] = [
  { value: "day_trade", label: "Day" },
  { value: "both",      label: "Both" },
  { value: "long_term", label: "Long" },
]

export function ModeToggle() {
  const { mode, setMode } = useStore()

  return (
    <div style={{
      display: "flex",
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderRadius: 7,
      overflow: "hidden",
      flexShrink: 0,
    }}>
      {MODES.map((m, i) => (
        <button
          key={m.value}
          onClick={() => setMode(m.value)}
          style={{
            padding: "5px 13px",
            fontSize: 12,
            border: "none",
            borderRight: i < MODES.length - 1 ? `1px solid ${T.border}` : "none",
            cursor: "pointer",
            background: mode === m.value ? T.blue : "transparent",
            fontWeight: mode === m.value ? 600 : 400,
            color: mode === m.value ? "#fff" : T.text2,
            transition: "all 0.12s ease",
            letterSpacing: "0.02em",
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
