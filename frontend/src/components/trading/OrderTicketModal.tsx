import { useEffect, useMemo, useState } from "react"
import { brokerApi, expectedConfirmToken, newClientOrderId } from "../../services/broker"
import { useStore } from "../../store"
import { T } from "../../theme"
import type {
  CapRejection, OrderSide, OrderType, PlaceOrderBody, TimeInForce,
} from "../../types/index"

export interface TicketPrefill {
  symbol: string
  side: OrderSide
  qty?: number
  qtyDollars?: number
  orderType?: OrderType
  limitPrice?: number
  stopPrice?: number
  takeProfitPrice?: number
  source?: "manual" | "scanner_alert"
  scannerAlertId?: string | null
}

interface Props {
  prefill: TicketPrefill
  onClose: () => void
  onPlaced: (orderId: string) => void | Promise<void>
}

const CAP_COPY: Record<string, (d: CapRejection) => string> = {
  max_order_dollars_exceeded: (d) =>
    `Order rejected — \$${d.attempted_dollars} exceeds the per-order cap of \$${d.limit_dollars}. Lower qty or split the order.`,
  max_position_dollars_exceeded: (d) =>
    `Order rejected — would push position to \$${(d.current_position_dollars ?? 0) + (d.attempted_add_dollars ?? 0)} ` +
    `(cap \$${d.limit_dollars}). Trim qty or close an existing position first.`,
  daily_order_count_cap_reached: (d) =>
    `Order rejected — already placed ${d.today_count} orders today (cap ${d.limit}).`,
  daily_loss_cap_reached: (d) =>
    `Order rejected — today's P&L is \$${d.day_pnl_dollars} (cap \$${d.cap_dollars}). New buys blocked until midnight ET.`,
  no_price_reference_for_market_order: () =>
    `Market order rejected — could not fetch a quote to enforce the per-order cap. Use a limit order instead.`,
  confirm_token_mismatch: (d) =>
    `Live-mode confirmation required. Type exactly: ${d.expected}`,
  broker_rejected: (d) =>
    `Broker rejected the order: ${d.message || "no reason given"}`,
}


export function OrderTicketModal({ prefill, onClose, onPlaced }: Props) {
  const brokerAccount = useStore((s) => s.brokerAccount)
  const isLive = brokerAccount?.mode === "live"

  const [symbol, setSymbol] = useState(prefill.symbol.toUpperCase())
  const [side, setSide] = useState<OrderSide>(prefill.side)
  const [orderType, setOrderType] = useState<OrderType>(prefill.orderType || "limit")
  const [qtyMode, setQtyMode] = useState<"shares" | "dollars">(
    prefill.qtyDollars != null ? "dollars" : "shares",
  )
  const [qtyInput, setQtyInput] = useState<string>(
    prefill.qty != null ? String(prefill.qty) :
    prefill.qtyDollars != null ? String(prefill.qtyDollars) : "",
  )
  const [limitPrice, setLimitPrice] = useState<string>(prefill.limitPrice != null ? String(prefill.limitPrice) : "")
  const [stopPrice, setStopPrice]   = useState<string>(prefill.stopPrice   != null ? String(prefill.stopPrice)   : "")
  const [takeProfitPrice, setTakeProfitPrice] = useState<string>(prefill.takeProfitPrice != null ? String(prefill.takeProfitPrice) : "")
  const [tif, setTif] = useState<TimeInForce>("day")
  const [bracket, setBracket] = useState<boolean>(prefill.stopPrice != null || prefill.takeProfitPrice != null)
  const [confirmToken, setConfirmToken] = useState<string>("")

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // client_order_id is generated once per modal mount — retries within the
  // same modal session are idempotent on the broker side.
  const clientOrderId = useMemo(() => newClientOrderId(), [])

  // Derive shares from dollars when qtyMode = dollars + we have a price reference
  const refPrice = useMemo(() => {
    const lp = parseFloat(limitPrice)
    if (!isNaN(lp) && lp > 0) return lp
    return null
  }, [limitPrice])

  const shares = useMemo(() => {
    const n = parseFloat(qtyInput)
    if (isNaN(n) || n <= 0) return 0
    if (qtyMode === "shares") return Math.floor(n)
    if (refPrice) return Math.floor(n / refPrice)
    return 0  // dollars mode without a limit price — can't compute shares yet
  }, [qtyInput, qtyMode, refPrice])

  const expected = expectedConfirmToken(side, shares, symbol)

  const canSubmit = symbol.trim() !== "" && shares > 0 && (
    orderType === "market" || (refPrice !== null && refPrice > 0)
  ) && (!isLive || confirmToken === expected)

  useEffect(() => {
    if (orderType === "stop_limit" && !stopPrice) {
      // sensible default — limit price + 0.5%
      const lp = parseFloat(limitPrice)
      if (!isNaN(lp)) setStopPrice(lp.toFixed(2))
    }
  }, [orderType, limitPrice, stopPrice])

  const submit = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const body: PlaceOrderBody = {
        symbol: symbol.trim().toUpperCase(),
        side,
        qty: shares,
        order_type: orderType,
        limit_price: orderType === "limit" || orderType === "stop_limit" ? parseFloat(limitPrice) : null,
        stop_price: orderType === "stop" || orderType === "stop_limit"
          ? parseFloat(stopPrice)
          : (bracket && stopPrice ? parseFloat(stopPrice) : null),
        take_profit_price: bracket && takeProfitPrice ? parseFloat(takeProfitPrice) : null,
        time_in_force: tif,
        client_order_id: clientOrderId,
        source: prefill.source || "manual",
        scanner_alert_id: prefill.scannerAlertId || null,
        confirm_token: isLive ? confirmToken : null,
      }
      const placed = await brokerApi.placeOrder(body)
      await onPlaced(placed.broker_order_id)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (detail && typeof detail === "object" && detail.error) {
        const fn = CAP_COPY[detail.error as string]
        setError(fn ? fn(detail) : `Order rejected: ${detail.error}`)
      } else if (typeof detail === "string") {
        setError(detail)
      } else {
        setError(e?.message || "Submit failed")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={cardStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <h2 style={{ fontSize: 16, margin: 0, color: T.text }}>Order Ticket</h2>
          {brokerAccount && (
            <span style={{
              fontSize: 10, fontWeight: 700, fontFamily: T.mono, letterSpacing: "0.08em",
              padding: "2px 8px", borderRadius: 20,
              background: isLive ? T.redDim : T.amberDim,
              color: isLive ? T.red : T.amber,
              border: `1px solid ${isLive ? T.red : T.amber}`,
            }}>{brokerAccount.mode.toUpperCase()}</span>
          )}
          <button onClick={onClose} style={{
            marginLeft: "auto", background: "transparent", border: "none",
            color: T.text2, cursor: "pointer", fontSize: 18, padding: 0,
          }}>×</button>
        </div>

        {/* Side toggle */}
        <Row label="Side">
          <SegToggle
            options={[{ v: "buy", label: "Buy", c: T.green }, { v: "sell", label: "Sell", c: T.red }]}
            value={side}
            onChange={(v) => setSide(v as OrderSide)}
          />
        </Row>

        {/* Symbol */}
        <Row label="Symbol">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={inputStyle} />
        </Row>

        {/* Qty */}
        <Row label={qtyMode === "shares" ? "Quantity (shares)" : "Quantity ($)"}>
          <div style={{ display: "flex", gap: 8 }}>
            <input value={qtyInput} onChange={(e) => setQtyInput(e.target.value)}
                   inputMode="decimal" style={{ ...inputStyle, flex: 1 }} />
            <SegToggle
              options={[{ v: "shares", label: "shares" }, { v: "dollars", label: "$" }]}
              value={qtyMode}
              onChange={(v) => setQtyMode(v as "shares" | "dollars")}
            />
          </div>
          {qtyMode === "dollars" && shares > 0 && (
            <div style={{ fontSize: 11, color: T.text2, marginTop: 4, fontFamily: T.mono }}>
              → {shares} shares @ {limitPrice ? `\$${limitPrice}` : "(set limit price)"}
            </div>
          )}
        </Row>

        {/* Order type */}
        <Row label="Type">
          <SegToggle
            options={[
              { v: "market", label: "Market" },
              { v: "limit",  label: "Limit"  },
              { v: "stop",   label: "Stop"   },
              { v: "stop_limit", label: "Stop-Limit" },
            ]}
            value={orderType}
            onChange={(v) => setOrderType(v as OrderType)}
          />
        </Row>

        {(orderType === "limit" || orderType === "stop_limit") && (
          <Row label="Limit price">
            <input value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} inputMode="decimal" style={inputStyle} />
          </Row>
        )}
        {(orderType === "stop" || orderType === "stop_limit") && (
          <Row label="Stop price">
            <input value={stopPrice} onChange={(e) => setStopPrice(e.target.value)} inputMode="decimal" style={inputStyle} />
          </Row>
        )}

        {/* Bracket */}
        <Row label="Bracket (stop loss + take profit)">
          <label style={{ display: "flex", alignItems: "center", gap: 8, color: T.text2, fontSize: 13 }}>
            <input type="checkbox" checked={bracket} onChange={(e) => setBracket(e.target.checked)} />
            Attach bracket
          </label>
        </Row>
        {bracket && (
          <>
            <Row label="Stop loss">
              <input value={stopPrice} onChange={(e) => setStopPrice(e.target.value)} inputMode="decimal" style={inputStyle} />
            </Row>
            <Row label="Take profit">
              <input value={takeProfitPrice} onChange={(e) => setTakeProfitPrice(e.target.value)} inputMode="decimal" style={inputStyle} />
            </Row>
          </>
        )}

        {/* TIF */}
        <Row label="Time in force">
          <SegToggle
            options={[
              { v: "day", label: "DAY" },
              { v: "gtc", label: "GTC" },
              { v: "ioc", label: "IOC" },
              { v: "fok", label: "FOK" },
            ]}
            value={tif}
            onChange={(v) => setTif(v as TimeInForce)}
          />
        </Row>

        {/* Live confirmation */}
        {isLive && (
          <Row label={`Type to confirm`}>
            <div style={{ fontSize: 11, color: T.text2, marginBottom: 4, fontFamily: T.mono }}>
              Must match exactly: <span style={{ color: T.red }}>{expected}</span>
            </div>
            <input value={confirmToken} onChange={(e) => setConfirmToken(e.target.value)}
                   placeholder={expected}
                   style={{ ...inputStyle, borderColor: confirmToken === expected ? T.green : T.red }} />
          </Row>
        )}

        {/* Error */}
        {error && (
          <div style={{
            background: T.redDim, color: T.red, border: `1px solid ${T.red}`,
            padding: "8px 12px", borderRadius: 6, marginTop: 12, fontSize: 12,
          }}>{error}</div>
        )}

        {/* Submit */}
        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: "10px 16px", fontFamily: T.mono, fontSize: 13,
            background: T.surface2, color: T.text2, border: `1px solid ${T.border}`,
            borderRadius: 6, cursor: "pointer",
          }}>Cancel</button>
          <button disabled={!canSubmit || submitting} onClick={submit} style={{
            flex: 2, padding: "10px 16px", fontFamily: T.mono, fontSize: 13, fontWeight: 700,
            background: side === "buy" ? T.green : T.red, color: "#fff", border: "none",
            borderRadius: 6, cursor: canSubmit && !submitting ? "pointer" : "not-allowed",
            opacity: canSubmit && !submitting ? 1 : 0.4,
          }}>
            {submitting ? "Submitting…" : `${side.toUpperCase()} ${shares} ${symbol}`}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Styles ────────────────────────────────────────────────────────────────────

const overlayStyle: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
}
const cardStyle: React.CSSProperties = {
  background: T.surface, border: `1px solid ${T.borderBright}`, borderRadius: 12,
  padding: 22, width: 460, maxWidth: "92vw", maxHeight: "92vh", overflow: "auto",
}
const inputStyle: React.CSSProperties = {
  padding: "8px 10px", fontSize: 13, fontFamily: T.mono,
  background: T.bg, color: T.text, border: `1px solid ${T.border}`,
  borderRadius: 6, width: "100%", boxSizing: "border-box",
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{
        fontSize: 10, color: T.text3, textTransform: "uppercase",
        letterSpacing: "0.07em", marginBottom: 6, fontFamily: T.mono,
      }}>{label}</div>
      {children}
    </div>
  )
}

function SegToggle({ options, value, onChange }: {
  options: { v: string; label: string; c?: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div style={{ display: "inline-flex", gap: 2, background: T.bg, padding: 2, border: `1px solid ${T.border}`, borderRadius: 6 }}>
      {options.map((o) => (
        <button key={o.v} onClick={() => onChange(o.v)} style={{
          padding: "5px 11px", fontSize: 11, fontFamily: T.mono, fontWeight: 600,
          background: value === o.v ? (o.c || T.surface2) : "transparent",
          color: value === o.v ? (o.c ? "#fff" : T.text) : T.text2,
          border: "none", borderRadius: 4, cursor: "pointer",
        }}>{o.label}</button>
      ))}
    </div>
  )
}
