import numpy as np
from langchain_core.tools import tool

from app.tools._yf_client import get_ticker


@tool
def get_canslim_score(ticker: str) -> dict:
    """
    William O'Neil's CANSLIM composite framework.
    Scores 7 criteria and returns an overall verdict with per-criterion detail.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        spy = __import__("yfinance").Ticker("SPY").history(period="1y")

        if hist.empty:
            return {"error": f"No price data for {ticker}"}

        closes = hist["Close"].dropna()
        current_price = float(closes.iloc[-1])

        criteria = {}

        # C — Current quarterly EPS growth > 25%
        c_pass = None
        c_detail = "No earnings data"
        try:
            qe = stock.quarterly_earnings
            if qe is not None and not qe.empty and len(qe) >= 2:
                last_q = float(qe.iloc[0].get("Earnings") or 0)
                prior_yr_q = float(
                    qe.iloc[4].get("Earnings") if len(qe) > 4 else qe.iloc[1].get("Earnings") or 0
                )
                if prior_yr_q != 0:
                    growth = (last_q - prior_yr_q) / abs(prior_yr_q) * 100
                    c_pass = growth >= 25
                    c_detail = f"Latest quarter EPS growth: {growth:.0f}% (need ≥25%)"
        except Exception:
            pass
        criteria["C_quarterly_earnings"] = {
            "pass": c_pass,
            "detail": c_detail,
            "label": "Current Q EPS Growth ≥25%",
        }

        # A — Annual EPS growth > 20% for last 3 years
        a_pass = None
        a_detail = "No multi-year earnings data"
        try:
            ae = stock.earnings
            if ae is not None and not ae.empty and len(ae) >= 3:
                eps_vals = [float(ae.iloc[i].get("Earnings") or 0) for i in range(min(4, len(ae)))]
                eps_vals = [e for e in eps_vals if e != 0]
                if len(eps_vals) >= 2:
                    growth_rates = [
                        (eps_vals[i] - eps_vals[i + 1]) / abs(eps_vals[i + 1]) * 100
                        for i in range(len(eps_vals) - 1)
                        if eps_vals[i + 1] != 0
                    ]
                    avg_growth = np.mean(growth_rates) if growth_rates else 0
                    a_pass = avg_growth >= 20
                    a_detail = f"Annual EPS CAGR: {avg_growth:.0f}% (need ≥20%)"
        except Exception:
            pass
        criteria["A_annual_earnings"] = {
            "pass": a_pass,
            "detail": a_detail,
            "label": "Annual EPS Growth ≥20% (3yr)",
        }

        # N — New 52-week high (price within 5% of high = near new high)
        high_52w = float(closes.rolling(252, min_periods=50).max().iloc[-1])
        pct_from_high = (high_52w - current_price) / high_52w * 100
        n_pass = pct_from_high <= 15
        criteria["N_new_high"] = {
            "pass": n_pass,
            "detail": f"{pct_from_high:.1f}% from 52-week high (need ≤15%)",
            "label": "Near New 52-Week High",
        }

        # S — Supply: float < 25M = small/emerging, < 100M = mid, > 500M = less favorable
        float_shares = info.get("floatShares") or info.get("sharesOutstanding") or 0
        float_m = float_shares / 1e6
        s_pass = float_m < 500
        s_detail = f"Float: {float_m:.0f}M shares ({'favorable' if float_m < 100 else 'large'})"
        criteria["S_supply"] = {"pass": s_pass, "detail": s_detail, "label": "Float < 500M shares"}

        # L — Leader: RS Rating > 70 (from technicals if available)
        l_pass = None
        l_detail = "RS Rating not available"
        try:
            if not spy.empty and len(closes) >= 52:
                spy_ret = float(spy["Close"].pct_change(252).dropna().iloc[-1])
                stk_ret = float(closes.pct_change(252).dropna().iloc[-1])
                # Simple RS proxy on 0-99 scale
                rs_proxy = min(99, max(0, int(50 + (stk_ret - spy_ret) * 100)))
                l_pass = rs_proxy >= 70
                l_detail = f"RS Rating proxy: {rs_proxy}/99 (need ≥70)"
        except Exception:
            pass
        criteria["L_leader"] = {"pass": l_pass, "detail": l_detail, "label": "RS Rating ≥70"}

        # I — Institutional: increasing sponsorship
        i_pass = None
        i_detail = "No institutional data"
        try:
            inst = stock.institutional_holders
            if inst is not None and not inst.empty:
                total_pct = float(inst["pctHeld"].sum()) if "pctHeld" in inst.columns else 0
                i_pass = total_pct > 0.20  # >20% institutional ownership
                i_detail = f"Institutional ownership: {total_pct*100:.0f}% (need >20%)"
        except Exception:
            pass
        criteria["I_institutional"] = {
            "pass": i_pass,
            "detail": i_detail,
            "label": "Institutional Ownership >20%",
        }

        # M — Market direction: S&P trending up and VIX < 25
        m_pass = None
        m_detail = "No market data"
        try:
            import yfinance as yf

            vix = yf.Ticker("^VIX").history(period="5d")
            vix_val = float(vix["Close"].iloc[-1]) if not vix.empty else 25
            spy_trend = float(spy["Close"].pct_change(20).iloc[-1]) if not spy.empty else 0
            m_pass = vix_val < 25 and spy_trend > 0
            m_detail = f"VIX {vix_val:.0f} ({'ok' if vix_val < 25 else 'elevated'}), S&P 20d: {spy_trend*100:.1f}%"
        except Exception:
            pass
        criteria["M_market"] = {
            "pass": m_pass,
            "detail": m_detail,
            "label": "Market Direction Bullish",
        }

        passed = sum(1 for c in criteria.values() if c["pass"] is True)
        total = 7

        if passed >= 6:
            verdict = "STRONG SETUP"
            verdict_color = "green"
        elif passed >= 4:
            verdict = "MODERATE SETUP"
            verdict_color = "amber"
        else:
            verdict = "DOES NOT QUALIFY"
            verdict_color = "red"

        return {
            "ticker": ticker.upper(),
            "score": passed,
            "total": total,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "criteria": criteria,
        }
    except Exception as e:
        return {"error": f"CANSLIM scoring failed for {ticker}: {str(e)}"}
