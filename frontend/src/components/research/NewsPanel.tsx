import type { NewsItem } from "../../types"
import { T } from "../../theme"

interface Props {
  news: NewsItem[]
  filteredCount?: number
}

const sentStyle = {
  positive: { bg: T.greenDim, color: T.green },
  negative: { bg: T.redDim,   color: T.red },
  neutral:  { bg: T.surface2, color: T.text2 },
}

const strengthColor = { HIGH: T.red, MEDIUM: T.amber, LOW: T.text3 }

export function NewsPanel({ news, filteredCount = 0 }: Props) {
  const items = news.slice(0, 8)
  return (
    <div>
      {filteredCount > 0 && (
        <div style={{ fontSize: 11, color: T.text3, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: T.amber, flexShrink: 0, display: "inline-block" }} />
          {filteredCount} off-topic {filteredCount === 1 ? "article" : "articles"} filtered — showing company-specific news only
        </div>
      )}

      {items.length === 0 && (
        <div style={{ fontSize: 12, color: T.text3 }}>No relevant news found</div>
      )}

      {items.map((item, i) => {
        const s = sentStyle[item.sentiment] ?? sentStyle.neutral
        const sc = item.catalyst_strength ? strengthColor[item.catalyst_strength] : null
        const isLast = i === items.length - 1
        return (
          <div key={i} style={{
            paddingBottom: isLast ? 0 : 10,
            marginBottom: isLast ? 0 : 10,
            borderBottom: isLast ? "none" : `1px solid ${T.border}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5, flexWrap: "wrap" }}>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
                background: s.bg, color: s.color, letterSpacing: "0.04em", flexShrink: 0,
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
              <span style={{ fontSize: 10, color: T.text3, fontFamily: T.mono, marginLeft: "auto" }}>
                {item.source} · {item.published}
              </span>
            </div>

            <div style={{ fontSize: 12, color: T.text, lineHeight: 1.45, marginBottom: item.description ? 4 : 0 }}>
              <a href={item.url} target="_blank" rel="noreferrer"
                style={{ color: "inherit", textDecoration: "none" }}
                onMouseEnter={e => (e.currentTarget.style.color = T.blue)}
                onMouseLeave={e => (e.currentTarget.style.color = "inherit")}
              >
                {item.headline}
              </a>
            </div>

            {item.description && (
              <div style={{ fontSize: 11, color: T.text3, lineHeight: 1.4 }}>
                {item.description}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
