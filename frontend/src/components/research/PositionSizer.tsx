import { useState, useEffect } from "react"
import { T } from "../../theme"

const LS_ACCOUNT = "ps_account_size"
const LS_RISK    = "ps_risk_pct"

const inputStyle: React.CSSProperties = {
  width: "100%", background: T.surface, border: `1px solid ${T.border}`,
  borderRadius: 6, padding: "6px 8px", color: T.text, fontSize: 13,
  fontFamily: T.mono, outline: "none", boxSizing: "border-box",
}

function Field({
  label, value, onChange, prefix, suffix, step = 1, min = 0, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void
  prefix?: string; suffix?: string; step?: number; min?: number; placeholder?: string
}) {
  return (
    <div>
      <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3, fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        {prefix && <span style={{ position: "absolute", left: 8, fontSize: 12, color: T.text3, pointerEvents: "none" }}>{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={e => onChange(e.target.value)}
          step={step}
          min={min}
          placeholder={placeholder}
          style={{ ...inputStyle, paddingLeft: prefix ? 18 : 8, paddingRight: suffix ? 22 : 8 }}
        />
        {suffix && <span style={{ position: "absolute", right: 8, fontSize: 12, color: T.text3, pointerEvents: "none" }}>{suffix}</span>}
      </div>
    </div>
  )
}

function ResultCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: T.surface2, borderRadius: 8, padding: "8px 12px", border: `1px solid ${T.border}` }}>
      <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 600, color: color || T.text, fontFamily: T.mono }}>{value}</div>
    </div>
  )
}

interface Props {
  currentPrice: number
}

export function PositionSizer({ currentPrice }: Props) {
  const [account, setAccount] = useState(() => localStorage.getItem(LS_ACCOUNT) || "25000")
  const [riskPct, setRiskPct] = useState(() => localStorage.getItem(LS_RISK)    || "1")
  const [entry,   setEntry]   = useState(currentPrice.toFixed(2))
  const [stop,    setStop]    = useState((currentPrice * 0.97).toFixed(2))
  const [target,  setTarget]  = useState("")

  // Reset entry + stop when the searched stock changes
  useEffect(() => {
    setEntry(currentPrice.toFixed(2))
    setStop((currentPrice * 0.97).toFixed(2))
    setTarget("")
  }, [currentPrice])

  // Persist account size and risk % across sessions
  useEffect(() => { localStorage.setItem(LS_ACCOUNT, account) }, [account])
  useEffect(() => { localStorage.setItem(LS_RISK,    riskPct) }, [riskPct])

  const acc      = parseFloat(account) || 0
  const risk     = parseFloat(riskPct) || 0
  const entryN   = parseFloat(entry)   || 0
  const stopN    = parseFloat(stop)    || 0
  const targetN  = parseFloat(target)  || 0

  const stopDist     = entryN - stopN
  const maxRisk$     = acc * (risk / 100)
  const shares       = stopDist > 0.001 && maxRisk$ > 0 ? Math.floor(maxRisk$ / stopDist) : 0
  const actualRisk$  = shares * stopDist
  const actualRiskPct = acc > 0 ? (actualRisk$ / acc) * 100 : 0
  const posValue     = shares * entryN
  const posPct       = acc > 0 ? (posValue / acc) * 100 : 0
  const rr           = targetN > entryN && stopDist > 0.001 ? (targetN - entryN) / stopDist : null

  const valid = shares > 0

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* Input grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(105px, 1fr))", gap: 8 }}>
        <Field label="Account"      value={account} onChange={setAccount} prefix="$" step={1000} min={1000} />
        <Field label="Risk %"       value={riskPct} onChange={setRiskPct} suffix="%" step={0.1}  min={0.1} />
        <Field label="Entry"        value={entry}   onChange={setEntry}   prefix="$" step={0.01} min={0.01} />
        <Field label="Stop Loss"    value={stop}    onChange={setStop}    prefix="$" step={0.01} min={0.01} />
        <Field label="Target (opt)" value={target}  onChange={setTarget}  prefix="$" step={0.01} min={0} placeholder="—" />
      </div>

      {!valid && (
        <div style={{ fontSize: 12, color: T.text3, fontFamily: T.mono, padding: "6px 10px", background: T.surface2, borderRadius: 6, border: `1px solid ${T.border}` }}>
          {stopDist <= 0.001 ? "Stop must be below entry price." : "Enter account size and risk % to calculate."}
        </div>
      )}

      {valid && (
        <>
          {/* Summary line */}
          <div style={{
            fontSize: 13, color: T.text2, fontFamily: T.mono,
            background: T.surface2, borderRadius: 8, padding: "8px 12px",
            border: `1px solid ${T.border}`,
          }}>
            Risk{" "}
            <span style={{ color: T.red, fontWeight: 600 }}>${actualRisk$.toFixed(0)}</span>
            {" "}({actualRiskPct.toFixed(2)}% of ${acc >= 1000 ? (acc / 1000).toFixed(0) + "k" : acc.toFixed(0)})
            {" "}→{" "}
            <span style={{ color: T.text, fontWeight: 700 }}>{shares.toLocaleString()} shares max</span>
          </div>

          {/* Result cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(105px, 1fr))", gap: 8 }}>
            <ResultCard label="Shares"     value={shares.toLocaleString()} />
            <ResultCard label="$ Risk"     value={`$${actualRisk$.toFixed(0)}`}                     color={T.red} />
            <ResultCard label="Position $" value={`$${posValue >= 1000 ? (posValue / 1000).toFixed(1) + "k" : posValue.toFixed(0)}`} />
            <ResultCard label="% Portfolio" value={`${posPct.toFixed(1)}%`}                         color={posPct > 25 ? T.red : posPct > 10 ? T.amber : T.green} />
            {rr !== null && (
              <ResultCard label="R/R" value={`${rr.toFixed(1)}:1`} color={rr >= 2 ? T.green : rr >= 1 ? T.amber : T.red} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
