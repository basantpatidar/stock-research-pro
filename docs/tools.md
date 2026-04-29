# docs/tools.md — Tool catalog, invocation pattern, conventions, how to add a tool
# Sections: grep -n "SEC:" docs/tools.md
# SEC:TOOL_CONVENTIONS   Rules, invocation pattern, yfinance wrapper
# SEC:V1_TOOLS           20 V1 tools (name, source, what it returns)
# SEC:V2_TOOLS           6 V2 new tools (Tier 3 deep analysis)
# SEC:ADD_TOOL           Steps to add a new tool

---

<!-- SEC:TOOL_CONVENTIONS -->
## Tool Conventions

**All tools:**
- Use `@tool` decorator from `langchain_core.tools`
- Accept typed kwargs; invoked via `tool_fn.invoke({"ticker": sym, ...})`
- NEVER raise exceptions — always `return {"error": "reason"}` on failure
- One file per tool: `backend/app/tools/<name>.py`
- Re-exports: `analyst.py`, `earnings.py`, etc. re-export from `core_tools.py` or `remaining_tools.py`

**yfinance access:**
Always use `get_ticker(symbol)` from `_yf_client.py` — never `yf.Ticker()` directly.
Reason: `_yf_client.py` provides a global thread-safe rate limiter + poisoned-crumb detection.
Rate: `YF_REQUESTS_PER_SECOND` env var (default 2/s). All tool calls are serialized through one lock.

**Invocation from FastAPI:**
```python
result = await asyncio.to_thread(tool_fn.invoke, {"ticker": sym})
```
Tools are synchronous (blocking I/O); `asyncio.to_thread` keeps the async event loop free.

---

<!-- SEC:V1_TOOLS -->
## V1 Tool Catalog (20 tools, all in `backend/app/tools/`)

| Tool function | File | Data source | Key fields returned |
|---|---|---|---|
| `get_price` | price.py | yfinance | current_price, change_pct_today, change_pct_7d, OHLCV, volume_ratio, price_history |
| `get_technicals` | technicals.py | yfinance | rsi_14, rsi_signal, macd (crossover), bollinger_bands, moving_averages, vwap_20d |
| `get_news_impact` | news.py | NewsAPI | news[] (headline, sentiment, source, url), sentiment_breakdown, articles_found |
| `get_sentiment` | sentiment.py | StockTwits + Reddit | bullish_pct, bearish_pct, summary |
| `get_analyst_consensus` | analyst.py → core_tools | yfinance | consensus, price_target, upside_pct, rating_counts, recent_rating_changes |
| `get_earnings` | earnings.py → core_tools | yfinance | next_earnings_date, earnings_history[], beat_rate_pct |
| `get_fundamentals` | fundamentals.py → core_tools | yfinance | pe_ratio, peg_ratio, profit_margin, debt_to_equity, free_cash_flow |
| `get_options_signals` | options.py → core_tools | yfinance | put_call_ratio, iv, unusual_activity |
| `get_insider_activity` | insider.py → core_tools | yfinance (Form 4) | insider_signal, recent_trades[] |
| `get_institutional_changes` | institutional.py → core_tools | yfinance (13F) | top_holders[] |
| `get_short_interest` | short_interest.py → core_tools | yfinance | short_float_pct, days_to_cover, short_squeeze_potential |
| `get_geopolitical_events` | geopolitical.py | NewsAPI | events[] (title, severity, impacted_sectors) |
| `get_macro_environment` | macro.py → remaining_tools | yfinance | vix, sp500, oil_wti, yields, gold — NO ticker arg |
| `get_sector_heatmap` | sector.py → remaining_tools | yfinance | 11 sector ETFs 5d perf — NO ticker arg |
| `get_cascade_impact` | cascade.py → remaining_tools | LLM | causal chain: event → stock impact |
| `get_price_forecast` | forecast.py → remaining_tools | yfinance + LLM | forecast text, targets {days, weeks, quarter} |
| `get_risk_reward` | risk_reward.py → remaining_tools | yfinance | entry_price, stop_loss, target_price, risk_reward_ratio |
| `run_screener` | screener.py → remaining_tools | yfinance | matching tickers[] with price/cap/volume/sector |
| `get_convergence_score` | convergence.py → remaining_tools | all signals | convergence_score (0-100), label, signals[], bullish/bearish count |
| `get_trends` | google_trends.py → remaining_tools | pytrends | interest spike detection |

**Note:** `get_macro_environment` and `get_sector_heatmap` take NO arguments — invoke with `{}`.

---

<!-- SEC:V2_TOOLS -->
## V2 New Tools (Tier 3 deep analysis, `backend/app/tools/new/`)

| Tool function | File | Est. tokens | Key args | Returns |
|---|---|---|---|---|
| `investor_personas` | investor_personas.py | ~5,000 | `ticker` | Buffett/Graham/Burry/Lynch/Wood verdicts |
| `bull_bear_debate` | bull_bear.py | ~6,000 | `ticker` | bull_case, bear_case, judge_verdict |
| `get_congressional_trades` | congressional.py | 0 | `ticker`, `days=180` | recent_trades[], net_sentiment, total_trades |
| `analyze_earnings_transcript` | earnings_transcript.py | ~4,000 | `ticker` | tone, guidance, key_risks, trade_implication |
| `run_backtest` | backtester.py | 0 (pure pandas) | `ticker`, `strategy="all"`, `period="2y"` | win_rate, avg_return, total_return vs buy-and-hold |
| `analyze_paper_trade` | paper_trade.py | ~800 | `ticker`, `entry_price`, `entry_date`, `position_size=1000`, `trade_type="long"`, `stop_loss?`, `target_price?`, `exit_price?`, `exit_date?` | P&L analysis, AI coaching |

---

<!-- SEC:ADD_TOOL -->
## How to Add a New Tool

1. Create `backend/app/tools/my_tool.py`:
   ```python
   from langchain_core.tools import tool
   from app.tools._yf_client import get_ticker

   @tool
   def my_tool(ticker: str) -> dict:
       """Docstring used by LangGraph agent."""
       try:
           ...
           return {"ticker": ticker, "result": ...}
       except Exception as e:
           return {"error": f"my_tool failed: {str(e)}"}
   ```

2. Wire into the LangGraph agent — `backend/app/agent/graph.py`:
   ```python
   from app.tools.my_tool import my_tool
   ALL_TOOLS = [..., my_tool]
   ```

3. If it's a Tier 2 or Tier 3 tool, add it to `research_v2.py`:
   - Add to `_TIER2_TOOLS` or `_TIER3_TOOLS` dict
   - Add token estimate to `_TOKEN_ESTIMATES`

4. Add token estimate to `docs/tools.md` (this file) and update `CLAUDE.md` Recent Changes.

5. Write a test in `backend/tests/tools/test_tools.py` — mock yfinance, assert `{"error": ...}` path works.
