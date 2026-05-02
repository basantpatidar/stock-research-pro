import type {
  OptionsIntelligenceResult,
  Verdict,
  CompositeVerdict,
  SignalResult,
  GEXLevel,
  TermPoint,
} from "../../types"

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

// ── Shared sub-components ─────────────────────────────────────────────────────

function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
  const s = VERDICT_STYLE[verdict]
  const fontSize = size === "lg" ? "1rem" : size === "md" ? "0.8rem" : "0.7rem"
  const padding  = size === "lg" ? "6px 14px" : size === "md" ? "4px 10px" : "3px 8px"
  return (
    <span style={{
      color: s.color, background: s.bg, border: `1px solid ${s.color}40`,
      borderRadius: 4, fontFamily: "monospace", fontWeight: 700,
      fontSize, padding, letterSpacing: "0.05em", whiteSpace: "nowrap",
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
  const dirIcon  = DIRECTION_ICON[signal.direction] || ""
  const dirColor = signal.direction === "IMPROVING" ? "#22cc66"
    : signal.direction === "DETERIORATING" ? "#ff6644" : "#888"

  return (
    <div style={{
      border: `1px solid ${s.color}30`, borderLeft: `3px solid ${s.color}`,
      borderRadius: 6, padding: "14px 16px", background: s.bg, marginBottom: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 6 }}>
        <span style={{ color: "#ccc", fontWeight: 600, fontSize: "0.85rem" }}>{title}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {signal.direction_note && (
            <span style={{ color: dirColor, fontSize: "0.75rem" }}>{dirIcon} {signal.direction_note}</span>
          )}
          <VerdictBadge verdict={signal.verdict} size="sm" />
          <ConvictionDots conviction={signal.conviction} />
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        {signal.value !== null && (
          <span style={{ color: s.color, fontFamily: "monospace", fontWeight: 700, fontSize: "1.1rem", marginRight: 10 }}>
            {signal.value}
          </span>
        )}
        <span style={{ color: "#ddd", fontSize: "0.85rem", fontWeight: 500 }}>{signal.headline}</span>
      </div>

      <p style={{ color: "#aaa", fontSize: "0.8rem", lineHeight: 1.5, margin: "0 0 8px" }}>{signal.why}</p>

      {extra}

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

// ── Options-specific extras ───────────────────────────────────────────────────

function GEXBar({ netGex, callGex, putGex, flipLevel, topLevels }: {
  netGex: number; callGex: number; putGex: number;
  flipLevel: number | null; topLevels: GEXLevel[]
}) {
  const isPositive = netGex >= 0
  const total = callGex + putGex
  const callPct = total > 0 ? (callGex / total) * 100 : 50
  const netM = (netGex / 1e6).toFixed(0)

  return (
    <div style={{ margin: "8px 0" }}>
      {/* Call vs Put GEX split bar */}
      <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginBottom: 4 }}>
        <div style={{ width: `${callPct}%`, background: "#22cc66", transition: "width 0.4s ease" }} />
        <div style={{ flex: 1, background: "#ff6644" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#555", marginBottom: 6 }}>
        <span style={{ color: "#22cc6680" }}>Call GEX ${(callGex / 1e6).toFixed(0)}M</span>
        <span style={{ color: isPositive ? "#22cc66" : "#ff6644", fontWeight: 600 }}>
          Net {isPositive ? "+" : ""}{netM}M
        </span>
        <span style={{ color: "#ff664480" }}>Put GEX ${(putGex / 1e6).toFixed(0)}M</span>
      </div>

      {/* Key levels */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: flipLevel ? 6 : 0 }}>
        {topLevels.slice(0, 4).map(({ strike, gex }) => (
          <span key={strike} style={{
            fontSize: "0.68rem", padding: "2px 7px", borderRadius: 3,
            background: gex >= 0 ? "rgba(34,204,102,0.12)" : "rgba(255,102,68,0.12)",
            color: gex >= 0 ? "#22cc66" : "#ff6644",
            border: `1px solid ${gex >= 0 ? "#22cc6630" : "#ff664430"}`,
            fontFamily: "monospace",
          }}>
            ${strike} ({gex >= 0 ? "+" : ""}{(gex / 1e6).toFixed(0)}M)
          </span>
        ))}
      </div>

      {flipLevel != null && (
        <div style={{ fontSize: "0.7rem", color: "#888", marginTop: 4 }}>
          GEX flip level: <span style={{ color: "#ffaa00", fontFamily: "monospace", fontWeight: 600 }}>${flipLevel}</span>
          {" — price crossing this triggers vol regime change"}
        </div>
      )}
    </div>
  )
}

function IVGauge({ ratio }: { ratio: number }) {
  const pct = Math.min(Math.max(((ratio - 0.5) / 1.5) * 100, 0), 100)
  const color = ratio > 1.3 ? "#ff6644" : ratio < 0.8 ? "#22cc66" : "#ffaa00"
  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ position: "relative", height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: "20%",  top: 0, bottom: 0, width: 1, background: "#22cc6650" }} />
        <div style={{ position: "absolute", left: "53.3%", top: 0, bottom: 0, width: 1, background: "#ff664450" }} />
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#555", marginTop: 3 }}>
        <span style={{ color: "#22cc6670" }}>CHEAP &lt;0.8×</span>
        <span>FAIR</span>
        <span style={{ color: "#ff664470" }}>EXPENSIVE &gt;1.3×</span>
      </div>
    </div>
  )
}

function SkewBar({ skewPct }: { skewPct: number }) {
  const clamped = Math.max(0, Math.min(20, skewPct))
  const pct     = (clamped / 20) * 100
  const color   = skewPct > 8 ? "#ff2222" : skewPct > 4 ? "#ff6644" : skewPct < 1 ? "#22cc66" : "#ffaa00"
  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ position: "relative", height: 8, background: "#1a1a1a", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: "20%", top: 0, bottom: 0, width: 1, background: "#ffaa0040" }} />
        <div style={{ position: "absolute", left: "40%", top: 0, bottom: 0, width: 1, background: "#ff664440" }} />
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#555", marginTop: 3 }}>
        <span style={{ color: "#22cc6670" }}>NEUTRAL &lt;1%</span>
        <span style={{ color: "#ffaa0070" }}>ELEVATED 4%</span>
        <span style={{ color: "#ff222270" }}>HEAVY &gt;8%</span>
      </div>
    </div>
  )
}

function TermTable({ term }: { term: TermPoint[] }) {
  if (!term || term.length === 0) return null
  const maxIV = Math.max(...term.map(t => t.atm_iv_pct))
  return (
    <div style={{ margin: "8px 0", display: "flex", flexDirection: "column", gap: 4 }}>
      {term.map((t, i) => {
        const barPct = (t.atm_iv_pct / maxIV) * 100
        const isNear = i === 0
        const isFar  = i === term.length - 1
        const barColor = isNear && term[0].atm_iv_pct > term[term.length - 1].atm_iv_pct + 3
          ? "#ff6644" : "#4488ff"
        return (
          <div key={t.expiry} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              fontSize: "0.68rem", fontFamily: "monospace", color: isNear || isFar ? "#ccc" : "#666",
              width: 86, flexShrink: 0,
            }}>
              {t.expiry}{isNear ? " ←near" : isFar ? " ←far" : ""}
            </span>
            <div style={{ flex: 1, height: 6, background: "#1a1a1a", borderRadius: 3, overflow: "hidden" }}>
              <div style={{ width: `${barPct}%`, height: "100%", background: barColor, borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "#aaa", width: 44, textAlign: "right" }}>
              {t.atm_iv_pct}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

function OverallVerdict({ composite, spotPrice, nearestExpiry }: {
  composite: CompositeVerdict; spotPrice: number; nearestExpiry: string
}) {
  const s = VERDICT_STYLE[composite.verdict]
  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.color}50`, borderRadius: 8,
      padding: "16px 20px", marginBottom: 20,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexWrap: "wrap", gap: 12,
    }}>
      <div>
        <div style={{ color: "#888", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
          Options Intelligence — Overall Verdict
        </div>
        <VerdictBadge verdict={composite.verdict} size="lg" />
        <ConvictionDots conviction={composite.conviction} />
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ color: s.color, fontFamily: "monospace", fontSize: "1.4rem", fontWeight: 700 }}>
          {composite.score > 0 ? "+" : ""}{composite.score.toFixed(2)}
        </div>
        <div style={{ color: "#666", fontSize: "0.72rem" }}>
          {composite.agree_count} of {composite.signal_count} signals agree
        </div>
        <div style={{ color: "#555", fontSize: "0.68rem", fontFamily: "monospace", marginTop: 2 }}>
          Near expiry {nearestExpiry} · Spot ${spotPrice.toFixed(2)}
        </div>
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface Props {
  data: OptionsIntelligenceResult
}

export default function OptionsIntelligencePanel({ data }: Props) {
  if (!data || (data as any).error) {
    return (
      <div style={{ color: "#ff6644", padding: 16, fontSize: "0.85rem" }}>
        {(data as any)?.error ?? "Could not compute options intelligence data."}
      </div>
    )
  }

  return (
    <div style={{ padding: "4px 0" }}>
      <OverallVerdict
        composite={data.composite}
        spotPrice={data.spot_price}
        nearestExpiry={data.nearest_expiry}
      />

      {data.gex?.signal && (
        <SignalCard
          title="GEX (Gamma Exposure) — Market Maker Vol Regime"
          signal={data.gex.signal}
          extra={
            <GEXBar
              netGex={data.gex.net_gex}
              callGex={data.gex.call_gex}
              putGex={data.gex.put_gex}
              flipLevel={data.gex.flip_level}
              topLevels={data.gex.top_levels}
            />
          }
        />
      )}

      {data.max_pain?.signal && (
        <SignalCard
          title="Max Pain — Option Seller Target Price"
          signal={data.max_pain.signal}
        />
      )}

      {data.iv_analysis?.signal && (
        <SignalCard
          title="IV vs Realized Vol — Option Premium Richness"
          signal={data.iv_analysis.signal}
          extra={
            data.iv_analysis.iv_rv_ratio != null
              ? <IVGauge ratio={data.iv_analysis.iv_rv_ratio} />
              : undefined
          }
        />
      )}

      {data.skew?.signal && (
        <SignalCard
          title="Put/Call Skew — Downside Hedging Pressure"
          signal={data.skew.signal}
          extra={
            data.skew.skew_pct != null
              ? <SkewBar skewPct={data.skew.skew_pct} />
              : undefined
          }
        />
      )}

      {data.term_structure?.signal && (
        <SignalCard
          title="Volatility Term Structure — Near vs Far IV"
          signal={data.term_structure.signal}
          extra={<TermTable term={data.term_structure.term} />}
        />
      )}

      <div style={{ fontSize: "0.68rem", color: "#444", marginTop: 8, lineHeight: 1.4 }}>
        GEX uses Black-Scholes gamma from yfinance options chains. Assumes dealers are short both calls and puts.
        Not financial advice.
      </div>
    </div>
  )
}
