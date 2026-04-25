import { useCallback } from "react"
import { useStore } from "../store"
import type { SSEEvent, TradeMode } from "../types"

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"
const API_KEY = import.meta.env.VITE_API_KEY || "dev-secret-key-change-in-production"

export function useSSE() {
  const { addStreamEvent, clearStream, setStreaming } = useStore()

  const startResearch = useCallback(
    (ticker: string, mode: TradeMode = "both") => {
      clearStream()
      setStreaming(true)

      const url = `${BASE_URL}/research/stream?ticker=${ticker}&mode=${mode}&api_key=${API_KEY}`
      const es = new EventSource(url)

      es.onmessage = (event) => {
        try {
          const data: SSEEvent = JSON.parse(event.data)
          addStreamEvent(data)
          if (data.type === "done" || data.type === "error") {
            setStreaming(false)
            es.close()
          }
        } catch (e) {
          console.error("SSE parse error:", e)
        }
      }

      es.onerror = () => {
        setStreaming(false)
        es.close()
      }

      return () => {
        es.close()
        setStreaming(false)
      }
    },
    [addStreamEvent, clearStream, setStreaming]
  )

  return { startResearch }
}
