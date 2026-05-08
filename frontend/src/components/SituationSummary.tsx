import { useState } from "react"
import { T } from "../theme"
import scenariosRaw from "../data/scenarios.json"

type ScenarioType = "buy" | "no_buy" | "prep" | "sell" | "hold" | "neutral"

interface Scenario {
  type: ScenarioType
  headline: string
  summary: string
  action: string
  risk_note: string
}

const scenarios = scenariosRaw as Record<string, Scenario>

const TYPE_CONFIG: Record<ScenarioType, { border: string; bg: string; label: string; labelColor: string }> = {
  buy:     { border: T.green,  bg: "rgba(16,185,129,0.07)",  label: "BUY SIGNAL",  labelColor: T.green },
  no_buy:  { border: T.amber,  bg: "rgba(245,158,11,0.07)",  label: "STAND BY",    labelColor: T.amber },
  prep:    { border: T.blue,   bg: "rgba(59,130,246,0.07)",  label: "PREPARE",     labelColor: T.blue },
  sell:    { border: T.red,    bg: "rgba(239,68,68,0.07)",   label: "SELL SIGNAL", labelColor: T.red },
  hold:    { border: T.green,  bg: "rgba(16,185,129,0.05)",  label: "HOLD",        labelColor: T.green },
  neutral: { border: T.text3,  bg: "transparent",            label: "",            labelColor: T.text3 },
}

interface SituationSummaryProps {
  scenarioKey: string | null
  compact?: boolean
}

export function SituationSummary({ scenarioKey, compact = false }: SituationSummaryProps) {
  const [expanded, setExpanded] = useState(!compact)
  const key = scenarioKey && scenarios[scenarioKey] ? scenarioKey : "waiting"
  const scenario = scenarios[key]
  const cfg = TYPE_CONFIG[scenario.type] || TYPE_CONFIG.neutral

  return (
    <div style={{
      borderLeft: `3px solid ${cfg.border}`,
      background: cfg.bg,
      borderRadius: "0 8px 8px 0",
      padding: compact ? "8px 12px" : "12px 16px",
      marginBottom: 12,
    }}>
      <div
        style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", cursor: compact ? "pointer" : "default", gap: 8 }}
        onClick={() => compact && setExpanded(e => !e)}
      >
        <div style={{ flex: 1 }}>
          {cfg.label && (
            <div style={{ fontSize: 9, fontWeight: 700, color: cfg.labelColor, letterSpacing: "0.12em", marginBottom: 4 }}>
              {cfg.label}
            </div>
          )}
          <div style={{ fontSize: compact ? 12 : 13, fontWeight: 600, color: T.text, lineHeight: 1.4 }}>
            {scenario.headline}
          </div>
        </div>
        {compact && (
          <span style={{ color: T.text3, fontSize: 11, flexShrink: 0, marginTop: 2 }}>
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </div>

      {(!compact || expanded) && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.65, marginBottom: 10 }}>
            {scenario.summary}
          </div>
          <div style={{ fontSize: 11, lineHeight: 1.5, marginBottom: 7 }}>
            <span style={{ color: cfg.border, fontWeight: 600 }}>What to do: </span>
            <span style={{ color: T.text2 }}>{scenario.action}</span>
          </div>
          <div style={{
            fontSize: 11, color: T.text3,
            borderTop: `1px solid ${T.border}`, paddingTop: 7, marginTop: 4,
          }}>
            {scenario.risk_note}
          </div>
        </div>
      )}
    </div>
  )
}
