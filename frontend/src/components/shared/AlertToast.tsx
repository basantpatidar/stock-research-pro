import { useStore } from "../../store"
import { api } from "../../services/api"

export function AlertToast() {
  const { alerts, dismissAlert } = useStore()
  const active = alerts.filter((a) => !("dismissed" in a)).slice(0, 3)

  if (!active.length) return null

  const handleDismiss = async (id: number) => {
    dismissAlert(id)
    try { await api.patch(`/alerts/history/${id}/dismiss`) } catch {}
  }

  const typeColor = (type: string) => {
    if (type === "watchlist_alert") return { border: "#16a34a", bg: "#f0fdf4" }
    if (type === "screener_alert") return { border: "#2563eb", bg: "#eff6ff" }
    return { border: "#d97706", bg: "#fffbeb" }
  }

  return (
    <div style={{ position: "fixed", bottom: 24, right: 24, zIndex: 100, display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
      {active.map((alert) => {
        const { border, bg } = typeColor(alert.type)
        return (
          <div key={alert.id} style={{
            background: bg,
            borderLeft: `3px solid ${border}`,
            borderRadius: 8,
            padding: "10px 14px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "#111", marginBottom: 3 }}>{alert.title}</div>
                <div style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.4 }}>{alert.body.slice(0, 120)}...</div>
              </div>
              <button
                onClick={() => handleDismiss(alert.id)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#9ca3af", fontSize: 16, lineHeight: 1, flexShrink: 0 }}
              >×</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
