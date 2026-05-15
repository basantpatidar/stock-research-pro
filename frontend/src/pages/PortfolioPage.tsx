import { useEffect, useState, useCallback } from "react"
import { brokerApi } from "../services/broker"
import { useStore } from "../store"
import { T, chgColor, chgDim } from "../theme"
import type { AutoTradeStatus, BrokerOrder, BrokerPosition } from "../types/index"
import { OrderTicketModal, type TicketPrefill } from "../components/trading/OrderTicketModal"
import { PortfolioRiskPanel } from "../components/trading/PortfolioRiskPanel"

const POLL_MS = 10_000

const fmt$ = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("en-US", { style: "currency", currency: "USD" })

const fmtPct = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`

const fmtDate = (iso: string | null) => {
  if (!iso) return "—"
  const d = new Date(iso)
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}


function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, fontFamily: T.mono, color: color || T.text, marginBottom: sub ? 4 : 0 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: T.text2 }}>{sub}</div>}
    </div>
  )
}


function AutoTradePanel({ s }: { s: AutoTradeStatus }) {
  // Colors: green when on AND will fire (allowlist non-empty), amber when on
  // but allowlist empty (no-op), grey when fully off. Red when scanner halted.
  const armed = s.enabled && s.allowlist.length > 0
  const halted = s.scanner_halted
  const accent = halted ? T.red : armed ? T.green : s.enabled ? T.amber : T.text3
  const bg = halted ? T.redDim : armed ? "rgba(34,197,94,0.08)" : s.enabled ? T.amberDim : T.surface

  const lastFired = s.last_auto_order_at
    ? new Date(s.last_auto_order_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
    : null

  return (
    <div style={{
      background: bg, border: `1px solid ${accent}`, borderRadius: 10,
      padding: "10px 14px", marginBottom: 16, display: "flex",
      alignItems: "center", gap: 16, flexWrap: "wrap",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, fontFamily: T.mono, letterSpacing: "0.08em",
          padding: "2px 8px", borderRadius: 4, background: accent,
          color: halted || armed ? "#000" : T.text,
        }}>
          {halted ? "SCANNER HALTED" : armed ? "AUTO-TRADE ON" : s.enabled ? "AUTO-TRADE (NO ALLOWLIST)" : "AUTO-TRADE OFF"}
        </span>
        {s.allowlist.length > 0 && (
          <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono }}>
            allow: {s.allowlist.join(", ")}
          </span>
        )}
      </div>
      <div style={{ marginLeft: "auto", display: "flex", gap: 18, fontSize: 12, fontFamily: T.mono }}>
        <span style={{ color: T.text2 }}>
          orders today: <span style={{ color: T.text }}>{s.orders_today}/{s.daily_order_cap}</span>
        </span>
        <span style={{ color: T.text2 }}>
          signals today: <span style={{ color: T.text }}>{s.scanner_signals_today}/{s.scanner_daily_signal_cap}</span>
        </span>
        {lastFired && (
          <span style={{ color: T.text2 }}>
            last: <span style={{ color: T.text }}>{s.last_auto_order_symbol} @ {lastFired}</span>
          </span>
        )}
      </div>
    </div>
  )
}


function ModePill({ mode }: { mode: "paper" | "live" }) {
  const isPaper = mode === "paper"
  const c = isPaper ? T.amber : T.red
  return (
    <span style={{
      display: "inline-block", padding: "3px 10px", borderRadius: 20,
      background: isPaper ? T.amberDim : T.redDim, color: c, border: `1px solid ${c}`,
      fontSize: 11, fontWeight: 700, fontFamily: T.mono, letterSpacing: "0.08em",
    }}>
      {mode.toUpperCase()}
    </span>
  )
}


export function PortfolioPage() {
  const { brokerAccount, brokerStatus, positions, openOrders,
          setBrokerAccount, setBrokerStatus, setPositions, setOpenOrders } = useStore()

  const [recentFills, setRecentFills] = useState<BrokerOrder[]>([])
  const [error, setError] = useState<string | null>(null)
  const [ticket, setTicket] = useState<TicketPrefill | null>(null)
  const [autoTrade, setAutoTrade] = useState<AutoTradeStatus | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [account, pos, open, closed, at] = await Promise.all([
        brokerApi.account(),
        brokerApi.positions(),
        brokerApi.listOrders("open", 100),
        brokerApi.listOrders("closed", 50),
        brokerApi.autoTradeStatus().catch(() => null),
      ])
      setBrokerAccount(account)
      setBrokerStatus("ok")
      setPositions(pos)
      setOpenOrders(open)
      setRecentFills(closed.filter((o) => o.status === "filled"))
      setAutoTrade(at)
    } catch (e: any) {
      const status = e?.response?.status
      const bs = e?.response?.headers?.["x-broker-status"]
      if (status === 503) {
        setBrokerStatus(bs === "misconfigured" ? "misconfigured" : "unreachable")
        setError(bs === "misconfigured"
          ? "Broker not configured — set ALPACA_API_KEY and ALPACA_API_SECRET in .env, then restart the backend."
          : "Broker unreachable — Alpaca appears to be down. Existing orders are unaffected; new orders are blocked until it recovers.")
      } else {
        setError(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : e?.message || "Unknown error")
      }
    }
  }, [setBrokerAccount, setBrokerStatus, setPositions, setOpenOrders])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, POLL_MS)
    return () => clearInterval(t)
  }, [refresh])

  const dayPnl = brokerAccount && brokerAccount.last_equity != null
    ? brokerAccount.equity - brokerAccount.last_equity
    : null
  const dayPnlPct = brokerAccount && brokerAccount.last_equity
    ? (dayPnl! / brokerAccount.last_equity) * 100
    : null

  const onClosePosition = (p: BrokerPosition) => {
    setTicket({
      symbol: p.symbol,
      side: p.qty > 0 ? "sell" : "buy",
      qty: Math.abs(p.qty),
      orderType: "market",
      source: "manual",
    })
  }

  const onCancelOrder = async (id: string) => {
    if (!confirm("Cancel this order?")) return
    try {
      await brokerApi.cancelOrder(id)
      await refresh()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Cancel failed")
    }
  }

  return (
    <div style={{ padding: "1.5rem 2rem", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: T.text, margin: 0 }}>Portfolio</h1>
        {brokerAccount && <ModePill mode={brokerAccount.mode} />}
        <button
          onClick={() => setTicket({ symbol: "", side: "buy", source: "manual" })}
          disabled={brokerStatus !== "ok"}
          style={{
            marginLeft: "auto", padding: "5px 14px", fontSize: 12, fontFamily: T.mono,
            background: brokerStatus === "ok" ? T.green : T.surface2,
            color: brokerStatus === "ok" ? "#000" : T.text3,
            border: `1px solid ${brokerStatus === "ok" ? T.green : T.border}`,
            borderRadius: 6, cursor: brokerStatus === "ok" ? "pointer" : "not-allowed",
            fontWeight: 600,
          }}
        >+ New Order</button>
        <button onClick={refresh} style={{
          padding: "5px 12px", fontSize: 12, fontFamily: T.mono,
          background: T.surface2, color: T.text2, border: `1px solid ${T.border}`,
          borderRadius: 6, cursor: "pointer",
        }}>↻ Refresh</button>
      </div>
      <div style={{ fontSize: 12, color: T.text2, marginBottom: 20 }}>
        Auto-refresh every {POLL_MS / 1000}s · Polling, no WebSocket yet
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          background: brokerStatus === "misconfigured" ? T.amberDim : T.redDim,
          color: brokerStatus === "misconfigured" ? T.amber : T.red,
          border: `1px solid ${brokerStatus === "misconfigured" ? T.amber : T.red}`,
          padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>{error}</div>
      )}

      {/* Auto-trade status */}
      {autoTrade && <AutoTradePanel s={autoTrade} />}

      {/* Account header */}
      {brokerAccount && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          <StatCard label="Equity" value={fmt$(brokerAccount.equity)} />
          <StatCard label="Buying Power" value={fmt$(brokerAccount.buying_power)} />
          <StatCard label="Cash" value={fmt$(brokerAccount.cash)} />
          <StatCard
            label="Day P&L"
            value={dayPnl != null ? fmt$(dayPnl) : "—"}
            sub={dayPnlPct != null ? fmtPct(dayPnlPct) : undefined}
            color={dayPnl == null ? T.text : chgColor(dayPnl)}
          />
        </div>
      )}

      {/* Risk */}
      {brokerAccount && positions.length > 0 && (
        <PortfolioRiskPanel
          positions={positions}
          openOrders={openOrders}
          equity={brokerAccount.equity}
        />
      )}

      {/* Open Positions */}
      <Section title={`Open Positions (${positions.length})`}>
        {positions.length === 0 ? (
          <Empty text="Flat — no open positions." />
        ) : (
          <Table cols={["Symbol", "Qty", "Avg Entry", "Current", "Market Value", "Unrealized P&L", ""]}>
            {positions.map((p) => (
              <tr key={p.symbol}>
                <Td mono bold>{p.symbol}</Td>
                <Td mono>{p.qty}</Td>
                <Td mono>{fmt$(p.avg_entry_price)}</Td>
                <Td mono>{fmt$(p.current_price)}</Td>
                <Td mono>{fmt$(p.market_value)}</Td>
                <Td mono color={chgColor(p.unrealized_pl)} bg={chgDim(p.unrealized_pl)}>
                  {fmt$(p.unrealized_pl)} ({fmtPct(p.unrealized_pl_pct)})
                </Td>
                <Td>
                  <button onClick={() => onClosePosition(p)} style={btnSm(T.red)}>Close</button>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Section>

      {/* Open Orders */}
      <Section title={`Open Orders (${openOrders.length})`}>
        {openOrders.length === 0 ? (
          <Empty text="No open orders." />
        ) : (
          <Table cols={["Symbol", "Side", "Qty", "Type", "Limit", "Status", "Submitted", ""]}>
            {openOrders.map((o) => (
              <tr key={o.broker_order_id}>
                <Td mono bold>{o.symbol}</Td>
                <Td mono color={o.side === "buy" ? T.green : T.red}>{o.side.toUpperCase()}</Td>
                <Td mono>{o.qty}</Td>
                <Td mono>{o.order_type}</Td>
                <Td mono>{o.limit_price != null ? fmt$(o.limit_price) : "—"}</Td>
                <Td mono>{o.status}</Td>
                <Td mono>{fmtDate(o.submitted_at)}</Td>
                <Td>
                  <button onClick={() => onCancelOrder(o.broker_order_id)} style={btnSm(T.text2)}>Cancel</button>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Section>

      {/* Recent Fills */}
      <Section title={`Recent Fills (${recentFills.length})`}>
        {recentFills.length === 0 ? (
          <Empty text="No filled orders yet." />
        ) : (
          <Table cols={["Symbol", "Side", "Qty", "Avg Fill", "Filled At"]}>
            {recentFills.map((o) => (
              <tr key={o.broker_order_id}>
                <Td mono bold>{o.symbol}</Td>
                <Td mono color={o.side === "buy" ? T.green : T.red}>{o.side.toUpperCase()}</Td>
                <Td mono>{o.filled_qty}</Td>
                <Td mono>{fmt$(o.filled_avg_price)}</Td>
                <Td mono>{fmtDate(o.filled_at)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Section>

      {ticket && (
        <OrderTicketModal
          prefill={ticket}
          onClose={() => setTicket(null)}
          onPlaced={async () => { setTicket(null); await refresh() }}
        />
      )}
    </div>
  )
}


// ── Small layout helpers ──────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontSize: 11, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8, fontFamily: T.mono }}>
        {title}
      </div>
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
        {children}
      </div>
    </div>
  )
}

function Table({ cols, children }: { cols: string[]; children: React.ReactNode }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ background: T.surface2 }}>
          {cols.map((c) => (
            <th key={c} style={{
              padding: "8px 12px", textAlign: "left", color: T.text2,
              fontSize: 10, textTransform: "uppercase", letterSpacing: "0.07em",
              fontFamily: T.mono, fontWeight: 500, borderBottom: `1px solid ${T.border}`,
            }}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  )
}

function Td({ children, mono, bold, color, bg }: {
  children: React.ReactNode; mono?: boolean; bold?: boolean; color?: string; bg?: string
}) {
  return (
    <td style={{
      padding: "8px 12px",
      fontFamily: mono ? T.mono : T.font,
      fontWeight: bold ? 600 : 400,
      color: color || T.text,
      background: bg,
      borderBottom: `1px solid ${T.border}`,
    }}>{children}</td>
  )
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: "20px 16px", color: T.text2, fontSize: 13, textAlign: "center" }}>{text}</div>
}

function btnSm(color: string): React.CSSProperties {
  return {
    padding: "4px 10px", fontSize: 11, fontFamily: T.mono,
    background: "transparent", color, border: `1px solid ${color}`,
    borderRadius: 4, cursor: "pointer",
  }
}
