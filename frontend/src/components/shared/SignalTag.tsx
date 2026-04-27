import { T } from "../../theme"

const STYLES: Record<string, { bg: string; color: string; border: string }> = {
  "Buy now":        { bg: T.greenDim,  color: T.green,  border: T.green },
  "Buy — 1 week":   { bg: T.greenDim,  color: T.green,  border: T.green },
  "Buy — 1 month":  { bg: "rgba(16,185,129,0.07)", color: "#34d399", border: "#34d399" },
  "Hold":           { bg: T.surface2,  color: T.text2,  border: T.borderBright },
  "Watch — wait":   { bg: T.amberDim,  color: T.amber,  border: T.amber },
  "Watch — risky":  { bg: T.amberDim,  color: T.amber,  border: T.amber },
  "Avoid":          { bg: T.redDim,    color: T.red,    border: T.red },
  "Sell":           { bg: T.redDim,    color: T.red,    border: T.red },
}

interface Props { signal: string; size?: "sm" | "md" }

export function SignalTag({ signal, size = "md" }: Props) {
  const s = STYLES[signal] ?? { bg: T.surface2, color: T.text2, border: T.borderBright }
  return (
    <span style={{
      display: "inline-block",
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.border}`,
      fontSize: size === "sm" ? 10 : 11,
      fontWeight: 500,
      padding: size === "sm" ? "2px 8px" : "3px 10px",
      borderRadius: 20,
      whiteSpace: "nowrap",
      letterSpacing: "0.02em",
    }}>
      {signal}
    </span>
  )
}
