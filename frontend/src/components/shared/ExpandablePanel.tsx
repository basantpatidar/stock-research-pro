import { useState, useEffect, useRef } from "react"
import { useStore } from "../../store"
import { T } from "../../theme"
import type { ExecMode } from "../../types"

const TIER_STYLES = {
  1: { color: T.green,  label: "T1", title: "Tier 1 — always loaded, 0 tokens" },
  2: { color: T.blue,   label: "T2", title: "Tier 2 — ~400–900 tokens on expand" },
  3: { color: T.purple, label: "T3", title: "Tier 3 — deep analysis, 800–6K tokens" },
}

interface Props {
  title: string
  tier: 1 | 2 | 3
  estimatedTokens?: number
  loading?: boolean
  error?: string | null
  onExpand?: () => void
  children: React.ReactNode
  /** Pre-expanded when execMode === "deep" (tier 2) or always (tier 1) */
  autoExpand?: boolean
}

export function ExpandablePanel({
  title, tier, estimatedTokens, loading = false, error = null,
  onExpand, children, autoExpand = false,
}: Props) {
  const { execMode } = useStore()
  const shouldAutoExpand = autoExpand || tier === 1 || (tier === 2 && execMode === "deep")
  const [open, setOpen] = useState(shouldAutoExpand)
  const ts = TIER_STYLES[tier]

  // When a panel starts pre-opened (e.g. deep mode), fire onExpand once on mount
  const calledOnExpand = useRef(false)
  useEffect(() => {
    if (shouldAutoExpand && onExpand && !calledOnExpand.current) {
      calledOnExpand.current = true
      onExpand()
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = () => {
    if (!open && onExpand) onExpand()
    setOpen(v => !v)
  }

  const tokenWarning = estimatedTokens != null && estimatedTokens > 3000 && execMode !== "saver"

  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${open ? T.borderBright : T.border}`,
      borderRadius: 12,
      overflow: "hidden",
      transition: "border-color 0.15s ease",
    }}>
      {/* Header — always visible, click to toggle */}
      <button
        onClick={handleToggle}
        disabled={execMode === "saver" && tier > 1}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px", background: "transparent", border: "none",
          cursor: execMode === "saver" && tier > 1 ? "not-allowed" : "pointer",
          textAlign: "left",
        }}
      >
        {/* Tier badge */}
        <span style={{
          fontSize: 9, fontFamily: T.mono, fontWeight: 700,
          padding: "2px 6px", borderRadius: 4,
          background: `${ts.color}22`, color: ts.color,
          border: `1px solid ${ts.color}`,
          letterSpacing: "0.04em", flexShrink: 0,
        }} title={ts.title}>
          {ts.label}
        </span>

        <span style={{ fontSize: 13, fontWeight: 500, color: T.text, flex: 1 }}>{title}</span>

        {/* Token estimate badge */}
        {estimatedTokens != null && !open && execMode !== "saver" && (
          <span style={{
            fontSize: 10, fontFamily: T.mono, color: tokenWarning ? T.amber : T.text3,
            flexShrink: 0,
          }}>
            ~{estimatedTokens >= 1000 ? `${(estimatedTokens / 1000).toFixed(1)}K` : estimatedTokens} tokens
          </span>
        )}

        {execMode === "saver" && tier > 1 && (
          <span style={{ fontSize: 10, color: T.text3, fontFamily: T.mono }}>saver mode</span>
        )}

        {loading && (
          <span style={{ width: 14, height: 14, borderRadius: "50%", border: `2px solid ${T.border}`, borderTopColor: ts.color, display: "inline-block", animation: "spin 0.7s linear infinite", flexShrink: 0 }} />
        )}

        {!loading && (
          <span style={{ fontSize: 11, color: T.text3, flexShrink: 0, transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }}>
            ▾
          </span>
        )}
      </button>

      {/* Body */}
      {open && !loading && !error && (
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "1rem 1.25rem" }}>
          {children}
        </div>
      )}

      {open && loading && (
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "1.5rem", textAlign: "center" }}>
          <div style={{ fontSize: 12, color: T.text2 }}>Loading {title.toLowerCase()}…</div>
        </div>
      )}

      {open && error && (
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "10px 14px", background: T.redDim }}>
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}
    </div>
  )
}
