import { useEffect, useRef, useCallback } from "react"
import { useStore } from "../store"
import { WS_URL } from "../services/api"
import type { WSMessage, Alert } from "../types"

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const { setWsConnected, addAlert } = useStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const apiKey = import.meta.env.VITE_API_KEY || "dev-secret-key-change-in-production"
    const ws = new WebSocket(`${WS_URL}/alerts/ws?api_key=${apiKey}`)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      // Send ping every 20s to keep connection alive
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }))
        }
      }, 20000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)

        if (msg.type === "watchlist_alert" || msg.type === "screener_alert") {
          const alert: Alert = {
            id: Date.now(),
            ticker: msg.ticker,
            type: msg.type,
            title: msg.title,
            body: msg.body,
            score: msg.type === "watchlist_alert" ? msg.score : null,
            triggered_at: msg.type === "watchlist_alert" ? msg.timestamp : new Date().toISOString(),
            source: msg.type === "watchlist_alert" ? "watchlist" : "screener",
          }
          addAlert(alert)
        }
      } catch (e) {
        console.error("WS parse error:", e)
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
      if (pingTimer.current) clearInterval(pingTimer.current)
      // Reconnect after 5s
      reconnectTimer.current = setTimeout(connect, 5000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [setWsConnected, addAlert])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (pingTimer.current) clearInterval(pingTimer.current)
      wsRef.current?.close()
    }
  }, [connect])
}
