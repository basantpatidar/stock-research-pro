import { T } from "../../theme"
import type { ValuationResult } from "../../types"

const Label = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>{children}</div>
)

const Stat = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div style={{ background: T.surface2, borderRadius: 8, padding: "10px 12px", border: `1px solid ${T.border}` }}>
    <Label>{label}</Label>
    <div style={{ fontSize: 16, fontWeight: 500, fontFamily: T.mono, color: color || T.text }}>{value}</div>
  </div>
)

function verdictColor(c: string) {
  if (c === "green") return T.green
  if (c === "red")   return T.red
  return T.text2
}

export function ValuationPanel({ data }: { data: ValuationResult }) {
  if (data.error) return <div style={{ color: T.red, fontSize: 12 }}>{data.error}</div>

  const price = data.current_price

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

      {/* DCF */}
      {data.dcf_per_share && Object.keys(data.dcf_per_share).length > 0 && (
        <div>
          <Label>DCF Intrinsic Value (growth: {data.dcf_growth_assumed_pct}%, WACC: {data.dcf_wacc_pct}%)</Label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {(["bear", "base", "bull"] as const).map((s) => {
              const val = (data.dcf_per_share as any)[s]
              if (val == null) return null
              const c = price ? (val > price * 1.1 ? T.green : val < price * 0.9 ? T.red : T.text2) : T.text2
              return <Stat key={s} label={`${s} case`} value={`$${val.toFixed(0)}`} color={c} />
            })}
          </div>
        </div>
      )}

      {/* Graham + PEG */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px,1fr))", gap: 8 }}>
        {data.graham_number != null && (
          <Stat
            label="Graham Number"
            value={`$${data.graham_number.toFixed(0)}`}
            color={price ? (data.graham_number > price ? T.green : T.red) : T.text2}
          />
        )}
        {data.peg_fair_value != null && (
          <Stat label="PEG Fair Value" value={`$${data.peg_fair_value.toFixed(0)}`} />
        )}
        {price != null && <Stat label="Current Price" value={`$${price.toFixed(2)}`} />}
        {data.revenue_cagr_pct != null && (
          <Stat label="Revenue CAGR" value={`${data.revenue_cagr_pct}%`} color={data.revenue_cagr_pct > 0 ? T.green : T.red} />
        )}
      </div>

      {/* Peer verdict */}
      {data.peer_verdict && (
        <div style={{
          padding: "9px 13px", borderRadius: 8,
          background: `${verdictColor(data.peer_verdict_color)}18`,
          border: `1px solid ${verdictColor(data.peer_verdict_color)}`,
        }}>
          <span style={{ fontSize: 12, color: verdictColor(data.peer_verdict_color), fontWeight: 500 }}>
            {data.peer_verdict}
          </span>
          {data.peer_median_pe != null && (
            <span style={{ fontSize: 11, color: T.text3, marginLeft: 8 }}>
              peer median P/E: {data.peer_median_pe}x
            </span>
          )}
        </div>
      )}

      {/* Peer table */}
      {data.peers?.length > 0 && (
        <div>
          <Label>Peer Comparables</Label>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Ticker", "P/E", "P/S", "EV/EBITDA", "PEG", "Mkt Cap"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "4px 8px", color: T.text3, fontWeight: 500, borderBottom: `1px solid ${T.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.peers.map(p => (
                  <tr key={p.ticker} style={{ borderBottom: `1px solid ${T.border}` }}>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.blue }}>{p.ticker}</td>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.text2 }}>{p.pe_ratio?.toFixed(1) ?? "—"}</td>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.text2 }}>{p.ps_ratio?.toFixed(1) ?? "—"}</td>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.text2 }}>{p.ev_ebitda?.toFixed(1) ?? "—"}</td>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.text2 }}>{p.peg_ratio?.toFixed(1) ?? "—"}</td>
                    <td style={{ padding: "5px 8px", fontFamily: T.mono, color: T.text2 }}>{p.market_cap_b != null ? `$${p.market_cap_b}B` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
