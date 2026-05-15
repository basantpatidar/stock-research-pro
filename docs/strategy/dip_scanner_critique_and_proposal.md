# A Counter-Proposal for the Dip Scanner Logic (API-Friendly Version)

## 1. Introduction

The current Dip Scanner implementation provides a solid foundation, utilizing a purely computational, zero-LLM approach based on standard technical indicators. It is designed to identify intraday dip-buying opportunities by assigning a score based on factors like RSI, VWAP proximity, and relative volume.

This document presents a critique of the existing additive scoring model and proposes a more robust, context-aware alternative that respects the project's constraint of using only free, rate-limited APIs like `yfinance`. The goal is to increase the scanner's win rate and reduce risk by focusing on high-confluence setups within a favorable market context.

---

## 2. Critique of the Current "Additive Scoring" Model

The current model, where `score = 50 + delta1 + delta2...`, has several inherent weaknesses:

*   **Over-Reliance on Lagging Indicators:** Indicators like RSI are calculated from past price action. By the time a 5-minute RSI becomes "oversold," the asset might already be in a strong downtrend, leading to premature entries.

*   **Assumes Independence of Factors:** The additive model treats each signal (RSI, VWAP, etc.) as an independent piece of information. In reality, their predictive power comes from **confluence**. An oversold RSI at a key support level is exponentially more powerful than the sum of their individual scores.

*   **Risk of "Catching a Falling Knife":** The primary weakness is its "inside-out" focus. The scanner analyzes an ETF's price action in isolation. However, during a market-wide panic, no amount of "oversold" on a single ETF will prevent it from going lower. The scanner lacks a robust, API-friendly mechanism to answer the crucial question: **"Is this a dip in a healthy market, or is the entire market falling?"**

---

## 3. Proposed Alternative: The "Market Context First" Funnel

I propose replacing the scoring system with a **multi-layered filter and confluence model**. This approach acts as a funnel, ensuring that the broad market conditions are favorable *before* ever looking for a specific ETF setup. This entire model is designed to work within the `yfinance` API limitations.

Think of it as a checklist, not a race. Every condition must be met.

### **Layer 1: The Higher Timeframe & Volatility Regime (The "Weather")**

*This filter runs once at the market open (or on the first scan) to set the bias for the day. It requires only one API call for SPY and one for VIX.*

1.  **Primary Trend Filter:** Is the market in a broader uptrend?
    *   **Implementation:** Check if the S&P 500 (SPY) is trading above its 20-day Exponential Moving Average (EMA) using daily data.
    *   **Logic:** We only want to buy dips if the prevailing market trend is bullish or neutral. If SPY is below this key moving average, the dip scanner is **disabled for the day**, or operates in a "very high caution" mode with much stricter criteria.

2.  **Volatility Regime Filter:** What is the current market fear level?
    *   **Implementation:** Use the VIX level from a single daily data fetch.
    *   **Logic:**
        *   **VIX < 18 (Complacency):** Dips are likely shallow. Scanner requires less of a dip to trigger.
        *   **VIX 18-30 (Healthy Volatility):** The sweet spot for mean-reversion. This is the ideal operating environment.
        *   **VIX > 30 (Panic):** Dips can be extreme. Scanner requires a much deeper pullback and clear signs of selling exhaustion before firing a signal.

### **Layer 2: Intraday "Internal Breadth" (The "Tide")**

*This filter runs every 5 minutes to gauge market-wide pressure using the same ETF data we are already fetching. It adds **zero extra API calls**.*

Instead of relying on specialized data like `$TICK` or `$ADD`, we create a proxy using our Tier 1 ETF list (SPY, QQQ, IWM, DIA).

1.  **Correlated Selling Filter:** Is the selling pressure broad-based?
    *   **Implementation:** Using the 5-minute intraday data for the Tier 1 ETFs, check how many are simultaneously down more than a certain threshold (e.g., -0.75%) from their opening price.
    *   **Logic:** A true, buyable panic dip is market-wide. We should only be interested when the selling is correlated across different market segments (large-cap, tech, small-cap).
    *   **Gate:** The scanner only proceeds if **at least 3 of the 4 Tier 1 ETFs** meet the dip criteria. This confirms a market-wide pullback, not just weakness in a single sector.

2.  **Selling Momentum Filter:** Is the selling pressure still accelerating?
    *   **Implementation:** Once the "Correlated Selling" gate is passed, we analyze the rate of change on the same ETFs.
    *   **Logic:** We must avoid entering while sellers are in full control. We can measure this by checking if the majority of our Tier 1 ETFs are still making new 5-minute lows.
    *   **Gate:** The scanner only proceeds if **at least 2 of the 4 Tier 1 ETFs have failed to make a new low** in the most recent 5-minute candle. This indicates the immediate downward momentum is fading.

### **Layer 3: The High-Confluence ETF Entry (The "Setup")**

*This filter only runs if Layers 1 and 2 have given a green light. This is where we find our specific entry on an individual ETF.*

A signal is fired only when the following three conditions align **simultaneously**:

1.  **Pullback to a Key Level:** The ETF must be trading at or near a significant, pre-defined support level. This includes the intraday VWAP, key pivot levels (S1, S2), or short-term EMAs (e.g., 8 or 21-period EMA on the 5-minute chart).

2.  **Price Action Confirmation:** We need to see real-time proof that buyers are stepping in *at that level*.
    *   **Implementation:** Look for a **strong bullish candlestick pattern** on the 5-minute chart, such as a **Hammer** or a **Bullish Engulfing** candle.
    *   **Logic:** This is direct evidence that the market rejected lower prices at the support level.

3.  **Volume Confirmation:** The buying must be backed by volume.
    *   **Implementation:** The confirmation candle (the Hammer or Engulfing) should occur on **volume that is above the recent average** for that time of day.
    *   **Logic:** This confirms that the buying interest is genuine and has conviction.

---

## 4. Side-by-Side Comparison

| Feature | Current "Scoring" Logic | Proposed "Funnel" Logic | Advantage of Proposal |
| :--- | :--- | :--- | :--- |
| **Core Concept** | Additive score from multiple indicators | Sequential filter based on market context | More robust, less prone to single-indicator failure |
| **Market Context** | Limited (VIX level) | Foundational (Daily Trend + **Internal Breadth**) | Avoids buying dips during a crash, **API-friendly** |
| **Primary Signal** | Oversold RSI (<35) | Price pullback to a key structural level | Focuses on structure, not just momentum |
| **Confirmation** | RVOL declining, hammer candle (+5 pts) | **Required** bullish candle on high volume at support | Demands real-time proof of buyers before entry |
| **Key Question** | "Is the ETF oversold?" | "Is the market healthy enough to buy this dip?" | Drastically improves risk management |

---

## 5. Example Trade Walkthrough (Proposed Logic)

*   **Time:** 10:30 AM ET
*   **Layer 1 (Weather):**
    *   SPY is above its 20-day EMA. **(Condition MET: Bullish Trend)**.
    *   VIX is at 21. **(Condition MET: Healthy Volatility)**.
*   **Layer 2 (Tide):**
    *   At 10:25 AM, SPY, QQQ, and IWM are all down >0.75% from their open. DIA is down 0.5%. **(Condition MET: Correlated Selling, 3 of 4)**.
    *   In the 10:30 AM candle, SPY and IWM do not make a new low compared to the 10:25 candle. **(Condition MET: Selling Momentum Fading, 2 of 4)**.
*   **Layer 3 (Setup):**
    *   The market is now cleared to look for a buy. The scanner observes QQQ.
    *   QQQ is approaching its 15-minute 21-period EMA at $442.
    *   The 10:30 AM 5-minute candle for QQQ forms a **Hammer candle right on the EMA** on **1.5x average volume**. **(All 3 Setup Conditions MET)**.
*   **==> FIRE BUY SIGNAL for QQQ at $442.50.**

---

## 6. Implementation Questions for Claude

1.  **State Management:** This logic is more of a state machine (e.g., "waiting for correlated dip," "waiting for momentum to fade"). What is the most effective way to implement this stateful logic within our existing `APScheduler` job structure while minimizing redundant calculations?
2.  **Refining the Filters:**
    *   Is the 20-day EMA the optimal choice for the daily trend filter, or should we consider a combination of moving averages (e.g., 10 and 20)?
    *   For our "Internal Breadth" model, is a 3-of-4 ETF agreement the right threshold, or should this be adjusted based on the VIX level? For example, in a high VIX environment, should we require a 4-of-4 agreement for a stronger signal?
3.  **Backtesting:** How can we structure a backtest for this new funnel-based logic using the historical `yfinance` data to validate its effectiveness against the old scoring model?

## 7. Conclusion

By shifting from an isolated, score-based system to a context-aware, sequential funnel, we can significantly enhance the quality and probability of our dip-buy signals. This revised "Market Context First" approach provides a robust framework for understanding market conditions using only the data available through our existing, free API, fundamentally reducing risk and improving the reliability of its alerts.
