import { useState, useCallback } from "react"
import { api } from "../services/api"
import type { ScreenerFilters, ScreenerResult, ScreenerPreset } from "../types"

const DEFAULT_FILTERS: ScreenerFilters = {
  min_market_cap_b: 100,
  min_volume: 1_000_000,
  min_price_drop_pct: 10,
  sector: "all",
  max_pe: 0,
  universe: "sp500",
  limit: 50,
}

export function useScreener() {
  const [filters, setFilters] = useState<ScreenerFilters>(DEFAULT_FILTERS)
  const [results, setResults] = useState<ScreenerResult[]>([])
  const [presets, setPresets] = useState<ScreenerPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runScreener = useCallback(async (overrideFilters?: ScreenerFilters) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post("/screener/run", overrideFilters || filters)
      setResults(res.data.results || [])
      return res.data
    } catch (e: any) {
      setError(e.response?.data?.detail || "Screener failed")
      return null
    } finally {
      setLoading(false)
    }
  }, [filters])

  const savePreset = useCallback(async (name: string, autoMonitor = false) => {
    try {
      await api.post("/screener/presets", { name, filters, auto_monitor: autoMonitor })
      await fetchPresets()
      return { success: true }
    } catch (e) {
      return { success: false }
    }
  }, [filters])

  const fetchPresets = useCallback(async () => {
    try {
      const res = await api.get("/screener/presets")
      setPresets(res.data.presets || [])
    } catch (e) {
      console.error("Failed to fetch presets:", e)
    }
  }, [])

  const runPreset = useCallback(async (presetId: number) => {
    setLoading(true)
    try {
      const res = await api.post(`/screener/presets/${presetId}/run`)
      setResults(res.data.results || [])
    } catch (e: any) {
      setError(e.response?.data?.detail || "Preset run failed")
    } finally {
      setLoading(false)
    }
  }, [])

  const toggleAutoMonitor = useCallback(async (presetId: number) => {
    await api.patch(`/screener/presets/${presetId}/toggle-monitor`)
    await fetchPresets()
  }, [fetchPresets])

  return {
    filters, setFilters,
    results,
    presets,
    loading, error,
    runScreener, savePreset, fetchPresets, runPreset, toggleAutoMonitor,
  }
}
