import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import { useWebSocket } from "./hooks/useWebSocket"
import { useStore } from "./store"
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

const TOKEN_DAILY_LIMIT = 50_000

function AppShell() {
  useWebSocket()
  const { wsConnected, alerts, tokenCount } = useStore()
  const unread = alerts.length
  const tokenPct = Math.min(100, Math.round((tokenCount / TOKEN_DAILY_LIMIT) * 100))
  const tokenPctColor = tokenPct >= 80 ? T.red : tokenPct >= 50 ? T.amber : T.green

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
          {tokenCount > 0 && (
            <span style={{
              fontSize: 10, fontFamily: T.mono, fontWeight: 600,
              padding: "2px 8px", borderRadius: 20,
              background: `${tokenPctColor}20`, color: tokenPctColor,
              border: `1px solid ${tokenPctColor}`,
              marginLeft: 4,
            }}>
              {tokenPct}% tokens
            </span>
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
