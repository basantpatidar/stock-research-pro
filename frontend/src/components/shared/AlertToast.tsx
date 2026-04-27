import { useStore } from "../../store"
import { api } from "../../services/api"
import { T } from "../../theme"

const typeStyle = (type: string) => {
  if (type === "watchlist_alert") return { border: T.green, accent: T.greenDim, icon: "▲" }
  if (type === "screener_alert")  return { border: T.blue,  accent: T.blueDim,  icon: "◈" }
  return                                 { border: T.amber, accent: T.amberDim, icon: "⚡" }
}

export function AlertToast() {
  const { alerts, dismissAlert } = useStore()
  const active = alerts.filter((a) => !("dismissed" in a)).slice(0, 3)

  if (!active.length) return null

  const handleDismiss = async (id: number) => {
    dismissAlert(id)
    try { await api.patch(`/alerts/history/${id}/dismiss`) } catch {}
  }

  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, zIndex: 100,
      display: "flex", flexDirection: "column", gap: 8, maxWidth: 340,
    }}>
      {active.map((alert) => {
        const s = typeStyle(alert.type)
        return (
          <div key={alert.id} className="slide-in" style={{
            background: T.surface2,
            border: `1px solid ${T.border}`,
            borderLeft: `3px solid ${s.border}`,
            borderRadius: 10,
            padding: "12px 14px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
                  <span style={{ color: s.border, fontSize: 12 }}>{s.icon}</span>
                  <span style={{ fontSize: 13, fontWeight: 500, color: T.text }}>{alert.title}</span>
                </div>
                <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.45 }}>
                  {alert.body.slice(0, 120)}{alert.body.length > 120 ? "…" : ""}
                </div>
              </div>
              <button
                onClick={() => handleDismiss(alert.id)}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: T.text3, fontSize: 18, lineHeight: 1, flexShrink: 0,
                  padding: "0 2px",
                }}
              >×</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
