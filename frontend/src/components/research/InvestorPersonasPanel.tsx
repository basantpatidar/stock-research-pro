import { T, scoreStyle } from "../../theme"

interface Persona {
  name: string
  style?: string
  verdict: string
  score?: number
  thesis?: string
  bull_factors?: string[]
  bear_factors?: string[]
  key_factors?: string[]
}

interface Props { data: any }

const PERSONA_ICON: Record<string, string> = {
  "Warren Buffett": "🏦",
  "Benjamin Graham": "📖",
  "Michael Burry": "🐻",
  "Peter Lynch": "📈",
  "Cathie Wood": "🚀",
}

const verdictStyle = (v: string) => {
  const lv = v.toLowerCase()
  if (lv.includes("buy") || lv.includes("strong"))
    return { bg: T.greenDim, color: T.green, border: T.green }
  if (lv.includes("avoid") || lv.includes("sell") || lv.includes("short"))
    return { bg: T.redDim,   color: T.red,   border: T.red }
  return { bg: T.amberDim, color: T.amber, border: T.amber }
}

export function InvestorPersonasPanel({ data }: Props) {
  const personas: Persona[] = data?.personas ?? []

  if (!personas.length) {
    return <div style={{ fontSize: 12, color: T.text2 }}>No persona data available.</div>
  }

  return (
    <div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 10,
      }}>
        {personas.map((p) => {
          const vs = verdictStyle(p.verdict)
          const ss = p.score != null ? scoreStyle(p.score) : null
          const factors = p.key_factors ?? [...(p.bull_factors ?? []), ...(p.bear_factors ?? [])]

          return (
            <div key={p.name} style={{
              background: T.surface2, border: `1px solid ${T.border}`,
              borderRadius: 10, padding: "12px 14px",
              display: "flex", flexDirection: "column", gap: 8,
            }}>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18 }}>{PERSONA_ICON[p.name] ?? "👤"}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{p.name}</div>
                  {p.style && (
                    <div style={{ fontSize: 10, color: T.text2 }}>{p.style}</div>
                  )}
                </div>
                {p.score != null && (
                  <span style={{
                    fontSize: 13, fontFamily: T.mono, fontWeight: 700,
                    color: ss!.text,
                  }}>{p.score}</span>
                )}
              </div>

              {/* Verdict badge */}
              <span style={{
                display: "inline-block", alignSelf: "flex-start",
                fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                background: vs.bg, color: vs.color, border: `1px solid ${vs.border}`,
                letterSpacing: "0.03em",
              }}>
                {p.verdict}
              </span>

              {/* Thesis */}
              {p.thesis && (
                <div style={{ fontSize: 11, color: T.text2, lineHeight: 1.5 }}>
                  {p.thesis.slice(0, 140)}{p.thesis.length > 140 ? "…" : ""}
                </div>
              )}

              {/* Key factors */}
              {factors.length > 0 && (
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 3 }}>
                  {factors.slice(0, 3).map((f, i) => (
                    <li key={i} style={{ display: "flex", gap: 6, fontSize: 11, color: T.text2, lineHeight: 1.4 }}>
                      <span style={{ color: T.text3, flexShrink: 0 }}>›</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
