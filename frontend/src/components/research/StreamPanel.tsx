import { useStore } from "../../store"

const TOOL_LABELS: Record<string, string> = {
  get_price: "Price",
  get_technicals: "Technicals",
  get_news_impact: "News",
  get_sentiment: "Sentiment",
  get_analyst_consensus: "Analysts",
  get_earnings: "Earnings",
  get_fundamentals: "Fundamentals",
  get_options_signals: "Options",
  get_insider_activity: "Insider",
  get_institutional_changes: "Institutional",
  get_short_interest: "Short interest",
  get_geopolitical_events: "Geopolitical",
  get_macro_environment: "Macro",
  get_sector_heatmap: "Sectors",
  get_cascade_impact: "Cascade",
  get_price_forecast: "Forecast",
  get_risk_reward: "Risk/reward",
  get_convergence_score: "Signal score",
  get_trends: "Trends",
}

function formatSummary(content: string) {
  const lines = content.split("\n").map(l => l.trim()).filter(Boolean)
  return lines.map((line, i) => {
    // Signal / header lines
    if (line.startsWith("DAY TRADE") || line.startsWith("LONG TERM") || line.startsWith("Convergence Score")) {
      return (
        <div key={i} style={{ fontWeight: 600, fontSize: 13, color: "#111827", marginTop: i === 0 ? 0 : 12 }}>
          {line}
        </div>
      )
    }
    // Signal line (starts with "Signal:")
    if (line.startsWith("Signal:")) {
      return (
        <div key={i} style={{ fontWeight: 600, fontSize: 13, color: "#111827", marginTop: i === 0 ? 0 : 4 }}>
          {line}
        </div>
      )
    }
    // Verdict line
    if (line.startsWith("Verdict:")) {
      return (
        <div key={i} style={{ fontSize: 13, color: "#374151", marginTop: 8, fontStyle: "italic", borderTop: "1px solid #f3f4f6", paddingTop: 8 }}>
          {line}
        </div>
      )
    }
    // Bullet points
    if (line.startsWith("•") || line.startsWith("-")) {
      return (
        <div key={i} style={{ display: "flex", gap: 8, fontSize: 13, color: "#374151", lineHeight: 1.55, paddingLeft: 4, marginTop: 3 }}>
          <span style={{ color: "#6b7280", flexShrink: 0 }}>•</span>
          <span>{line.replace(/^[•\-]\s*/, "")}</span>
        </div>
      )
    }
    // Fallback — plain line
    return (
      <div key={i} style={{ fontSize: 13, color: "#374151", lineHeight: 1.55, marginTop: 3 }}>
        {line}
      </div>
    )
  })
}

export function StreamPanel() {
  const { streamEvents, isStreaming } = useStore()

  if (!streamEvents.length && !isStreaming) return null

  const toolsDone = streamEvents.filter(e => e.type === "tool_result")
  const toolsInProgress = streamEvents.filter(e => e.type === "tool_call")
  const reasoningEvent = streamEvents.find(e => e.type === "reasoning")
  const isDone = streamEvents.some(e => e.type === "done")

  const activeTools = isStreaming
    ? toolsInProgress.map(e => TOOL_LABELS[e.tool] || e.tool)
    : toolsDone.map(e => TOOL_LABELS[e.tool] || e.tool)

  return (
    <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>AI Research Summary</span>
        {isStreaming && (
          <span style={{ fontSize: 11, color: "#6b7280", display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#16a34a", display: "inline-block", animation: "pulse 1s infinite" }} />
            Analyzing...
          </span>
        )}
        {isDone && !isStreaming && (
          <span style={{ fontSize: 11, color: "#16a34a", fontWeight: 500 }}>Complete</span>
        )}
      </div>

      {/* Tool activity strip */}
      {activeTools.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 14 }}>
          {activeTools.map((label, i) => {
            const done = !isStreaming || toolsDone.some(e => (TOOL_LABELS[e.tool] || e.tool) === label)
            return (
              <span key={i} style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 20,
                background: done ? "#f0fdf4" : "#eff6ff",
                color: done ? "#16a34a" : "#2563eb",
                border: `1px solid ${done ? "#bbf7d0" : "#bfdbfe"}`,
              }}>
                {done ? "✓ " : "→ "}{label}
              </span>
            )
          })}
        </div>
      )}

      {/* Summary / reasoning */}
      {reasoningEvent ? (
        <div style={{ borderTop: "1px solid #f3f4f6", paddingTop: 14 }}>
          {formatSummary(reasoningEvent.content)}
        </div>
      ) : isStreaming ? (
        <div style={{ fontSize: 13, color: "#9ca3af", paddingTop: 4 }}>Running analysis...</div>
      ) : null}
    </div>
  )
}
