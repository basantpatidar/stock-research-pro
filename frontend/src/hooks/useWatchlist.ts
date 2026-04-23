import { useCallback, useEffect } from "react"
import { useStore } from "../store"
import { api } from "../services/api"
import type { WatchlistItem } from "../types"

export function useWatchlist() {
  const { watchlist, setWatchlist, addToWatchlist, removeFromWatchlist } = useStore()

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await api.get("/watchlist/")
      setWatchlist(res.data.items as WatchlistItem[])
    } catch (e) {
      console.error("Failed to fetch watchlist:", e)
    }
  }, [setWatchlist])

  const addTicker = useCallback(
    async (ticker: string, companyName?: string) => {
      try {
        await api.post("/watchlist/", { ticker, company_name: companyName })
        await fetchWatchlist()
        return { success: true }
      } catch (e: any) {
        return { success: false, error: e.response?.data?.detail || "Failed to add" }
      }
    },
    [fetchWatchlist]
  )

  const removeTicker = useCallback(
    async (ticker: string) => {
      try {
        await api.delete(`/watchlist/${ticker}`)
        removeFromWatchlist(ticker)
        return { success: true }
      } catch (e) {
        return { success: false }
      }
    },
    [removeFromWatchlist]
  )

  useEffect(() => {
    fetchWatchlist()
  }, [fetchWatchlist])

  return { watchlist, addTicker, removeTicker, refresh: fetchWatchlist }
}
