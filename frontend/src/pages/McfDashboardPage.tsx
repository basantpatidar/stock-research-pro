import { McfScannerCard } from "../components/McfScannerCard"
import { T } from "../theme"

export function McfDashboardPage() {
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "1.5rem 1.25rem" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 600, color: T.text }}>MCF Dashboard</div>
        <div style={{ fontSize: 13, color: T.text2, marginTop: 4 }}>
          Market Context First (MCF) strategy targeting ~1% daily profit with high win rate logic.
        </div>
      </div>
      
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20 }}>
        <McfScannerCard />
        
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: T.text, marginBottom: 15 }}>How it works</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 15 }}>
            <div style={{ background: T.surface2, padding: 15, borderRadius: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 5 }}>1. Weather</div>
              <div style={{ fontSize: 12, color: T.text2 }}>Checks SPY daily trend and VIX level to ensure we are not buying a panic crash.</div>
            </div>
            <div style={{ background: T.surface2, padding: 15, borderRadius: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 5 }}>2. Tide</div>
              <div style={{ fontSize: 12, color: T.text2 }}>Requires 5-min correlation across SPY, QQQ, IWM, DIA showing broad momentum fading.</div>
            </div>
            <div style={{ background: T.surface2, padding: 15, borderRadius: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 5 }}>3. Setup</div>
              <div style={{ fontSize: 12, color: T.text2 }}>Specific ETF pulls back to support and prints a high-volume confirmation candle. Targets strict 1% profit.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
