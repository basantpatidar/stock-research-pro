import { useState, useCallback } from "react"
import { api } from "../../services/api"
import type { GapScanResult, GapItem } from "../../types"
import { T } from "../../theme"

interface Props {
  tickers: string[]
}

const FLOAT_COLOR: Record<string, string> = {
  nano:    T.red,
  micro:   T.amber,
  small:   T.text2,
  large:   T.text3,
  unknown: T.text3,
}

function GapRow({ g }: { g: GapItem }) {
  const isUp   = g.direction === "up"
  const color  = isUp ? T.green : T.red
  const mc     = g.market_cap
  const mcLabel = mc
    ? mc >= 1e12 ? `$${(mc / 1e12).toFixed(1)}T`
      : mc >= 1e9 ? `$${(mc / 1e9).toFixed(1)}B`
      : `$${(mc / 1e6).toFixed(0)}M`
    : "—"

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "60px 1fr 70px 70px 60px 60px 70px",
      gap: 10, padding: "9px 14px", alignItems: "center",
      borderBottom: `1px solid ${T.border}`,
    }}>
      <span style={{ fontWeight: 600, fontFamily: T.mono, color: T.text, fontSize: 13 }}>
        {g.ticker}
      </span>
      <span style={{ fontSize: 11, color: T.text2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {g.company_name}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, fontFamily: T.mono, color, textAlign: "right" }}>
        {isUp ? "▲" : "▼"} {Math.abs(g.gap_pct).toFixed(2)}%
      </span>
      <span style={{ fontSize: 12, fontFamily: T.mono, color: T.text2, textAlign: "right" }}>
        ${g.ext_price.toFixed(2)}
      </span>
      <span style={{
        fontSize: 10, fontFamily: T.mono, textAlign: "center",
        color: FLOAT_COLOR[g.float_class] ?? T.text3,
        background: T.surface2, borderRadius: 4, padding: "2px 5px",
      }}>
        {g.float_class}
      </span>
      <span style={{ fontSize: 11, color: T.text3, textAlign: "right", fontFamily: T.mono }}>
        {g.vol_ratio != null ? `${g.vol_ratio.toFixed(1)}x` : "—"}
      </span>
      <span style={{
        fontSize: 10, textAlign: "center", borderRadius: 4, padding: "2px 6px",
        background: g.gap_type === "earnings" ? "#ffaa0020" : T.surface2,
        color: g.gap_type === "earnings" ? T.amber : T.text3,
        fontFamily: T.mono,
      }}>
        {g.gap_type}
      </span>
    </div>
  )
}

export function GapScannerCard({ tickers }: Props) {
  const [result, setResult]   = useState<GapScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [lastRun, setLastRun] = useState<string | null>(null)

  const runScan = useCallback(async () => {
    if (!tickers.length) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.post<GapScanResult>("/gap-scanner/", {
        tickers,
        threshold_pct: 2.0,
      })
      setResult(res.data)
      setLastRun(new Date().toLocaleTimeString())
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Scan failed")
    } finally {
      setLoading(false)
    }
  }, [tickers])

  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 12, overflow: "hidden", marginBottom: 16,
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px", borderBottom: `1px solid ${T.border}`,
        background: T.surface2,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: T.text, letterSpacing: "0.04em" }}>
            Pre-Market Gap Scanner
          </span>
          {result && (
            <span style={{ fontSize: 10, fontFamily: T.mono, color: T.text3 }}>
              {result.gaps.length} gap{result.gaps.length !== 1 ? "s" : ""} found · {result.scanned} scanned
            </span>
          )}
          {lastRun && (
            <span style={{ fontSize: 10, color: T.text3 }}>· updated {lastRun}</span>
          )}
        </div>
        <button
          onClick={runScan}
          disabled={loading || tickers.length === 0}
          style={{
            fontSize: 11, fontWeight: 500, border: `1px solid ${T.blue}`,
            background: loading ? T.surface2 : T.blueDim,
            color: loading ? T.text3 : T.blue,
            borderRadius: 6, padding: "4px 14px", cursor: loading ? "not-allowed" : "pointer",
            transition: "all 0.12s ease",
          }}
        >
          {loading ? "Scanning…" : "Scan Now"}
        </button>
      </div>

      {error && (
        <div style={{ padding: "10px 14px", fontSize: 12, color: T.red }}>{error}</div>
      )}

      {!result && !loading && (
        <div style={{ padding: "2rem", textAlign: "center", color: T.text3, fontSize: 12 }}>
          {tickers.length === 0
            ? "Add tickers to your watchlist to scan for gaps."
            : `Click Scan Now to check ${tickers.length} watchlist ticker${tickers.length !== 1 ? "s" : ""} for pre-market gaps ≥2%.`}
        </div>
      )}

      {result && result.gaps.length === 0 && (
        <div style={{ padding: "1.5rem", textAlign: "center", color: T.text3, fontSize: 12 }}>
          No gaps ≥{result.threshold_pct}% found in {result.scanned} tickers.
        </div>
      )}

      {result && result.gaps.length > 0 && (
        <>
          {/* Column headers */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "60px 1fr 70px 70px 60px 60px 70px",
            gap: 10, padding: "6px 14px",
            borderBottom: `1px solid ${T.border}`,
          }}>
            {["Ticker", "Company", "Gap %", "Price", "Float", "Vol×", "Type"].map(h => (
              <span key={h} style={{ fontSize: 9, color: T.text3, textTransform: "uppercase", letterSpacing: "0.06em", textAlign: h === "Gap %" || h === "Price" || h === "Vol×" ? "right" : "center" as any }}>
                {h}
              </span>
            ))}
          </div>
          {result.gaps.map(g => <GapRow key={g.ticker} g={g} />)}
        </>
      )}
    </div>
  )
}
