import { useStore } from "../../store"
import type { TradeMode } from "../../types"

const MODES: { value: TradeMode; label: string }[] = [
  { value: "day_trade", label: "Day trade" },
  { value: "both", label: "Both" },
  { value: "long_term", label: "Long term" },
]

export function ModeToggle() {
  const { mode, setMode } = useStore()

  return (
    <div style={{
      display: "flex",
      border: "0.5px solid #d1d5db",
      borderRadius: 8,
      overflow: "hidden",
    }}>
      {MODES.map((m) => (
        <button
          key={m.value}
          onClick={() => setMode(m.value)}
          style={{
            padding: "6px 14px",
            fontSize: 13,
            border: "none",
            borderRight: m.value !== "long_term" ? "0.5px solid #d1d5db" : "none",
            cursor: "pointer",
            background: mode === m.value ? "#f3f4f6" : "transparent",
            fontWeight: mode === m.value ? 500 : 400,
            color: mode === m.value ? "#111" : "#6b7280",
            transition: "background 0.15s",
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
