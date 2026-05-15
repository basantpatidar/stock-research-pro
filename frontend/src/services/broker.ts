/**
 * Broker API client. See backend docs/api.md SEC:BROKER_ROUTES.
 *
 * Connectivity errors set the X-Broker-Status header (unreachable |
 * misconfigured) — components watch that on 503 to render the right banner.
 */
import { api } from "./api"
import type {
  BrokerAccount,
  BrokerClock,
  BrokerOrder,
  BrokerPosition,
  CapRejection,
  PlaceOrderBody,
} from "../types/index"

export interface BrokerError {
  status: number
  detail: string | CapRejection
  brokerStatus?: string  // "unreachable" | "misconfigured" — from response header
}

function wrap<T>(p: Promise<{ data: T }>): Promise<T> {
  return p.then((r) => r.data)
}

export const brokerApi = {
  account: () => wrap<BrokerAccount>(api.get("/broker/account")),
  clock:   () => wrap<BrokerClock>(api.get("/broker/clock")),
  positions: () => wrap<BrokerPosition[]>(api.get("/broker/positions")),

  /** status: "open" returns only new|accepted|partially_filled; "closed" the rest; "all" everything */
  listOrders: (status: "open" | "all" | "closed" = "open", limit = 50) =>
    wrap<BrokerOrder[]>(api.get(`/broker/orders`, { params: { status, limit } })),

  getOrder: (id: string) => wrap<BrokerOrder>(api.get(`/broker/orders/${id}`)),

  /**
   * Place an order. Throws on 422 (cap rejection / confirm_token mismatch)
   * or 503 (broker unreachable). client_order_id is REQUIRED — frontend
   * generates a UUID so retries are idempotent on the broker side.
   */
  placeOrder: (body: PlaceOrderBody) =>
    wrap<BrokerOrder>(api.post("/broker/orders", body)),

  cancelOrder: (id: string) => wrap<void>(api.delete(`/broker/orders/${id}`)),
}

/**
 * Compute the typed-confirmation token the live-mode order placement
 * route compares against. Frontend shows this string, user types it,
 * we pass it verbatim as `confirm_token` so the comparison stays
 * exact-match (no normalisation games).
 */
export function expectedConfirmToken(side: string, qty: number, symbol: string): string {
  const qtyStr = Number.isInteger(qty) ? String(qty) : String(qty)
  return `${side.toUpperCase()} ${qtyStr} ${symbol.toUpperCase()}`
}

/**
 * Best-effort UUIDv4 generator. Uses crypto.randomUUID when available
 * (modern browsers), falls back to a Math.random implementation so the
 * test harness and old Safari don't crash.
 */
export function newClientOrderId(): string {
  const c: any = typeof crypto !== "undefined" ? crypto : null
  if (c && typeof c.randomUUID === "function") return c.randomUUID()
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
