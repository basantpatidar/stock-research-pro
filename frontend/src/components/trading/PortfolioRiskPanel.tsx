/**
 * Portfolio Risk Panel — read-only exposure view derived entirely from data
 * the portfolio page already fetches (positions + open orders). No new API
 * call, no backend changes, no broker round-trip beyond the existing poll.
 *
 * The numbers it surfaces:
 *   - Total exposure: Σ(market_value) across positions
 *   - Concentration: weight % of each position; largest position called out
 *   - Max loss if every stop hits: Σ(qty × (avg_entry − stop_price)) over
 *     positions that have an open stop order; positions WITHOUT a stop are
 *     flagged separately so the user knows their loss exposure is uncapped.
 *
 * Why this matters during auto-paper-trade: the subscriber can open up to 50
 * orders/day. A scanner glitch that picks 30 correlated tickers would show
 * up here as 100% in one sector long before max-loss-if-stops-hit becomes
 * scary — call it out visually and the user can hit the kill switch.
 */
import { useMemo } from "react"
import { T, chgColor } from "../../theme"
import type { BrokerOrder, BrokerPosition } from "../../types/index"

const fmt$ = (v: number) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const fmtPct = (v: number) => `${v >= 0 ? "" : ""}${v.toFixed(1)}%`


interface Props {
  positions: BrokerPosition[]
  openOrders: BrokerOrder[]
  equity: number  // for "% of portfolio" — uses equity not just position sum so cash is honoured
}

interface PerSymbolRisk {
  symbol: string
  qty: number
  market_value: number
  weight_pct: number       // % of equity
  stop_price: number | null
  max_loss_to_stop: number | null  // null = no stop = uncapped
  unrealized_pl: number
  unrealized_pl_pct: number
}


export function PortfolioRiskPanel({ positions, openOrders, equity }: Props) {
  const risk = useMemo(() => {
    // Build a stop lookup from open orders. A position's stop comes from any
    // open SELL order with stop_price set on the same symbol (bracket exits
    // are submitted as sell-stop). If multiple, take the highest stop_price
    // (tightest stop loss) — conservative choice for risk display.
    const stops: Record<string, number> = {}
    for (const o of openOrders) {
      if (o.side === "sell" && o.stop_price != null && o.stop_price > 0) {
        const cur = stops[o.symbol]
        stops[o.symbol] = cur != null ? Math.max(cur, o.stop_price) : o.stop_price
      }
    }

    const totalMv = positions.reduce((acc, p) => acc + p.market_value, 0)
    const denom   = Math.max(equity, totalMv, 1)  // avoid /0 when equity load is racing

    const rows: PerSymbolRisk[] = positions.map((p) => {
      const stop = stops[p.symbol] ?? null
      const lossIfStopHit = stop != null
        ? Math.max(0, (p.avg_entry_price - stop) * Math.abs(p.qty))
        : null
      return {
        symbol: p.symbol,
        qty: p.qty,
        market_value: p.market_value,
        weight_pct: (p.market_value / denom) * 100,
        stop_price: stop,
        max_loss_to_stop: lossIfStopHit,
        unrealized_pl: p.unrealized_pl,
        unrealized_pl_pct: p.unrealized_pl_pct,
      }
    }).sort((a, b) => b.market_value - a.market_value)

    const positionsWithStops    = rows.filter((r) => r.max_loss_to_stop != null)
    const positionsWithoutStops = rows.filter((r) => r.max_loss_to_stop == null)
    const maxLossIfAllStopsHit  = positionsWithStops.reduce((acc, r) => acc + (r.max_loss_to_stop ?? 0), 0)

    return {
      rows,
      totalMv,
      maxLossIfAllStopsHit,
      maxLossPctOfEquity: equity > 0 ? (maxLossIfAllStopsHit / equity) * 100 : 0,
      positionsWithoutStops,
      largest: rows[0] ?? null,
    }
  }, [positions, openOrders, equity])

  if (positions.length === 0) return null

  // Concentration warning if the biggest position is >40% of equity OR
  // there are uncovered (no-stop) positions. Either condition deserves
  // immediate eyeball attention.
  const concentrationWarn = (risk.largest && risk.largest.weight_pct >= 40)
  const stopWarn = risk.positionsWithoutStops.length > 0
  const warn = concentrationWarn || stopWarn

  return (
    <section style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 10 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>
          Risk
        </h2>
        {warn && (
          <span style={{
            fontSize: 11, fontFamily: T.mono, fontWeight: 600,
            padding: "2px 8px", borderRadius: 4,
            background: T.amberDim, color: T.amber, border: `1px solid ${T.amber}`,
          }}>
            REVIEW
          </span>
        )}
      </div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
        <RiskStat
          label="Total Exposure"
          value={fmt$(risk.totalMv)}
          sub={equity > 0 ? `${((risk.totalMv / equity) * 100).toFixed(0)}% of equity` : undefined}
        />
        <RiskStat
          label="Positions"
          value={String(positions.length)}
          sub={`Largest: ${risk.largest?.symbol ?? "—"} @ ${risk.largest ? risk.largest.weight_pct.toFixed(0) : 0}%`}
          subColor={concentrationWarn ? T.amber : undefined}
        />
        <RiskStat
          label="Max Loss if All Stops Hit"
          value={fmt$(risk.maxLossIfAllStopsHit)}
          sub={`${risk.maxLossPctOfEquity.toFixed(1)}% of equity`}
          valueColor={T.red}
        />
        <RiskStat
          label="Uncovered Positions"
          value={String(risk.positionsWithoutStops.length)}
          sub={stopWarn ? risk.positionsWithoutStops.map((p) => p.symbol).join(", ") : "All have stops"}
          subColor={stopWarn ? T.amber : T.green}
        />
      </div>

      {/* Per-symbol risk table */}
      <div style={{
        border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden",
        background: T.surface,
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: T.surface2, color: T.text3, fontWeight: 500, letterSpacing: "0.04em" }}>
              <th style={th}>Symbol</th>
              <th style={thR}>Qty</th>
              <th style={thR}>Market Value</th>
              <th style={thR}>Weight</th>
              <th style={thR}>Unrealized</th>
              <th style={thR}>Stop</th>
              <th style={thR}>Max Loss to Stop</th>
            </tr>
          </thead>
          <tbody>
            {risk.rows.map((r) => {
              const heavy = r.weight_pct >= 25
              return (
                <tr key={r.symbol} style={{ borderTop: `1px solid ${T.border}` }}>
                  <td style={{ ...td, fontWeight: 600 }}>{r.symbol}</td>
                  <td style={tdR}>{r.qty}</td>
                  <td style={tdR}>{fmt$(r.market_value)}</td>
                  <td style={{ ...tdR, color: heavy ? T.amber : T.text }}>{fmtPct(r.weight_pct)}</td>
                  <td style={{ ...tdR, color: chgColor(r.unrealized_pl) }}>
                    {fmt$(r.unrealized_pl)} ({r.unrealized_pl_pct >= 0 ? "+" : ""}{r.unrealized_pl_pct.toFixed(2)}%)
                  </td>
                  <td style={tdR}>
                    {r.stop_price != null ? fmt$(r.stop_price) : (
                      <span style={{ color: T.amber }}>—</span>
                    )}
                  </td>
                  <td style={{ ...tdR, color: r.max_loss_to_stop != null ? T.red : T.amber }}>
                    {r.max_loss_to_stop != null ? fmt$(r.max_loss_to_stop) : "uncapped"}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}


function RiskStat({ label, value, sub, valueColor, subColor }: {
  label: string
  value: string
  sub?: string
  valueColor?: string
  subColor?: string
}) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10,
      padding: "10px 14px",
    }}>
      <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: T.mono, color: valueColor || T.text }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: subColor || T.text2, marginTop: 2 }}>{sub}</div>
      )}
    </div>
  )
}


const th = { textAlign: "left" as const, padding: "8px 12px", fontSize: 10, textTransform: "uppercase" as const }
const thR = { ...th, textAlign: "right" as const }
const td = { padding: "8px 12px", fontFamily: "var(--font-mono)", color: "var(--color-text)" }
const tdR = { ...td, textAlign: "right" as const }
