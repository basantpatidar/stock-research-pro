import { create } from "zustand"
import { persist } from "zustand/middleware"
import type {
  WatchlistItem, Alert, TradeMode, SSEEvent, ExecMode,
  BrokerAccount, BrokerPosition, BrokerOrder,
} from "./types/index"

interface StoreState {
  // Trade mode
  mode: TradeMode
  setMode: (mode: TradeMode) => void

  // Execution mode (saver / normal / deep)
  execMode: ExecMode
  setExecMode: (mode: ExecMode) => void

  // Last searched ticker — restored on reload
  lastTicker: string
  setLastTicker: (ticker: string) => void

  // Token usage counter (session)
  tokenCount: number
  addTokens: (n: number) => void
  resetTokens: () => void

  // Watchlist
  watchlist: WatchlistItem[]
  setWatchlist: (items: WatchlistItem[]) => void
  addToWatchlist: (item: WatchlistItem) => void
  removeFromWatchlist: (ticker: string) => void

  // Live alerts (WebSocket)
  alerts: Alert[]
  addAlert: (alert: Alert) => void
  dismissAlert: (id: number) => void
  clearAlerts: () => void

  // SSE stream state
  streamEvents: SSEEvent[]
  isStreaming: boolean
  addStreamEvent: (event: SSEEvent) => void
  clearStream: () => void
  setStreaming: (v: boolean) => void

  // WebSocket connection
  wsConnected: boolean
  setWsConnected: (v: boolean) => void

  // Scanner view mode
  scannerView: "simple" | "pro" | "guide"
  setScannerView: (v: "simple" | "pro" | "guide") => void

  // Broker / trading
  brokerAccount: BrokerAccount | null
  brokerStatus: "ok" | "unreachable" | "misconfigured" | "unknown"
  positions: BrokerPosition[]
  openOrders: BrokerOrder[]
  setBrokerAccount: (a: BrokerAccount | null) => void
  setBrokerStatus: (s: "ok" | "unreachable" | "misconfigured" | "unknown") => void
  setPositions: (p: BrokerPosition[]) => void
  setOpenOrders: (o: BrokerOrder[]) => void
}

export const useStore = create<StoreState>()(
  persist(
    (set) => ({
      mode: "both",
      setMode: (mode) => set({ mode }),

      execMode: "normal",
      setExecMode: (execMode) => set({ execMode }),

      lastTicker: "",
      setLastTicker: (lastTicker) => set({ lastTicker }),

      tokenCount: 0,
      addTokens: (n) => set((s) => ({ tokenCount: s.tokenCount + n })),
      resetTokens: () => set({ tokenCount: 0 }),

      watchlist: [],
      setWatchlist: (items) => set({ watchlist: items }),
      addToWatchlist: (item) =>
        set((s) => ({ watchlist: [...s.watchlist.filter((w) => w.ticker !== item.ticker), item] })),
      removeFromWatchlist: (ticker) =>
        set((s) => ({ watchlist: s.watchlist.filter((w) => w.ticker !== ticker) })),

      alerts: [],
      addAlert: (alert) => set((s) => ({ alerts: [alert, ...s.alerts].slice(0, 50) })),
      dismissAlert: (id) =>
        set((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) })),
      clearAlerts: () => set({ alerts: [] }),

      streamEvents: [],
      isStreaming: false,
      addStreamEvent: (event) =>
        set((s) => ({ streamEvents: [...s.streamEvents, event] })),
      clearStream: () => set({ streamEvents: [], isStreaming: false }),
      setStreaming: (v) => set({ isStreaming: v }),

      wsConnected: false,
      setWsConnected: (v) => set({ wsConnected: v }),

      scannerView: "simple",
      setScannerView: (v) => set({ scannerView: v }),

      brokerAccount: null,
      brokerStatus: "unknown",
      positions: [],
      openOrders: [],
      setBrokerAccount: (brokerAccount) => set({ brokerAccount }),
      setBrokerStatus: (brokerStatus) => set({ brokerStatus }),
      setPositions: (positions) => set({ positions }),
      setOpenOrders: (openOrders) => set({ openOrders }),
    }),
    {
      name: "srp-settings",
      partialize: (state) => ({
        mode: state.mode,
        execMode: state.execMode,
        lastTicker: state.lastTicker,
        scannerView: state.scannerView,
      }),
    }
  )
)
