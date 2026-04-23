import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import { useWebSocket } from "./hooks/useWebSocket"
import { useStore } from "./store"
import { AlertToast } from "./components/shared/AlertToast"
import { ResearchPage } from "./pages/ResearchPage"
import { WatchlistPage } from "./pages/WatchlistPage"
import { ScreenerPage } from "./pages/ScreenerPage"
import { MacroPage } from "./pages/MacroPage"

const NAV_LINKS = [
  { to: "/", label: "Research" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/screener", label: "Screener" },
  { to: "/macro", label: "Macro" },
]

function AppShell() {
  // Mount WebSocket once at app level — persists across page navigation
  useWebSocket()
  const { wsConnected, alerts } = useStore()
  const unread = alerts.length

  return (
    <div style={{ minHeight: "100vh", background: "#f9fafb", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      {/* Nav */}
      <nav style={{
        background: "#fff",
        borderBottom: "0.5px solid #e5e7eb",
        padding: "0 1.5rem",
        display: "flex",
        alignItems: "center",
        height: 52,
        gap: 4,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: "#111", marginRight: 24 }}>
          📈 Stock Research Pro
        </div>
        {NAV_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            style={({ isActive }) => ({
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              color: isActive ? "#111" : "#6b7280",
              textDecoration: "none",
              padding: "4px 12px",
              borderRadius: 6,
              background: isActive ? "#f3f4f6" : "transparent",
            })}
          >
            {label}
            {label === "Watchlist" && unread > 0 && (
              <span style={{
                marginLeft: 6, background: "#dc2626", color: "#fff",
                borderRadius: 20, fontSize: 10, fontWeight: 500,
                padding: "1px 5px",
              }}>{unread}</span>
            )}
          </NavLink>
        ))}

        {/* WS status */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%",
            background: wsConnected ? "#16a34a" : "#d1d5db",
          }} />
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {wsConnected ? "Live" : "Connecting..."}
          </span>
        </div>
      </nav>

      {/* Pages */}
      <main>
        <Routes>
          <Route path="/" element={<ResearchPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/screener" element={<ScreenerPage />} />
          <Route path="/macro" element={<MacroPage />} />
        </Routes>
      </main>

      {/* Toast notifications */}
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
