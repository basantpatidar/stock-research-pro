import { useState, useMemo } from "react"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts"
import type { PriceData } from "../../types"
import { T } from "../../theme"

const PERIODS = ["1d", "1W", "1M", "3M", "6M", "1Y"] as const
type Period = typeof PERIODS[number]

// Days of daily-candle history to show per period (unused for 1d which uses intraday)
const PERIOD_DAYS: Record<Exclude<Period, "1d">, number> = {
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
}

interface Props {
  data: PriceData
  defaultPeriod?: Period
}

const CustomTooltip = ({ active, payload, label, intraday }: any) => {
  if (!active || !payload?.length) return null
  const d = new Date(label)
  const dateLabel = intraday
    ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
  return (
    <div style={{
      background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: "8px 12px", fontSize: 12,
    }}>
      <div style={{ color: T.text2, marginBottom: 3, fontFamily: T.mono }}>{dateLabel}</div>
      <div style={{ color: T.text, fontFamily: T.mono, fontWeight: 500 }}>
        ${Number(payload[0].value).toFixed(2)}
      </div>
    </div>
  )
}

export function PriceChart({ data, defaultPeriod = "1d" }: Props) {
  const [activePeriod, setActivePeriod] = useState<Period>(defaultPeriod)
  const isPositive = data.change_pct_7d >= 0
  const lineColor = isPositive ? T.green : T.red
  const gradId = `pg-${isPositive ? "g" : "r"}`
  const isIntraday = activePeriod === "1d"

  const vp  = data.volume_profile
  const piv = data.pivots
  const sr  = data.support_resistance
  const orb = data.orb

  // Volume profile — multi-day charts only (computed from daily bars)
  const showVP  = !isIntraday && vp?.vpoc != null
  // Pivots — intraday chart only (daily pivot levels most useful for day trading)
  const showPiv = isIntraday && piv != null
  // Swing S/R — multi-day charts only
  const showSR  = !isIntraday && sr != null && (sr.resistance.length > 0 || sr.support.length > 0)
  // ORB — intraday only
  const showORB = isIntraday && orb != null

  const chartData = useMemo(() => {
    if (isIntraday) return data.intraday_history ?? []
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - PERIOD_DAYS[activePeriod as Exclude<Period, "1d">])
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return (data.price_history ?? []).filter(p => p.date >= cutoffStr)
  }, [data.price_history, data.intraday_history, activePeriod, isIntraday])

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Price History
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setActivePeriod(p)}
              style={{
                padding: "3px 10px", fontSize: 11, borderRadius: 20, cursor: "pointer",
                border: `1px solid ${activePeriod === p ? T.blue : T.border}`,
                background: activePeriod === p ? T.blueDim : "transparent",
                fontWeight: activePeriod === p ? 500 : 400,
                color: activePeriod === p ? T.blue : T.text2,
                fontFamily: T.mono,
                transition: "all 0.12s ease",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={lineColor} stopOpacity={0.2} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => isIntraday
              ? new Date(d).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
              : new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" })
            }
            tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip content={<CustomTooltip intraday={isIntraday} />} />
          {/* Volume Profile — multi-day */}
          {showVP && vp!.vpoc && (
            <ReferenceLine y={vp!.vpoc} stroke="#ffaa00" strokeDasharray="5 3" strokeWidth={1.5} />
          )}
          {showVP && vp!.vah && (
            <ReferenceLine y={vp!.vah} stroke="#22cc66" strokeDasharray="3 5" strokeWidth={1} />
          )}
          {showVP && vp!.val && (
            <ReferenceLine y={vp!.val} stroke="#ff6644" strokeDasharray="3 5" strokeWidth={1} />
          )}

          {/* Pivot Points — intraday (1d) */}
          {showPiv && (
            <>
              <ReferenceLine y={piv!.R2} stroke="#ff4444" strokeDasharray="2 4" strokeWidth={1}
                label={{ value: "R2", position: "insideTopRight", fontSize: 9, fill: "#ff4444" }} />
              <ReferenceLine y={piv!.R1} stroke="#ff7777" strokeDasharray="4 3" strokeWidth={1}
                label={{ value: "R1", position: "insideTopRight", fontSize: 9, fill: "#ff7777" }} />
              <ReferenceLine y={piv!.P}  stroke="#ffbb00" strokeDasharray="5 3" strokeWidth={1.5}
                label={{ value: "P",  position: "insideTopRight", fontSize: 9, fill: "#ffbb00" }} />
              <ReferenceLine y={piv!.S1} stroke="#66cc77" strokeDasharray="4 3" strokeWidth={1}
                label={{ value: "S1", position: "insideTopRight", fontSize: 9, fill: "#66cc77" }} />
              <ReferenceLine y={piv!.S2} stroke="#33aa55" strokeDasharray="2 4" strokeWidth={1}
                label={{ value: "S2", position: "insideTopRight", fontSize: 9, fill: "#33aa55" }} />
            </>
          )}

          {/* Swing S/R Levels — multi-day */}
          {showSR && sr!.resistance.map((lvl) => (
            <ReferenceLine key={`r-${lvl}`} y={lvl} stroke="#ff6644" strokeDasharray="3 4" strokeWidth={1}
              label={{ value: `R $${lvl}`, position: "insideTopRight", fontSize: 8, fill: "#ff6644" }} />
          ))}
          {showSR && sr!.support.map((lvl) => (
            <ReferenceLine key={`s-${lvl}`} y={lvl} stroke="#22ccaa" strokeDasharray="3 4" strokeWidth={1}
              label={{ value: `S $${lvl}`, position: "insideTopRight", fontSize: 8, fill: "#22ccaa" }} />
          ))}

          {/* ORB Levels — intraday (1d) */}
          {showORB && (
            <>
              <ReferenceLine y={orb!.orb_30.high} stroke="#7799ff" strokeDasharray="2 3" strokeWidth={1}
                label={{ value: "ORB30H", position: "insideTopLeft", fontSize: 8, fill: "#7799ff" }} />
              <ReferenceLine y={orb!.orb_30.low}  stroke="#7799ff" strokeDasharray="2 3" strokeWidth={1}
                label={{ value: "ORB30L", position: "insideTopLeft", fontSize: 8, fill: "#7799ff" }} />
              <ReferenceLine y={orb!.orb_15.high} stroke="#cc88ff" strokeDasharray="4 2" strokeWidth={1.5}
                label={{ value: "ORB15H", position: "insideTopLeft", fontSize: 8, fill: "#cc88ff" }} />
              <ReferenceLine y={orb!.orb_15.low}  stroke="#cc88ff" strokeDasharray="4 2" strokeWidth={1.5}
                label={{ value: "ORB15L", position: "insideTopLeft", fontSize: 8, fill: "#cc88ff" }} />
            </>
          )}

          <Area
            type="monotone" dataKey="close"
            stroke={lineColor} strokeWidth={1.5}
            fill={`url(#${gradId})`} dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Volume Profile legend — multi-day */}
      {showVP && vp && (
        <div style={{ display: "flex", gap: 14, marginTop: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
          {vp.vpoc && <span style={{ fontSize: 9, fontFamily: T.mono, color: "#ffaa00" }}>— — VPOC ${vp.vpoc.toFixed(2)}</span>}
          {vp.vah  && <span style={{ fontSize: 9, fontFamily: T.mono, color: "#22cc66" }}>- - VAH ${vp.vah.toFixed(2)}</span>}
          {vp.val  && <span style={{ fontSize: 9, fontFamily: T.mono, color: "#ff6644" }}>- - VAL ${vp.val.toFixed(2)}</span>}
          <span style={{ fontSize: 9, color: T.text3 }}>Volume Profile ({vp.period_days}d)</span>
        </div>
      )}

      {/* Swing S/R legend — multi-day */}
      {showSR && (sr!.resistance.length > 0 || sr!.support.length > 0) && (
        <div style={{ display: "flex", gap: 14, marginTop: 4, justifyContent: "flex-end", flexWrap: "wrap" }}>
          {sr!.resistance.map((lvl) => (
            <span key={`rl-${lvl}`} style={{ fontSize: 9, fontFamily: T.mono, color: "#ff6644" }}>↑ R ${lvl.toFixed(2)}</span>
          ))}
          {sr!.support.map((lvl) => (
            <span key={`sl-${lvl}`} style={{ fontSize: 9, fontFamily: T.mono, color: "#22ccaa" }}>↓ S ${lvl.toFixed(2)}</span>
          ))}
          <span style={{ fontSize: 9, color: T.text3 }}>Swing S/R</span>
        </div>
      )}

      {/* Pivot + ORB legend — intraday */}
      {showPiv && piv && (
        <div style={{ display: "flex", gap: 14, marginTop: 4, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#ff4444" }}>R2 ${piv.R2.toFixed(2)}</span>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#ff7777" }}>R1 ${piv.R1.toFixed(2)}</span>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#ffbb00" }}>P ${piv.P.toFixed(2)}</span>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#66cc77" }}>S1 ${piv.S1.toFixed(2)}</span>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#33aa55" }}>S2 ${piv.S2.toFixed(2)}</span>
          <span style={{ fontSize: 9, color: T.text3 }}>Classic Pivots</span>
        </div>
      )}
      {showORB && orb && (
        <div style={{ display: "flex", gap: 14, marginTop: 4, justifyContent: "flex-end", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#cc88ff" }}>
            ORB-15 {orb.orb_15.low.toFixed(2)}–{orb.orb_15.high.toFixed(2)}
          </span>
          <span style={{ fontSize: 9, fontFamily: T.mono, color: "#7799ff" }}>
            ORB-30 {orb.orb_30.low.toFixed(2)}–{orb.orb_30.high.toFixed(2)}
          </span>
          <span style={{
            fontSize: 9, fontFamily: T.mono, fontWeight: 600, padding: "1px 6px", borderRadius: 4,
            background: orb.orb_15.position === "above" ? "#22cc6630" : orb.orb_15.position === "below" ? "#ff664430" : "#ffffff15",
            color: orb.orb_15.position === "above" ? "#22cc66" : orb.orb_15.position === "below" ? "#ff6644" : T.text3,
          }}>
            {orb.orb_15.position === "above" ? "↑ Above ORB" : orb.orb_15.position === "below" ? "↓ Below ORB" : "Inside ORB"}
          </span>
          {orb.orb_15.breakout !== "none" && (
            <span style={{ fontSize: 9, color: "#ffbb00", fontFamily: T.mono }}>
              ✓ Breakout {orb.orb_15.breakout}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
