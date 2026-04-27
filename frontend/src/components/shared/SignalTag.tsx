import type { SignalLabel } from "../../types"

const SIGNAL_STYLES: Record<string, { bg: string; color: string }> = {
  "Buy now":       { bg: "#d1fae5", color: "#065f46" },
  "Buy — 1 week":  { bg: "#dcfce7", color: "#14532d" },
  "Buy — 1 month": { bg: "#ecfdf5", color: "#166534" },
  "Hold":          { bg: "#f3f4f6", color: "#374151" },
  "Watch — wait":  { bg: "#fef3c7", color: "#92400e" },
  "Watch — risky": { bg: "#fef9c3", color: "#713f12" },
  "Avoid":         { bg: "#fee2e2", color: "#991b1b" },
  "Sell":          { bg: "#fecaca", color: "#7f1d1d" },
}

interface Props {
  signal: string
  size?: "sm" | "md"
}

export function SignalTag({ signal, size = "md" }: Props) {
  const style = SIGNAL_STYLES[signal] || { bg: "#f3f4f6", color: "#374151" }
  return (
    <span style={{
      display: "inline-block",
      background: style.bg,
      color: style.color,
      fontSize: size === "sm" ? 11 : 12,
      fontWeight: 500,
      padding: size === "sm" ? "2px 7px" : "3px 10px",
      borderRadius: 20,
      whiteSpace: "nowrap",
    }}>
      {signal}
    </span>
  )
}
