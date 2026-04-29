# Stock Research Pro — Feature Roadmap

> Single-stop platform for day traders and long-term investors to make confident buy/sell decisions.
> Last updated: 2026-04-29

---

## Design Principle: Every Data Point Must Be Actionable

Raw numbers are useless to most users. Every metric in this app must follow the **Signal-Explain-Act** framework:

1. **Signal** — Convert the metric to a clear label: `BULLISH / BEARISH / NEUTRAL` with strength (strong/moderate/weak)
2. **Plain English** — One sentence: "What this means for you right now"
3. **Context** — Where does this reading sit historically? (e.g., "Top 10% of all readings in the past year")
4. **Direction** — Is it improving or deteriorating vs last period? (↑ / ↓ / →)
5. **Action context** — What should you consider doing given this signal?

### Signal Interpretation System (applies to all sprints)

Every panel and every metric renders with:

```
[🟢 BULLISH] Piotroski F-Score: 8/9
"Company is strengthening across profitability, debt, and efficiency.
Historically, F-Score ≥ 8 precedes outperformance over the next 12 months."
↑ Improved from 6 last quarter
```

```
[🔴 HIGH RISK] Beneish M-Score: -1.4
"Earnings manipulation likely. Financial patterns match companies that
later restated or restated earnings. Treat reported EPS with skepticism."
→ Unchanged from prior quarter
```

```
[🟡 NEUTRAL] GEX: +$1.2B
"Market makers are long gamma — they will buy dips and sell rips.
Expect range-bound price action until the next catalyst or expiry."
↓ Falling — gamma environment weakening
```

### LLM Signal Synthesis (per ticker)
After all signals are computed, the LLM writes a 3–5 sentence narrative:
> "AAPL shows strong earnings quality (Piotroski 8, clean accruals) but the
> options market is pricing elevated near-term risk (IVR 72, negative skew).
> For long-term investors, the financial strength supports accumulation on
> weakness. Day traders should expect larger-than-normal intraday swings
> given the negative GEX environment heading into expiry Friday."

### Color and Icon System (consistent across all panels)
| Signal | Color | Icon | Meaning |
|---|---|---|---|
| Strong Buy | `#00ff88` green | 🟢 ▲▲ | Multiple confirming bullish signals |
| Bullish | `#22cc66` green | 🟢 ▲ | Bullish lean, not unanimous |
| Neutral | `#ffaa00` amber | 🟡 → | No strong directional signal |
| Bearish | `#ff6644` orange | 🔴 ▼ | Bearish lean |
| Strong Sell | `#ff2222` red | 🔴 ▼▼ | Multiple confirming bearish signals |
| Risk Flag | `#ff4400` red | ⚠️ | Risk/manipulation/distress detected |

---

## Current App Coverage (V2 Baseline)

| Category | Already Built |
|---|---|
| Price & Technicals | RSI, MACD, Bollinger, VWAP, 50d/200d MA, ATR |
| Earnings | History, beat/miss rate, surprise %, forward EPS, revision direction, implied move |
| Fundamentals | P/E, PEG, margins, debt/equity, FCF, ROE, market cap |
| News & Sentiment | NewsAPI headlines + sentiment, Reddit/StockTwits |
| Analyst | Consensus, price target, rating changes |
| Options | Put/call ratio, IV, ATM straddle implied move |
| Short Interest | Short % of float, days to cover, squeeze signal |
| Insider | SEC Form 4 trades, buy/sell balance |
| Institutional | 13F top holders |
| Congressional | STOCK Act trades |
| Macro | VIX, S&P, oil, yields |
| Sector | 11-sector heatmap |
| LLM (Tier 3) | Investor personas, bull/bear debate, earnings transcript NLP, backtest |

---

## Sprint Roadmap

---

### Sprint 1 — Earnings Quality Scores
**Goal:** Surface the 4 models professional analysts use to assess whether earnings are real and the company is financially healthy.
**Data source:** yfinance financial statements (already being pulled)
**New API cost:** $0
**Backend:** New tool `earnings_quality.py`
**Frontend:** New `EarningsQualityPanel` in Tier 2

#### Features
| Model | What it computes | Output |
|---|---|---|
| **Beneish M-Score** | 8 financial ratios that predict earnings manipulation. Score > -2.22 = manipulator likely. Caught Enron, WorldCom before collapse. | Score + risk label + plain English |
| **Piotroski F-Score** | 9-point checklist: profitability (4) + leverage/liquidity (3) + efficiency (2). 8–9 = strong buy, 0–1 = strong short. | Score/9 + signal label + per-component breakdown |
| **Altman Z-Score** | Bankruptcy proximity model. Below 1.81 = distress, above 2.99 = safe. Sector-relative context matters. | Score + zone label + peer context |
| **Accruals Ratio (Sloan)** | (Net Income - CFO - CFI) / Avg Assets. High accruals = paper earnings not backed by cash. > 5% = red flag. | % + quality label + cash vs accrual breakdown |

#### Signal interpretation for each
- **M-Score**: "This company's financial patterns match those of earnings manipulators" vs "No manipulation signals detected"
- **F-Score**: Component-by-component traffic lights so user sees exactly which checks passed/failed
- **Z-Score**: Gauge visualization with zones (Distress / Grey / Safe), compared to sector median
- **Accruals**: Pie chart of earnings source (cash vs accrual) with plain English label

---

### Sprint 2 — Options Intelligence Dashboard
**Goal:** Give day traders the options market signals professionals pay $150/month for.
**Data source:** yfinance options chains (already pulling for implied move)
**New API cost:** $0
**Backend:** New tool `options_intelligence.py`
**Frontend:** New `OptionsIntelligencePanel` in Tier 2

#### Features
| Metric | What it tells you |
|---|---|
| **GEX (Gamma Exposure)** | Market maker gamma position. Positive = suppressed vol (range). Negative = amplified moves. Flip levels = volatility triggers. |
| **Max Pain** | Strike where option sellers profit most at expiry. Price gravitates here near expiration. |
| **IV Rank / IV Percentile** | IVR > 50 = options expensive (sell premium). IVR < 20 = options cheap (buy premium / long convexity). |
| **Put/Call Skew** | How much more expensive OTM puts are vs equivalent calls. Steep = heavy downside hedging. |
| **Volatility Term Structure** | Short vs long dated IV across expirations. Backwardation = near-term event fear. |
| **Key GEX Levels** | Price levels where gamma flips — act as support/resistance because MMs delta-hedge there. |

#### Signal interpretation
- GEX: "Market makers will DAMPEN moves today" vs "Market makers will AMPLIFY moves today — expect volatile price action"
- IVR: "Options are unusually expensive — buying options here is low edge" vs "Options are cheap — good time to buy protection or speculative calls"
- Max Pain: "Options market gravity points to $XXX by Friday" with distance from current price

---

### Sprint 3 — FRED Macro Dashboard
**Goal:** Replace the basic VIX/yields macro panel with the credit and rates data institutional PMs actually watch.
**Data source:** FRED API (St. Louis Fed) — completely free, no rate limits
**New API cost:** $0
**Backend:** Extend `macro.py` with FRED integration
**Frontend:** Expanded `MacroPage` + ticker-level macro context panel

#### Features
| Indicator | FRED Series | Why it matters |
|---|---|---|
| **HY Credit Spread** | BAMLH0A0HYM2 | Widens 6–8 weeks before equity selloffs. Bond market's fear gauge. |
| **IG Credit Spread** | BAMLC0A0CM | Corporate credit health baseline. |
| **10-Year Real Yield** | DFII10 | Single most important variable for growth stock valuations. |
| **TIPS Breakeven Inflation** | T10YIE | Market-implied inflation. Drives commodity vs bond rotation. |
| **Yield Curve 2s10s** | T10Y2Y | Inverted = recession signal 12–18 months ahead. Every US recession since 1970. |
| **Yield Curve 3m10y** | T10Y3M | NY Fed preferred recession predictor. |
| **M2 Money Supply Growth** | M2SL YoY | Global liquidity proxy. M2 expansion leads equity rallies by 6–12 months. |
| **SOFR Rate** | SOFR | Interbank stress. Spikes = liquidity crisis risk. |

#### Additional cross-asset signals (yfinance)
| Signal | Ticker | What it tells you |
|---|---|---|
| Copper/Gold Ratio | HG=F / GC=F | Risk-on vs risk-off. Leads 10-year yield and equity direction. |
| Dollar Index | DX-Y.NYB | Strong dollar = headwind for EM, commodities, multinationals. |
| Baltic Dry Index | ^BDIY | Global trade volume leading indicator. |

#### Signal interpretation
- Credit spreads: "Credit markets are calm — equities have a green light" vs "HY spreads spiking — bond market sees stress not visible in stocks yet"
- Yield curve: "Yield curve inverted for X months — historically this precedes recession within 12–18 months"
- Real yield: "Real yields at X% — this level historically compresses growth stock multiples by Y×"

---

### Sprint 4 — Volume Profile on Price Charts
**Goal:** Add the single most-used professional technical tool that no retail platform surfaces well.
**Data source:** yfinance OHLCV (already pulling)
**New API cost:** $0
**Backend:** Compute VPOC/VAH/VAL from historical price/volume data
**Frontend:** Overlay on existing price chart in `PriceChart.tsx`

#### Features
| Level | Meaning | Signal |
|---|---|---|
| **VPOC** (Volume Point of Control) | Most volume traded = price magnet | "Price will likely revisit $XXX — highest volume anchor" |
| **VAH** (Value Area High) | Top of 70% volume zone | Resistance when price is above, support when below |
| **VAL** (Value Area Low) | Bottom of 70% volume zone | Support when price is above, resistance when below |
| **HVN** (High Volume Nodes) | Zones of price acceptance | "Strong support/resistance — market spent a lot of time here" |
| **LVN** (Low Volume Nodes) | Price rejection zones | "Price moves through this level quickly — low resistance" |

---

### Sprint 5 — Portfolio Risk Page
**Goal:** Turn the app from a ticker lookup into a real portfolio management tool.
**Data source:** yfinance historical prices (multi-ticker)
**New API cost:** $0
**Backend:** New `portfolio_risk.py` tool
**Frontend:** New `PortfolioPage` (6th page)

#### Features
| Metric | What it enables |
|---|---|
| **Correlation Matrix** | Are you actually diversified or do all positions move together? |
| **VaR / CVaR** (95% / 99%) | Worst-case loss with and beyond the confidence threshold |
| **Maximum Drawdown + Calmar Ratio** | How badly has this portfolio blown up historically vs its returns? |
| **Beta-adjusted net exposure** | Am I actually 60% long market, not 100% in a defensive-heavy book? |
| **Factor exposure decomposition** | Am I stock-picking or just long momentum/value/size? |
| **Effective number of bets (1/HHI)** | A 20-stock portfolio might have the risk of only 4 independent bets |
| **Stress test scenarios** | 2008 GFC / 2020 COVID / 2022 rate shock — portfolio response |
| **Liquidity score** | Days to liquidate each position without moving the market |

---

### Sprint 6 — Enhanced Earnings Call NLP
**Goal:** Go beyond basic sentiment to what institutional NLP platforms charge $50K/year for.
**Data source:** Existing earnings transcript tool (already in Tier 3)
**New API cost:** $0 (uses existing LLM)
**Backend:** Extend `earnings_transcript.py`

#### Features
| Analysis | What it detects |
|---|---|
| **Hedging language frequency** | Count of "uncertain", "challenging", "difficult", "headwinds" vs prior quarters |
| **Management specificity score** | Vague guidance ("we expect improvement") vs specific ("we guide to 15–17% growth") |
| **Forward vs backward-looking ratio** | Confident management talks about the future; defensive management explains the past |
| **Analyst question aggression score** | Are analysts pushing back hard? Softballs vs probing questions |
| **Language drift vs prior quarter** | Significant tone change flags automatically |
| **CEO vs CFO sentiment split** | CFOs are typically more conservative; when they're bullish too, it's significant |

---

### Sprint 7 — Short Squeeze Intelligence (Enhanced)
**Goal:** Combine all available signals into a single squeeze probability score.
**Data source:** yfinance + FINRA public data (free weekly)
**New API cost:** $0

#### Composite Squeeze Score inputs
| Signal | Source | Weight |
|---|---|---|
| Short % of float | yfinance | High |
| Days to cover | yfinance | High |
| CTB trend (estimated) | Derived from float utilization | Medium |
| Float utilization rate | Derived from shares short / available float | High |
| Recent % change in short interest | yfinance month-over-month | Medium |
| Options implied move vs historical | Already computed | Medium |
| Social mention velocity | Reddit/StockTwits | Low |

**Output:** "Squeeze probability: HIGH (82/100) — 94% utilization, short interest rising, cost-to-borrow proxy elevated, social volume spiking"

---

### Sprint 8 — Alternative Data (Paid tier, Phase 3)
**Goal:** Add the alt-data signals hedge funds pay millions for, via affordable APIs.

| Feature | Provider | Cost | Signal |
|---|---|---|---|
| Web traffic per company | SimilarWeb API | Free tier | Revenue proxy for consumer/e-commerce |
| Job postings velocity | Adzuna API | Free | R&D intensity, sales pipeline health |
| App download rank | data.ai free tier | Limited | Consumer engagement leading indicator |
| Dark pool print levels | FINRA ATS (weekly, free) | Free | Institutional accumulation zones |
| Unusual options activity | Unusual Whales API | $35/mo | Smart money positioning |
| Real-time short borrow rate | Ortex | $200/mo | Squeeze precursor — most actionable signal |

---

## Interpretation Framework — Implementation Checklist

For every new metric added to the app, it must have:

- [ ] Threshold-based signal label (bullish/bearish/neutral + strength)
- [ ] Plain English "what this means" sentence (1 line, jargon-free)
- [ ] Direction indicator (improving ↑ / deteriorating ↓ / stable →) vs prior period
- [ ] Historical context ("Top 15% of all readings in past year")
- [ ] Color coding consistent with Signal Color System above
- [ ] Tooltip with: metric name, formula/definition, how to act on it
- [ ] Contribution to the overall ticker Convergence Score

---

## Data Source Quick Reference

| Source | Cost | What it covers |
|---|---|---|
| yfinance | Free | Price, OHLCV, options, financials, earnings, analyst, insider, institutional |
| NewsAPI | Free tier | News headlines |
| FRED API | Free | Credit spreads, real yields, yield curve, M2, SOFR, inflation breakevens |
| Reddit PRAW | Free | WallStreetBets sentiment |
| StockTwits | Free | Retail sentiment |
| FINRA ATS | Free (weekly) | Dark pool volume by stock |
| Adzuna API | Free tier | Job postings velocity |
| LLM (Groq/Cerebras/etc.) | Free/cheap tiers | All LLM synthesis and analysis |

---

## Outstanding Items (pre-roadmap backlog)
- [ ] Portfolio risk page (multi-stock exposure view)
- [ ] Email alerts via SendGrid/SES (notifier.py stubbed)
- [ ] Full JWT auth (auth.py ready to swap)
- [ ] Paper trade journal persistence in PostgreSQL
- [ ] Crypto correlation tracker
- [ ] Expand screener beyond 30 hardcoded tickers
- [ ] Frontend usage bars in nav (% used inline)
- [ ] pytrends added to requirements.txt
