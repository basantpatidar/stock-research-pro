import type { EarningsQualityResult, Verdict, CompositeVerdict, SignalResult } from "../../types"

// ── Verdict styling ───────────────────────────────────────────────────────────

const VERDICT_STYLE: Record<Verdict, { color: string; bg: string; label: string }> = {
  STRONG_BUY: { color: "#00ff88", bg: "rgba(0,255,136,0.12)", label: "▲▲ STRONG BUY" },
  BUY:        { color: "#22cc66", bg: "rgba(34,204,102,0.12)", label: "▲ BUY" },
  HOLD:       { color: "#ffaa00", bg: "rgba(255,170,0,0.12)",  label: "→ HOLD" },
  SELL:       { color: "#ff6644", bg: "rgba(255,102,68,0.12)", label: "▼ SELL" },
  AVOID:      { color: "#ff2222", bg: "rgba(255,34,34,0.12)",  label: "▼▼ AVOID" },
  RISK_FLAG:  { color: "#ff4400", bg: "rgba(255,68,0,0.15)",   label: "⚠ RISK" },
}

const DIRECTION_ICON: Record<string, string> = {
  IMPROVING:    "↑",
  DETERIORATING:"↓",
  STABLE:       "→",
  UNKNOWN:      "",
}

// ── Sub-components ────────────────────────────────────────────────────────────

function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
  const s = VERDICT_STYLE[verdict]
  const fontSize = size === "lg" ? "1rem" : size === "md" ? "0.8rem" : "0.7rem"
  const padding  = size === "lg" ? "6px 14px" : size === "md" ? "4px 10px" : "3px 8px"
  return (
    <span style={{
      color: s.color,
      background: s.bg,
      border: `1px solid ${s.color}40`,
      borderRadius: 4,
      fontFamily: "monospace",
      fontWeight: 700,
      fontSize,
      padding,
      letterSpacing: "0.05em",
      whiteSpace: "nowrap",
    }}>
      {s.label}
    </span>
  )
}

function ConvictionDots({ conviction }: { conviction: string }) {
  const levels: Record<string, number> = { HIGH: 3, MODERATE: 2, LOW: 1, MIXED: 1 }
  const filled = levels[conviction] ?? 1
  return (
    <span style={{ fontSize: "0.7rem", color: "#888", marginLeft: 6 }}>
      {[1, 2, 3].map(i => (
        <span key={i} style={{ color: i <= filled ? "#ffaa00" : "#333", marginRight: 2 }}>●</span>
      ))}
      <span style={{ marginLeft: 4 }}>{conviction}</span>
    </span>
  )
}

function SignalCard({ title, signal, extra }: { title: string; signal: SignalResult; extra?: React.ReactNode }) {
  const s = VERDICT_STYLE[signal.verdict]
  const dirIcon = DIRECTION_ICON[signal.direction] || ""
  const dirColor = signal.direction === "IMPROVING" ? "#22cc66"
    : signal.direction === "DETERIORATING" ? "#ff6644" : "#888"

  return (
    <div style={{
      border: `1px solid ${s.color}30`,
      borderLeft: `3px solid ${s.color}`,
      borderRadius: 6,
      padding: "14px 16px",
      background: s.bg,
      marginBottom: 12,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 6 }}>
        <span style={{ color: "#ccc", fontWeight: 600, fontSize: "0.85rem" }}>{title}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {signal.direction_note && (
            <span style={{ color: dirColor, fontSize: "0.75rem" }}>
              {dirIcon} {signal.direction_note}
            </span>
          )}
          <VerdictBadge verdict={signal.verdict} size="sm" />
          <ConvictionDots conviction={signal.conviction} />
        </div>
      </div>

      {/* Value + headline */}
      <div style={{ marginBottom: 8 }}>
        {signal.value !== null && (
          <span style={{ color: s.color, fontFamily: "monospace", fontWeight: 700, fontSize: "1.1rem", marginRight: 10 }}>
            {signal.value}
          </span>
        )}
        <span style={{ color: "#ddd", fontSize: "0.85rem", fontWeight: 500 }}>{signal.headline}</span>
      </div>

      {/* Why */}
      <p style={{ color: "#aaa", fontSize: "0.8rem", lineHeight: 1.5, margin: "0 0 8px" }}>{signal.why}</p>

      {/* Extra content (checks, gauge, etc.) */}
      {extra}

      {/* Action / risk row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, borderTop: "1px solid #ffffff10", paddingTop: 8 }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <span style={{ color: "#666", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>Action</span>
          <p style={{ color: "#e0e0e0", fontSize: "0.8rem", margin: "2px 0 0" }}>{signal.action}</p>
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <span style={{ color: "#666", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>Key Risk</span>
          <p style={{ color: "#aaa", fontSize: "0.8rem", margin: "2px 0 0" }}>{signal.key_risk}</p>
        </div>
      </div>
    </div>
  )
}

function PiotroskiChecks({ checks }: { checks: Record<string, { passed: boolean; label: string }> }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
      {Object.entries(checks).map(([key, c]) => (
        <span key={key} style={{
          fontSize: "0.72rem",
          padding: "3px 8px",
          borderRadius: 3,
          background: c.passed ? "rgba(34,204,102,0.15)" : "rgba(255,68,34,0.15)",
          color: c.passed ? "#22cc66" : "#ff6644",
          border: `1px solid ${c.passed ? "#22cc6640" : "#ff664440"}`,
        }}>
          {c.passed ? "✓" : "✗"} {c.label}
        </span>
      ))}
    </div>
  )
}

function AltmanGauge({ score, zone }: { score: number; thresholds: { distress: number; grey_zone: number }; zone: string }) {
  const max = 6
  const pct = Math.min(Math.max((score / max) * 100, 0), 100)
  const color = zone === "SAFE" ? "#22cc66" : zone === "GREY" ? "#ffaa00" : "#ff2222"
  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ position: "relative", height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
        {/* Zone markers */}
        <div style={{ position: "absolute", left: "30.2%", top: 0, bottom: 0, width: 1, background: "#ff444480" }} />
        <div style={{ position: "absolute", left: "49.8%", top: 0, bottom: 0, width: 1, background: "#ffaa0080" }} />
        {/* Fill */}
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#555", marginTop: 3 }}>
        <span style={{ color: "#ff444480" }}>DISTRESS &lt;1.81</span>
        <span style={{ color: "#ffaa0080" }}>GREY 1.81–2.99</span>
        <span style={{ color: "#22cc6680" }}>SAFE &gt;2.99</span>
      </div>
    </div>
  )
}

function AccrualsBar({ ratio }: { ratio: number }) {
  const clamped = Math.max(-20, Math.min(20, ratio))
  const center = 50
  const pct = center + (clamped / 20) * 50
  const color = ratio < 0 ? "#22cc66" : ratio < 5 ? "#ffaa00" : "#ff2222"
  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ position: "relative", height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "visible" }}>
        <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "#ffffff20" }} />
        <div style={{
          position: "absolute", top: 0, height: "100%", borderRadius: 4, background: color,
          left: ratio < 0 ? `${pct}%` : "50%",
          width: `${Math.abs(clamped / 20) * 50}%`,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#555", marginTop: 3 }}>
        <span style={{ color: "#22cc6680" }}>← CASH-BACKED (good)</span>
        <span>0%</span>
        <span style={{ color: "#ff222280" }}>PAPER EARNINGS (risk) →</span>
      </div>
    </div>
  )
}

function OverallVerdict({ overall }: { overall: CompositeVerdict }) {
  const s = VERDICT_STYLE[overall.verdict]
  return (
    <div style={{
      background: s.bg,
      border: `1px solid ${s.color}50`,
      borderRadius: 8,
      padding: "16px 20px",
      marginBottom: 20,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
      gap: 12,
    }}>
      <div>
        <div style={{ color: "#888", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
          Earnings Quality — Overall Verdict
        </div>
        <VerdictBadge verdict={overall.verdict} size="lg" />
        <ConvictionDots conviction={overall.conviction} />
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ color: s.color, fontFamily: "monospace", fontSize: "1.4rem", fontWeight: 700 }}>
          {overall.score > 0 ? "+" : ""}{overall.score.toFixed(2)}
        </div>
        <div style={{ color: "#666", fontSize: "0.72rem" }}>
          {overall.agree_count} of {overall.signal_count} signals agree
        </div>
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface Props {
  data: EarningsQualityResult
}

export default function EarningsQualityPanel({ data }: Props) {
  if (!data || data.error) {
    return (
      <div style={{ color: "#ff6644", padding: 16, fontSize: "0.85rem" }}>
        Could not compute earnings quality data.
      </div>
    )
  }

  return (
    <div style={{ padding: "4px 0" }}>
      <OverallVerdict overall={data.overall} />

      <SignalCard
        title="Piotroski F-Score — Financial Strength"
        signal={data.piotroski.signal}
        extra={<PiotroskiChecks checks={data.piotroski.checks} />}
      />

      <SignalCard
        title="Beneish M-Score — Earnings Manipulation Risk"
        signal={data.beneish.signal}
      />

      <SignalCard
        title="Altman Z-Score — Bankruptcy Proximity"
        signal={data.altman.signal}
        extra={
          data.altman.score !== null
            ? <AltmanGauge score={data.altman.score} thresholds={data.altman.thresholds} zone={data.altman.zone} />
            : undefined
        }
      />

      <SignalCard
        title="Accruals Ratio — Cash vs Paper Earnings"
        signal={data.accruals.signal}
        extra={
          data.accruals.accruals_ratio_pct !== null
            ? <AccrualsBar ratio={data.accruals.accruals_ratio_pct} />
            : undefined
        }
      />

      <div style={{ fontSize: "0.68rem", color: "#444", marginTop: 8, lineHeight: 1.4 }}>
        Not financial advice. Models use trailing financial statement data — signals reflect historical patterns, not guarantees of future performance.
      </div>
    </div>
  )
}
