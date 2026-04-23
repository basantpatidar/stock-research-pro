import { useStore } from "../../store"

const TOOL_LABELS: Record<string, string> = {
  get_price: "Fetching price data",
  get_technicals: "Computing technical indicators",
  get_news_impact: "Analyzing recent news",
  get_sentiment: "Checking social sentiment",
  get_analyst_consensus: "Reviewing analyst ratings",
  get_earnings: "Checking earnings history",
  get_fundamentals: "Fetching fundamentals",
  get_options_signals: "Analyzing options flow",
  get_insider_activity: "Checking insider trades",
  get_institutional_changes: "Reviewing institutional activity",
  get_short_interest: "Checking short interest",
  get_geopolitical_events: "Scanning geopolitical events",
  get_macro_environment: "Assessing macro environment",
  get_sector_heatmap: "Building sector heatmap",
  get_cascade_impact: "Analyzing cascade effects",
  get_price_forecast: "Generating price forecast",
  get_risk_reward: "Calculating risk/reward",
  get_convergence_score: "Computing signal score",
  get_trends: "Checking Google Trends",
}

export function StreamPanel() {
  const { streamEvents, isStreaming } = useStore()

  if (!streamEvents.length && !isStreaming) return null

  return (
    <div style={{ background: "#fff", border: "0.5px solid #e5e7eb", borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>Agent reasoning</span>
        {isStreaming && (
          <span style={{ fontSize: 11, color: "#6b7280", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#16a34a", display: "inline-block", animation: "pulse 1s infinite" }} />
            Running...
          </span>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 280, overflowY: "auto" }}>
        {streamEvents.map((event, i) => {
          if (event.type === "tool_call") {
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#374151", padding: "4px 0" }}>
                <span style={{ color: "#2563eb", fontSize: 14 }}>→</span>
                <span>{TOOL_LABELS[event.tool] || event.tool}</span>
              </div>
            )
          }
          if (event.type === "tool_result") {
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#16a34a", padding: "4px 0" }}>
                <span style={{ fontSize: 14 }}>✓</span>
                <span>{TOOL_LABELS[event.tool] || event.tool} — done</span>
              </div>
            )
          }
          if (event.type === "reasoning") {
            return (
              <div key={i} style={{ fontSize: 12, color: "#374151", lineHeight: 1.6, padding: "6px 0", borderTop: "0.5px solid #f3f4f6", marginTop: 4 }}>
                {event.content}
              </div>
            )
          }
          if (event.type === "done") {
            return (
              <div key={i} style={{ fontSize: 12, color: "#16a34a", fontWeight: 500, padding: "4px 0" }}>
                Research complete
              </div>
            )
          }
          return null
        })}
      </div>
    </div>
  )
}
