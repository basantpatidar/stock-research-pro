import { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { brokerApi } from "../../services/broker"
import { useStore } from "../../store"
import { T } from "../../theme"

const POLL_MS = 30_000

/**
 * Top-nav indicator: broker name, mode (PAPER/LIVE), connectivity.
 * Polls /broker/account every 30s and updates the store. Click → /portfolio.
 */
export function BrokerStatusBadge() {
  const navigate = useNavigate()
  const { brokerAccount, brokerStatus, setBrokerAccount, setBrokerStatus } = useStore()

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const acct = await brokerApi.account()
        if (!cancelled) {
          setBrokerAccount(acct)
          setBrokerStatus("ok")
        }
      } catch (e: any) {
        if (!cancelled) {
          const bs = e?.response?.headers?.["x-broker-status"]
          setBrokerStatus(bs === "misconfigured" ? "misconfigured" : "unreachable")
        }
      }
    }
    tick()
    const t = setInterval(tick, POLL_MS)
    return () => { cancelled = true; clearInterval(t) }
  }, [setBrokerAccount, setBrokerStatus])

  const isLive = brokerAccount?.mode === "live"
  const modeColor = brokerStatus === "ok"
    ? (isLive ? T.red : T.amber)
    : brokerStatus === "misconfigured" ? T.text3 : T.red
  const dotColor = brokerStatus === "ok" ? T.green : T.red
  const label = brokerStatus === "ok"
    ? (brokerAccount?.mode.toUpperCase() || "—")
    : brokerStatus === "misconfigured" ? "NOT SET" : "DOWN"

  return (
    <button
      onClick={() => navigate("/portfolio")}
      title={
        brokerStatus === "ok"
          ? `${brokerAccount?.broker || "broker"} · ${brokerAccount?.mode || ""} · click for portfolio`
          : brokerStatus === "misconfigured"
            ? "Broker not configured — set ALPACA_API_KEY in .env"
            : "Broker unreachable"
      }
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "3px 9px", borderRadius: 20,
        background: "transparent", color: modeColor,
        border: `1px solid ${modeColor}`,
        fontSize: 10, fontWeight: 700, fontFamily: T.mono, letterSpacing: "0.08em",
        cursor: "pointer",
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor }} />
      {label}
    </button>
  )
}
