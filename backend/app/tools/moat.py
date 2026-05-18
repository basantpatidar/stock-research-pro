import numpy as np
from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def get_moat_score(ticker: str) -> dict:
    """
    Economic moat proxy score using ROE consistency, gross margin trend,
    ROIC vs cost-of-capital, and revenue growth stability. 0–5 score.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        inc = stock.income_stmt
        components = {}
        score = 0

        # 1. ROE > 15% (trailing)
        roe = info.get("returnOnEquity")
        if roe is not None:
            roe_pass = roe >= 0.15
            components["roe"] = {
                "label": "ROE ≥15%",
                "value": f"{roe*100:.1f}%",
                "pass": roe_pass,
                "note": "Sustainable high ROE = pricing power or cost advantage",
            }
            if roe_pass:
                score += 1
        else:
            components["roe"] = {
                "label": "ROE ≥15%",
                "value": "N/A",
                "pass": None,
                "note": "Data unavailable",
            }

        # 2. Gross margin trend (expanding = moat strengthening)
        gm_pass = None
        gm_trend = "unknown"
        gm_current = None
        try:
            if (
                inc is not None
                and not inc.empty
                and "Gross Profit" in inc.index
                and "Total Revenue" in inc.index
            ):
                gp = inc.loc["Gross Profit"].dropna()
                rev = inc.loc["Total Revenue"].dropna()
                margins = (gp / rev).dropna()
                if len(margins) >= 2:
                    gm_current = float(margins.iloc[0])
                    gm_old = float(margins.iloc[-1])
                    gm_pass = gm_current >= 0.30 and gm_current >= gm_old * 0.95
                    gm_trend = "stable/expanding" if gm_current >= gm_old * 0.98 else "contracting"
        except Exception:
            pass
        components["gross_margin"] = {
            "label": "Gross Margin ≥30% (stable/expanding)",
            "value": f"{gm_current*100:.1f}%" if gm_current is not None else "N/A",
            "pass": gm_pass,
            "note": f"Trend: {gm_trend}",
        }
        if gm_pass:
            score += 1

        # 3. ROIC > WACC proxy (ROIC > 10%)
        roic = info.get("returnOnAssets")  # use ROA as ROIC proxy
        roic_pass = None
        if roic is not None:
            roic_pass = roic >= 0.10
            components["roic"] = {
                "label": "ROIC ≥10% (ROA proxy)",
                "value": f"{roic*100:.1f}%",
                "pass": roic_pass,
                "note": "Returns above cost-of-capital = capital allocator advantage",
            }
            if roic_pass:
                score += 1
        else:
            components["roic"] = {
                "label": "ROIC ≥10%",
                "value": "N/A",
                "pass": None,
                "note": "Data unavailable",
            }

        # 4. Revenue growth consistency (low CV of annual growth rates)
        rev_consistent = None
        try:
            if inc is not None and not inc.empty and "Total Revenue" in inc.index:
                revs = inc.loc["Total Revenue"].dropna().values[::-1]
                if len(revs) >= 3:
                    growth_rates = np.diff(revs) / np.abs(revs[:-1])
                    cv = np.std(growth_rates) / max(abs(np.mean(growth_rates)), 1e-6)
                    rev_consistent = cv < 1.0 and np.mean(growth_rates) > 0
                    components["revenue_consistency"] = {
                        "label": "Revenue Growth Consistent",
                        "value": f"CV={cv:.2f}, avg growth={np.mean(growth_rates)*100:.1f}%",
                        "pass": rev_consistent,
                        "note": "Low variance growth = durable competitive position",
                    }
                    if rev_consistent:
                        score += 1
        except Exception:
            pass
        if "revenue_consistency" not in components:
            components["revenue_consistency"] = {
                "label": "Revenue Growth Consistent",
                "value": "N/A",
                "pass": None,
                "note": "Insufficient data",
            }

        # 5. Profit margin > 10% (pricing power)
        margin = info.get("profitMargins")
        margin_pass = margin is not None and margin >= 0.10
        components["profit_margin"] = {
            "label": "Net Profit Margin ≥10%",
            "value": f"{margin*100:.1f}%" if margin else "N/A",
            "pass": margin_pass,
            "note": "High margin = pricing power or scale advantage",
        }
        if margin_pass:
            score += 1

        if score >= 4:
            moat_width = "WIDE"
            moat_color = "green"
            summary = "Strong, durable competitive advantage"
        elif score >= 2:
            moat_width = "NARROW"
            moat_color = "amber"
            summary = "Some competitive advantages — monitor for erosion"
        else:
            moat_width = "NONE"
            moat_color = "red"
            summary = "No clear moat identified — commodity-like business"

        return {
            "ticker": ticker.upper(),
            "moat_width": moat_width,
            "moat_color": moat_color,
            "score": score,
            "total": 5,
            "summary": summary,
            "components": components,
        }
    except Exception as e:
        return {"error": f"Moat score failed for {ticker}: {str(e)}"}
