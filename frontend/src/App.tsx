import { useEffect, useState } from "react"
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import { useWebSocket } from "./hooks/useWebSocket"
import { useStore } from "./store"
import { api } from "./services/api"
import { AlertToast } from "./components/shared/AlertToast"
import { ExecModeBar } from "./components/shared/ExecModeBar"
import { ResearchPage } from "./pages/ResearchPage"
import { WatchlistPage } from "./pages/WatchlistPage"
import { ScreenerPage } from "./pages/ScreenerPage"
import { MacroPage } from "./pages/MacroPage"
import { UsagePage } from "./pages/UsagePage"
import { DashboardPage } from "./pages/DashboardPage"
import { McfDashboardPage } from "./pages/McfDashboardPage"
import { PortfolioPage } from "./pages/PortfolioPage"
import { BrokerStatusBadge } from "./components/shared/BrokerStatusBadge"
import { T } from "./theme"

const NAV_ITEMS = [
  { to: "/",           label: "Research" },
  { to: "/dashboard",  label: "Dashboard" },
  { to: "/mcf",        label: "MCF Dashboard" },
  { to: "/watchlist",  label: "Watchlist" },
  { to: "/screener",   label: "Screener" },
  { to: "/macro",      label: "Macro" },
  { to: "/portfolio",  label: "Portfolio" },
  { to: "/usage",      label: "Usage" },
]

interface UsageTodayLite {
  tokens_today_pct: number
  api_calls_today_pct: number
  tokens_today: number
  api_calls_today: number
  token_daily_limit: number
  api_calls_daily_limit: number
}

// Inline pill — color tiers (green <50%, amber 50-79%, red 80%+) match the
// thresholds the backend uses for its `warning` field, so visual state and
// the actual cap-rejection logic stay in sync. Hides at 0% to avoid noise
// before any usage has accumulated.
function UsagePill({ label, pct, count, limit }: { label: string; pct: number; count: number; limit: number }) {
  if (count === 0) return null
  const color = pct >= 80 ? T.red : pct >= 50 ? T.amber : T.green
  return (
    <span
      title={`${count.toLocaleString()} / ${limit.toLocaleString()} ${label} used today`}
      style={{
        fontSize: 10, fontFamily: T.mono, fontWeight: 600,
        padding: "2px 8px", borderRadius: 20,
        background: `${color}20`, color, border: `1px solid ${color}`,
        marginLeft: 4,
      }}
    >
      {Math.round(pct)}% {label}
    </span>
  )
}

function AppShell() {
  useWebSocket()
  const { wsConnected, alerts } = useStore()
  const unread = alerts.length

  // Server-side usage state — single source of truth. Polled every 30s so the
  // pill reflects what's actually counted against the daily cap, not what the
  // frontend session has locally accumulated (the old `tokenCount` store).
  const [usage, setUsage] = useState<UsageTodayLite | null>(null)
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const { data } = await api.get<UsageTodayLite>("/usage/today")
        if (!cancelled) setUsage(data)
      } catch {}
    }
    load()
    const t = setInterval(load, 30_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  return (
    <div style={{ minHeight: "100vh", background: T.bg }}>
      {/* Top nav */}
      <nav style={{
        background: T.surface,
        borderBottom: `1px solid ${T.border}`,
        padding: "0 1.5rem",
        display: "flex",
        alignItems: "center",
        height: 52,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 32 }}>
          <div style={{
            fontFamily: T.mono, fontSize: 16, fontWeight: 500,
            background: `linear-gradient(135deg, ${T.blue} 0%, ${T.purple} 100%)`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            letterSpacing: "0.02em",
          }}>SRP</div>
          <span style={{ color: T.text2, fontSize: 13 }}>Stock Research Pro</span>
        </div>

        {/* Nav links */}
        <div style={{ display: "flex", gap: 2 }}>
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => ({
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                color: isActive ? T.text : T.text2,
                textDecoration: "none",
                padding: "5px 13px",
                borderRadius: 6,
                background: isActive ? T.surface2 : "transparent",
                border: `1px solid ${isActive ? T.borderBright : "transparent"}`,
                display: "inline-flex", alignItems: "center", gap: 6,
                transition: "all 0.12s ease",
              })}
            >
              {label}
              {label === "Watchlist" && unread > 0 && (
                <span style={{ background: T.red, color: "#fff", borderRadius: 20, fontSize: 10, fontWeight: 600, padding: "1px 6px", lineHeight: 1.4 }}>
                  {unread}
                </span>
              )}
            </NavLink>
          ))}
        </div>

        {/* Live status + broker badge + token counter */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          <BrokerStatusBadge />
          <div style={{ position: "relative", width: 8, height: 8, flexShrink: 0 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: wsConnected ? T.green : T.text3, position: "absolute",
              animation: wsConnected ? "pulse-dot 2s ease-in-out infinite" : "none",
            }} />
            {wsConnected && (
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.green, position: "absolute", animation: "pulse-ring 1.8s ease-out infinite" }} />
            )}
          </div>
          <span style={{ fontSize: 11, color: T.text2, fontFamily: T.mono, letterSpacing: "0.05em" }}>
            {wsConnected ? "LIVE" : "OFFLINE"}
          </span>
          {usage && (
            <>
              <UsagePill
                label="tokens"
                pct={usage.tokens_today_pct}
                count={usage.tokens_today}
                limit={usage.token_daily_limit}
              />
              <UsagePill
                label="api"
                pct={usage.api_calls_today_pct}
                count={usage.api_calls_today}
                limit={usage.api_calls_daily_limit}
              />
            </>
          )}
        </div>
      </nav>

      {/* ExecModeBar — shown below nav on all pages */}
      <ExecModeBar />

      <main>
        <Routes>
          <Route path="/"           element={<ResearchPage />} />
          <Route path="/dashboard"  element={<DashboardPage />} />
          <Route path="/mcf"        element={<McfDashboardPage />} />
          <Route path="/watchlist"  element={<WatchlistPage />} />
          <Route path="/screener"   element={<ScreenerPage />} />
          <Route path="/macro"      element={<MacroPage />} />
          <Route path="/portfolio"  element={<PortfolioPage />} />
          <Route path="/usage"      element={<UsagePage />} />
        </Routes>
      </main>

      <AlertToast />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
