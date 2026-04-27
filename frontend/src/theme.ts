export const T = {
  bg: "#0b0f1a",
  surface: "#111827",
  surface2: "#1a2234",
  surfaceHover: "#1e2840",

  border: "#1e293b",
  borderBright: "#2d3f5e",

  text: "#e2e8f6",
  text2: "#64748b",
  text3: "#374151",

  blue: "#3b82f6",
  blueDim: "rgba(59,130,246,0.12)",
  blueGlow: "0 0 20px rgba(59,130,246,0.2)",

  green: "#10b981",
  greenDim: "rgba(16,185,129,0.12)",
  greenGlow: "0 0 20px rgba(16,185,129,0.2)",

  red: "#ef4444",
  redDim: "rgba(239,68,68,0.12)",
  redGlow: "0 0 20px rgba(239,68,68,0.2)",

  amber: "#f59e0b",
  amberDim: "rgba(245,158,11,0.12)",

  purple: "#8b5cf6",
  purpleDim: "rgba(139,92,246,0.12)",

  font: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  mono: '"JetBrains Mono", "SF Mono", "Fira Code", "Consolas", monospace',
} as const

export const scoreStyle = (score: number) => {
  if (score >= 70) return { text: T.green, bg: T.greenDim, border: T.green, glow: T.greenGlow }
  if (score >= 50) return { text: T.amber, bg: T.amberDim, border: T.amber, glow: "none" }
  return { text: T.red, bg: T.redDim, border: T.red, glow: T.redGlow }
}

export const chgColor = (v: number) => (v >= 0 ? T.green : T.red)
export const chgDim = (v: number) => (v >= 0 ? T.greenDim : T.redDim)
