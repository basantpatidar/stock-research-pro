from langchain_core.tools import tool
from app.tools._yf_client import get_ticker
import numpy as np
import pandas as pd


@tool
def get_dividend_health(ticker: str) -> dict:
    """
    Dividend health scorecard: payout ratio, growth CAGR, consecutive growth years, FCF coverage.
    Only meaningful for dividend-paying stocks.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        div_yield = info.get("dividendYield") or 0
        div_rate = info.get("dividendRate") or 0
        if not div_yield and not div_rate:
            return {
                "ticker": ticker.upper(),
                "pays_dividend": False,
                "verdict": "NO DIVIDEND",
                "verdict_color": "neutral",
                "detail": "This stock does not currently pay a dividend",
            }

        # Payout ratio
        payout_ratio = info.get("payoutRatio")
        eps = info.get("trailingEps") or 1

        # Dividend history for CAGR
        divs = stock.dividends
        div_cagr_3y = None
        div_cagr_5y = None
        consecutive_growth = 0

        if divs is not None and not divs.empty:
            # Annual dividend totals
            annual = divs.resample("YE").sum()
            annual = annual[annual > 0].dropna()

            if len(annual) >= 2:
                # 3yr CAGR
                if len(annual) >= 4:
                    newest = float(annual.iloc[-1])
                    three_ago = float(annual.iloc[-4])
                    div_cagr_3y = round((newest / three_ago) ** (1/3) - 1, 4) if three_ago > 0 else None

                # 5yr CAGR
                if len(annual) >= 6:
                    five_ago = float(annual.iloc[-6])
                    div_cagr_5y = round((newest / five_ago) ** (1/5) - 1, 4) if five_ago > 0 else None

                # Consecutive growth years
                vals = annual.values.tolist()
                for i in range(len(vals)-1, 0, -1):
                    if vals[i] > vals[i-1]:
                        consecutive_growth += 1
                    else:
                        break

        # FCF coverage
        fcf_coverage = None
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                ocf = cf.loc["Operating Cash Flow"].iloc[0] if "Operating Cash Flow" in cf.index else 0
                capex = cf.loc["Capital Expenditure"].iloc[0] if "Capital Expenditure" in cf.index else 0
                fcf = float(ocf or 0) + float(capex or 0)
                shares = info.get("sharesOutstanding") or 1
                total_divs_paid = float(div_rate or 0) * shares
                if total_divs_paid > 0:
                    fcf_coverage = round(fcf / total_divs_paid, 2)
        except Exception:
            pass

        # Verdict
        safe_checks = [
            payout_ratio is not None and payout_ratio < 0.60,
            fcf_coverage is not None and fcf_coverage > 2.0,
            div_cagr_3y is not None and div_cagr_3y > 0,
            consecutive_growth >= 3,
        ]
        safe_count = sum(safe_checks)

        if safe_count >= 3:
            verdict = "SAFE"
            verdict_color = "green"
        elif safe_count >= 2:
            verdict = "WATCH"
            verdict_color = "amber"
        else:
            verdict = "DANGER"
            verdict_color = "red"

        return {
            "ticker": ticker.upper(),
            "pays_dividend": True,
            "dividend_yield_pct": round(div_yield * 100, 2) if div_yield else None,
            "dividend_rate": round(div_rate, 2) if div_rate else None,
            "payout_ratio_pct": round(payout_ratio * 100, 1) if payout_ratio else None,
            "fcf_coverage": fcf_coverage,
            "div_cagr_3y_pct": round(div_cagr_3y * 100, 1) if div_cagr_3y else None,
            "div_cagr_5y_pct": round(div_cagr_5y * 100, 1) if div_cagr_5y else None,
            "consecutive_growth_years": consecutive_growth,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "checks": {
                "payout_safe": safe_checks[0],
                "fcf_covers_dividend": safe_checks[1],
                "dividend_growing": safe_checks[2],
                "streak_3_plus_years": safe_checks[3],
            },
        }
    except Exception as e:
        return {"error": f"Dividend health failed for {ticker}: {str(e)}"}
