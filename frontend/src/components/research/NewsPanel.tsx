import type { NewsItem } from "../../types"

interface Props { news: NewsItem[] }

const sentimentStyle = {
  positive: { bg: "#dcfce7", color: "#166534" },
  negative: { bg: "#fee2e2", color: "#991b1b" },
  neutral:  { bg: "#f3f4f6", color: "#374151" },
}

export function NewsPanel({ news }: Props) {
  return (
    <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10 }}>Recent news impact</div>
      {news.length === 0 && <div style={{ fontSize: 12, color: "#9ca3af" }}>No recent news found</div>}
      {news.slice(0, 6).map((item, i) => {
        const s = sentimentStyle[item.sentiment]
        return (
          <div key={i} style={{ paddingBottom: 10, marginBottom: 10, borderBottom: i < news.slice(0, 6).length - 1 ? "0.5px solid #f3f4f6" : "none" }}>
            <span style={{ display: "inline-block", fontSize: 10, fontWeight: 500, padding: "2px 7px", borderRadius: 20, background: s.bg, color: s.color, marginBottom: 4 }}>
              {item.sentiment.charAt(0).toUpperCase() + item.sentiment.slice(1)}
            </span>
            <div style={{ fontSize: 12, color: "#111", lineHeight: 1.4, marginBottom: 2 }}>
              <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "none" }}>
                {item.headline}
              </a>
            </div>
            <div style={{ fontSize: 11, color: "#9ca3af" }}>{item.source} · {item.published}</div>
          </div>
        )
      })}
    </div>
  )
}
