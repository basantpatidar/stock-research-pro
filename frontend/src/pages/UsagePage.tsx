import { useState, useEffect } from "react"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import { api } from "../services/api"
import { T } from "../theme"

interface TodaySummary {
  tokens_today: number
  tokens_today_pct: number
  api_calls_today: number
  tickers_today: string[]
  warning?: string
}

interface DailyPoint { date: string; tokens: number; api_calls: number }

interface UsageLimits {
  token_daily_limit: number
  token_weekly_limit: number
  token_monthly_limit: number
  api_calls_daily_limit: number
}

interface HistoryData {
  daily: DailyPoint[]
  limits?: UsageLimits
}

const StatCard = ({ label, value, sub, pct, color }: {
  label: string; value: string; sub?: string; pct?: number; color?: string
}) => (
  <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
    <div style={{ fontSize: 10, color: T.text3, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 8 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 700, fontFamily: T.mono, color: color || T.text, marginBottom: sub ? 4 : 0 }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: T.text2 }}>{sub}</div>}
    {pct != null && (
      <div style={{ marginTop: 8 }}>
        <div style={{ height: 4, background: T.border, borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            width: `${Math.min(100, pct)}%`, height: "100%", borderRadius: 2,
            background: pct >= 80 ? T.red : pct >= 50 ? T.amber : T.green,
            transition: "width 0.6s ease",
          }} />
        </div>
        <div style={{ fontSize: 10, color: T.text3, marginTop: 4, fontFamily: T.mono }}>
          {pct.toFixed(1)}% of daily limit
        </div>
      </div>
    )}
  </div>
)

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 12 }}>
      <div style={{ color: T.text2, marginBottom: 4, fontFamily: T.mono }}>{label}</div>
      <div style={{ color: T.blue, fontFamily: T.mono }}>
        {payload[0].value >= 1000 ? `${(payload[0].value / 1000).toFixed(1)}K` : payload[0].value} tokens
      </div>
    </div>
  )
}

export function UsagePage() {
  const [today, setToday] = useState<TodaySummary | null>(null)
  const [history, setHistory] = useState<HistoryData | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [todayRes, histRes] = await Promise.all([
        api.get("/usage/today"),
        api.get("/usage/history"),
      ])
      setToday(todayRes.data)
      setHistory(histRes.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchAll() }, [])

  const chartData = (history?.daily ?? [])
    .slice(-30)
    .map(d => ({ date: d.date.slice(5), tokens: d.tokens }))

  const maxTokens = Math.max(...chartData.map(d => d.tokens), 1)

  const limits = history?.limits

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem 1.25rem" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: T.text }}>Usage &amp; Guard Rails</div>
          <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>Token consumption and API call tracking</div>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          style={{
            fontSize: 12, color: T.text2, background: T.surface2,
            border: `1px solid ${T.border}`, borderRadius: 7,
            padding: "6px 14px", cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Loading…" : "↻ Refresh"}
        </button>
      </div>

      {/* Today summary cards */}
      {today && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
          <StatCard
            label="Tokens Today"
            value={today.tokens_today >= 1000 ? `${(today.tokens_today / 1000).toFixed(1)}K` : String(today.tokens_today)}
            sub={limits ? `of ${(limits.token_daily_limit / 1000).toFixed(0)}K daily limit` : undefined}
            pct={today.tokens_today_pct}
            color={today.tokens_today_pct >= 80 ? T.red : today.tokens_today_pct >= 50 ? T.amber : T.green}
          />
          <StatCard
            label="API Calls Today"
            value={String(today.api_calls_today)}
            sub={limits ? `of ${limits.api_calls_daily_limit} daily limit` : undefined}
          />
          <StatCard
            label="Tickers Researched"
            value={String(today.tickers_today?.length ?? 0)}
            sub={today.tickers_today?.slice(0, 5).join(", ")}
          />
        </div>
      )}

      {today?.warning && (
        <div style={{
          background: T.amberDim, border: `1px solid ${T.amber}`,
          borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 13, color: T.amber,
        }}>
          ⚠ {today.warning}
        </div>
      )}

      {/* 30-day bar chart */}
      {chartData.length > 0 && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1rem 1.25rem", marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
            Token Usage — Last 30 Days
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barSize={10}>
              <XAxis
                dataKey="date" tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
                tickLine={false} axisLine={false} interval={4}
              />
              <YAxis
                tick={{ fontSize: 10, fill: T.text3, fontFamily: T.mono }}
                tickLine={false} axisLine={false}
                tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: T.surface2 }} />
              <Bar dataKey="tokens" radius={[3, 3, 0, 0]}>
                {chartData.map((d, i) => (
                  <Cell
                    key={i}
                    fill={d.tokens > maxTokens * 0.8 ? T.red : d.tokens > maxTokens * 0.5 ? T.amber : T.blue}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Limits table */}
      {limits && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: T.text2, textTransform: "uppercase", letterSpacing: "0.06em", padding: "10px 16px", background: T.surface2, borderBottom: `1px solid ${T.border}` }}>
            Guard Rail Limits
          </div>
          {[
            { label: "Tokens / day",   value: `${(limits.token_daily_limit / 1000).toFixed(0)}K` },
            { label: "Tokens / week",  value: `${(limits.token_weekly_limit / 1000).toFixed(0)}K` },
            { label: "Tokens / month", value: `${(limits.token_monthly_limit / 1000).toFixed(0)}K` },
            { label: "API calls / day",value: String(limits.api_calls_daily_limit) },
          ].map(({ label, value }, i, arr) => (
            <div key={label} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 16px",
              borderBottom: i < arr.length - 1 ? `1px solid ${T.border}` : "none",
            }}>
              <span style={{ fontSize: 13, color: T.text2 }}>{label}</span>
              <span style={{ fontSize: 13, fontFamily: T.mono, fontWeight: 500, color: T.text }}>{value}</span>
            </div>
          ))}
          <div style={{ padding: "8px 16px", background: T.surface2, borderTop: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 11, color: T.text3 }}>
              Limits are set via environment variables. Edit <code style={{ fontFamily: T.mono, color: T.blue }}>.env</code> to change them.
            </span>
          </div>
        </div>
      )}

      {!today && !loading && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 14, padding: "3rem", textAlign: "center" }}>
          <div style={{ fontSize: 28, color: T.text3, fontFamily: T.mono, marginBottom: 10 }}>📊</div>
          <div style={{ color: T.text2 }}>Click refresh to load usage data</div>
        </div>
      )}
    </div>
  )
}
