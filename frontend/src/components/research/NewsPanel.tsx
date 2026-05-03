import type { NewsItem } from "../../types"
import { T } from "../../theme"

interface Props { news: NewsItem[] }

const sentStyle = {
  positive: { bg: T.greenDim, color: T.green },
  negative: { bg: T.redDim,   color: T.red },
  neutral:  { bg: T.surface2, color: T.text2 },
}

const strengthColor = { HIGH: T.red, MEDIUM: T.amber, LOW: T.text3 }

export function NewsPanel({ news }: Props) {
  return (
    <div>
      {news.length === 0 && (
        <div style={{ fontSize: 12, color: T.text3 }}>No recent news found</div>
      )}
      {news.slice(0, 5).map((item, i) => {
        const s = sentStyle[item.sentiment] ?? sentStyle.neutral
        const sc = item.catalyst_strength ? strengthColor[item.catalyst_strength] : null
        return (
          <div key={i} style={{
            paddingBottom: 10, marginBottom: 10,
            borderBottom: i < news.slice(0, 5).length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4, flexWrap: "wrap" }}>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
                background: s.bg, color: s.color, letterSpacing: "0.04em",
              }}>
                {item.sentiment.toUpperCase()}
              </span>
              {item.catalyst_type && (
                <span style={{
                  fontSize: 10, padding: "2px 7px", borderRadius: 20,
                  background: T.surface2, color: T.text2, border: `1px solid ${T.border}`,
                }}>
                  {item.catalyst_type}
                </span>
              )}
              {item.catalyst_strength && sc && (
                <span style={{
                  fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3,
                  background: `${sc}18`, color: sc, border: `1px solid ${sc}40`,
                  fontFamily: "monospace", letterSpacing: "0.05em",
                }}>
                  {item.catalyst_strength}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: T.text, lineHeight: 1.45, marginBottom: 4 }}>
              <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "none" }}>
                {item.headline}
              </a>
            </div>
            <div style={{ fontSize: 11, color: T.text3 }}>
              {item.source} · {item.published}
            </div>
          </div>
        )
      })}
    </div>
  )
}
