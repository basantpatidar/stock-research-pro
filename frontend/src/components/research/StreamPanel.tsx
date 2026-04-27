import { useStore } from "../../store"
import { T } from "../../theme"

const TOOL_LABELS: Record<string, string> = {
  get_price: "price",
  get_technicals: "technicals",
  get_news_impact: "news",
  get_sentiment: "sentiment",
  get_analyst_consensus: "analysts",
  get_earnings: "earnings",
  get_fundamentals: "fundamentals",
  get_options_signals: "options",
  get_insider_activity: "insider",
  get_institutional_changes: "institutional",
  get_short_interest: "short_interest",
  get_geopolitical_events: "geopolitical",
  get_macro_environment: "macro",
  get_sector_heatmap: "sectors",
  get_cascade_impact: "cascade",
  get_price_forecast: "forecast",
  get_risk_reward: "risk_reward",
  get_convergence_score: "signal_score",
  get_trends: "trends",
}

function renderSummary(content: string) {
  const lines = content.split("\n").map(l => l.trim()).filter(Boolean)
  return lines.map((line, i) => {
    if (line.startsWith("DAY TRADE") || line.startsWith("LONG TERM") || line.startsWith("Convergence Score")) {
      return (
        <div key={i} style={{ fontWeight: 600, color: T.blue, marginTop: i === 0 ? 0 : 14, marginBottom: 4, letterSpacing: "0.04em" }}>
          {line}
        </div>
      )
    }
    if (line.startsWith("Signal:")) {
      return (
        <div key={i} style={{ fontWeight: 600, color: T.text, marginTop: 4 }}>
          {line}
        </div>
      )
    }
    if (line.startsWith("Verdict:")) {
      return (
        <div key={i} style={{
          color: T.text2, marginTop: 10, fontStyle: "italic",
          borderTop: `1px solid ${T.border}`, paddingTop: 10,
        }}>
          {line}
        </div>
      )
    }
    if (line.startsWith("•") || line.startsWith("-")) {
      return (
        <div key={i} style={{ display: "flex", gap: 8, color: T.text, lineHeight: 1.6, paddingLeft: 2, marginTop: 3 }}>
          <span style={{ color: T.text3, flexShrink: 0 }}>›</span>
          <span>{line.replace(/^[•\-]\s*/, "")}</span>
        </div>
      )
    }
    return (
      <div key={i} style={{ color: T.text2, lineHeight: 1.6, marginTop: 3 }}>{line}</div>
    )
  })
}

export function StreamPanel() {
  const { streamEvents, isStreaming } = useStore()

  if (!streamEvents.length && !isStreaming) return null

  const toolsDone = streamEvents.filter(e => e.type === "tool_result")
  const toolsInFlight = streamEvents.filter(e => e.type === "tool_call")
  const reasoningEvent = streamEvents.find(e => e.type === "reasoning")
  const isDone = streamEvents.some(e => e.type === "done")

  const activeTools = isStreaming
    ? toolsInFlight.map(e => TOOL_LABELS[e.tool] || e.tool)
    : toolsDone.map(e => TOOL_LABELS[e.tool] || e.tool)

  return (
    <div className="animate-in" style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderRadius: 12,
      padding: "1rem 1.25rem",
      marginBottom: 12,
      fontFamily: T.mono,
      fontSize: 13,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: T.purple, fontSize: 14 }}>◈</span>
          <span style={{ fontFamily: T.font, fontSize: 13, fontWeight: 500, color: T.text }}>AI Research Summary</span>
        </div>
        {isStreaming && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{
              width: 7, height: 7, borderRadius: "50%",
              background: T.green,
              animation: "pulse-dot 1s ease-in-out infinite",
            }} />
            <span style={{ fontSize: 11, color: T.text2, fontFamily: T.font }}>Analyzing…</span>
          </div>
        )}
        {isDone && !isStreaming && (
          <span style={{ fontSize: 11, color: T.green, fontFamily: T.font }}>✓ Complete</span>
        )}
      </div>

      {/* Tool activity row */}
      {activeTools.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 14, paddingBottom: 12, borderBottom: `1px solid ${T.border}` }}>
          {activeTools.map((label, i) => {
            const done = !isStreaming || toolsDone.some(e => (TOOL_LABELS[e.tool] || e.tool) === label)
            return (
              <span key={i} style={{
                fontSize: 10,
                padding: "2px 8px",
                borderRadius: 4,
                background: done ? T.greenDim : T.blueDim,
                color: done ? T.green : T.blue,
                border: `1px solid ${done ? T.green : T.blue}`,
                opacity: done ? 1 : 0.85,
                letterSpacing: "0.02em",
              }}>
                {done ? "✓ " : "→ "}{label}
              </span>
            )
          })}
        </div>
      )}

      {/* Summary */}
      {reasoningEvent ? (
        <div style={{ fontSize: 13, fontFamily: T.font, lineHeight: 1.6 }}>
          {renderSummary(reasoningEvent.content)}
        </div>
      ) : isStreaming ? (
        <div style={{ color: T.text3, display: "flex", alignItems: "center", gap: 6 }}>
          <span>{">"}</span>
          <span>Running analysis</span>
          <span style={{ animation: "blink 1s step-end infinite" }}>_</span>
        </div>
      ) : null}
    </div>
  )
}
