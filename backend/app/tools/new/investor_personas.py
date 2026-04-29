from langchain_core.tools import tool
from app.tools._yf_client import get_ticker


@tool
def investor_personas(ticker: str) -> dict:
    """
    Analyze a stock from the perspective of 5 legendary investors:
    Warren Buffett (value/moat), Benjamin Graham (deep value/margin of safety),
    Michael Burry (contrarian/debt), Peter Lynch (growth at reasonable price),
    Cathie Wood (disruptive innovation).
    Returns fundamental data and per-persona analysis instructions.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")

        if hist.empty:
            return {"error": f"No data for {ticker}"}

        current = round(float(hist["Close"].iloc[-1]), 2)
        high_52 = round(float(hist["High"].max()), 2)
        low_52 = round(float(hist["Low"].min()), 2)
        drawdown_from_high = round((current - high_52) / high_52 * 100, 1)

        fundamentals = {
            "current_price": current,
            "52w_high": high_52,
            "52w_low": low_52,
            "drawdown_from_52w_high_pct": drawdown_from_high,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "profit_margin": info.get("profitMargins"),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "free_cashflow": info.get("freeCashflow"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "analyst_target": info.get("targetMeanPrice"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "business_summary": (info.get("longBusinessSummary") or "")[:500],
        }

        return {
            "ticker": ticker.upper(),
            "fundamentals": fundamentals,
            "personas": [
                {
                    "name": "Warren Buffett",
                    "style": "Quality at fair price — durable competitive moat, strong ROE, predictable earnings",
                    "key_metrics": ["roe", "profit_margin", "pe_ratio", "debt_to_equity", "free_cashflow"],
                    "verdict_instruction": (
                        f"As Warren Buffett, evaluate {ticker.upper()} on: "
                        f"(1) economic moat — does it have pricing power and durable competitive advantage? "
                        f"(2) management quality — is capital allocated wisely? "
                        f"(3) predictable earnings — is free cash flow consistent? "
                        f"(4) reasonable price — is P/E justified given quality? "
                        f"Give a BUY / HOLD / AVOID verdict with 2-sentence reasoning."
                    ),
                },
                {
                    "name": "Benjamin Graham",
                    "style": "Deep value — large margin of safety, low P/B, net-net assets, low debt",
                    "key_metrics": ["price_to_book", "pe_ratio", "current_ratio", "debt_to_equity"],
                    "verdict_instruction": (
                        f"As Benjamin Graham, evaluate {ticker.upper()} on: "
                        f"(1) margin of safety — is P/B below 1.5 and P/E below 15? "
                        f"(2) financial strength — is current ratio > 2 and debt/equity manageable? "
                        f"(3) earnings stability — sustained profits over multiple years? "
                        f"(4) dividend record — does it pay dividends consistently? "
                        f"Give a BUY / HOLD / AVOID verdict with 2-sentence reasoning."
                    ),
                },
                {
                    "name": "Michael Burry",
                    "style": "Contrarian — deeply undervalued, high debt risk, mean-reversion plays",
                    "key_metrics": ["price_to_book", "debt_to_equity", "drawdown_from_52w_high_pct", "ev_to_ebitda"],
                    "verdict_instruction": (
                        f"As Michael Burry, evaluate {ticker.upper()} on: "
                        f"(1) mispricing — is the market ignoring real asset value? "
                        f"(2) debt risk — is the balance sheet hiding insolvency risk? "
                        f"(3) contrarian case — is negative sentiment overdone? "
                        f"(4) catalyst — what forces mean-reversion? "
                        f"Give a BUY / SHORT / AVOID verdict with 2-sentence reasoning."
                    ),
                },
                {
                    "name": "Peter Lynch",
                    "style": "Growth at reasonable price — PEG < 1, understandable business, local insight",
                    "key_metrics": ["peg_ratio", "revenue_growth", "earnings_growth", "pe_ratio"],
                    "verdict_instruction": (
                        f"As Peter Lynch, evaluate {ticker.upper()} on: "
                        f"(1) PEG ratio — is growth being paid for at a fair price (PEG < 1 ideal)? "
                        f"(2) understandability — is the business simple enough to explain in one sentence? "
                        f"(3) growth runway — how many more years can it grow at this rate? "
                        f"(4) institutional ownership — is it underfollowed (hidden gem)? "
                        f"Classify as: Fast Grower, Stalwart, Turnaround, Asset Play, or Slow Grower. "
                        f"Give a BUY / HOLD / AVOID verdict with 2-sentence reasoning."
                    ),
                },
                {
                    "name": "Cathie Wood",
                    "style": "Disruptive innovation — TAM expansion, exponential growth, 5-year horizon",
                    "key_metrics": ["revenue_growth", "price_to_sales", "beta", "sector"],
                    "verdict_instruction": (
                        f"As Cathie Wood, evaluate {ticker.upper()} on: "
                        f"(1) disruption potential — is this company enabling or leading a platform shift? "
                        f"(2) TAM expansion — could the addressable market 10x in 5 years? "
                        f"(3) innovation pipeline — does it invest heavily in R&D? "
                        f"(4) convergence — does it sit at the intersection of multiple technologies? "
                        f"Give a STRONG BUY / BUY / AVOID verdict with 2-sentence reasoning."
                    ),
                },
            ],
        }
    except Exception as e:
        return {"error": f"Failed to run investor personas for {ticker}: {str(e)}"}
