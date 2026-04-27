import type { NewsItem } from "../../types"
import { T } from "../../theme"

interface Props { news: NewsItem[] }

const sentStyle = {
  positive: { bg: T.greenDim, color: T.green },
  negative: { bg: T.redDim,   color: T.red },
  neutral:  { bg: T.surface2, color: T.text2 },
}

export function NewsPanel({ news }: Props) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
        News Impact
      </div>
      {news.length === 0 && (
        <div style={{ fontSize: 12, color: T.text3 }}>No recent news found</div>
      )}
      {news.slice(0, 5).map((item, i) => {
        const s = sentStyle[item.sentiment] ?? sentStyle.neutral
        return (
          <div key={i} style={{
            paddingBottom: 10, marginBottom: 10,
            borderBottom: i < news.slice(0, 5).length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
                background: s.bg, color: s.color, letterSpacing: "0.04em",
              }}>
                {item.sentiment.toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 12, color: T.text, lineHeight: 1.45, marginBottom: 4 }}>
              <a href={item.url} target="_blank" rel="noreferrer" style={{
                color: "inherit", textDecoration: "none",
              }}>
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
