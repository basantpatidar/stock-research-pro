"""
Earnings Quality tool — Sprint 1.

Computes four institutional-grade models that reveal whether reported earnings
are real, the company is financially healthy, and bankruptcy risk is elevated.

Models:
  Piotroski F-Score  — financial strength (0–9)
  Beneish M-Score    — earnings manipulation probability
  Altman Z-Score     — bankruptcy proximity
  Accruals Ratio     — cash vs paper earnings quality (Sloan)

Every metric returns a full SignalResult with a direct verdict (BUY / HOLD /
SELL / AVOID / RISK_FLAG) so the user never has to interpret raw numbers.
"""

from langchain_core.tools import tool

from app.tools._yf_client import get_ticker
from app.tools.signal import build_signal, composite_verdict

# ── Piotroski F-Score ─────────────────────────────────────────────────────────


def _piotroski(info: dict, fin: dict, bs: dict, cf: dict) -> dict:
    """
    9-point financial strength checklist.
    4 profitability + 3 leverage/liquidity + 2 efficiency checks.
    Returns score, per-check breakdown, and a SignalResult.
    """
    checks = {}

    # ── Profitability (4 checks) ──
    roa = info.get("returnOnAssets")
    checks["positive_roa"] = bool(roa and roa > 0)

    cfo = (
        cf.get("Operating Cash Flow", [None])[0]
        if cf.get("Operating Cash Flow") is not None
        else None
    )
    checks["positive_cfo"] = bool(cfo and cfo > 0)

    # ROA trend: current vs prior year
    roa_curr = info.get("returnOnAssets")
    # Approximate prior-year ROA from income / asset trend
    net_inc = fin.get("Net Income", [None, None])
    ta_vals = bs.get("Total Assets", [None, None])
    try:
        roa_prior = float(net_inc[1]) / float(ta_vals[1]) if net_inc[1] and ta_vals[1] else None
        checks["improving_roa"] = bool(roa_curr and roa_prior and roa_curr > roa_prior)
    except (TypeError, ZeroDivisionError):
        checks["improving_roa"] = False

    # Accrual check: CFO > Net Income (cash earnings beat accrual earnings)
    try:
        ni_curr = float(net_inc[0]) if net_inc[0] else None
        cfo_curr = float(cfo) if cfo else None
        checks["cfo_gt_net_income"] = bool(cfo_curr and ni_curr and cfo_curr > ni_curr)
    except TypeError:
        checks["cfo_gt_net_income"] = False

    # ── Leverage / Liquidity (3 checks) ──
    debt = bs.get("Long Term Debt", [None, None])
    try:
        lt_debt_curr = float(debt[0]) if debt[0] else 0
        lt_debt_prior = float(debt[1]) if len(debt) > 1 and debt[1] else 0
        ta_curr = float(ta_vals[0]) if ta_vals[0] else 1
        ta_prior = float(ta_vals[1]) if ta_vals[1] else 1
        lev_curr = lt_debt_curr / ta_curr
        lev_prior = lt_debt_prior / ta_prior
        checks["declining_leverage"] = lev_curr < lev_prior
    except (TypeError, ZeroDivisionError):
        checks["declining_leverage"] = False

    curr_ratio = info.get("currentRatio")
    checks["improving_liquidity"] = bool(curr_ratio and curr_ratio > 1.0)

    shares = bs.get("Ordinary Shares Number", [None, None])
    try:
        sh_curr = float(shares[0]) if shares[0] else None
        sh_prior = float(shares[1]) if len(shares) > 1 and shares[1] else None
        checks["no_dilution"] = bool(sh_curr and sh_prior and sh_curr <= sh_prior * 1.01)
    except TypeError:
        checks["no_dilution"] = False

    # ── Operating Efficiency (2 checks) ──
    gm = fin.get("Gross Profit", [None, None])
    rev = fin.get("Total Revenue", [None, None])
    try:
        gm_curr = float(gm[0]) / float(rev[0]) if gm[0] and rev[0] else None
        gm_prior = float(gm[1]) / float(rev[1]) if len(gm) > 1 and gm[1] and rev[1] else None
        checks["improving_gross_margin"] = bool(gm_curr and gm_prior and gm_curr > gm_prior)
    except (TypeError, ZeroDivisionError):
        checks["improving_gross_margin"] = False

    try:
        at_curr = float(rev[0]) / float(ta_vals[0]) if rev[0] and ta_vals[0] else None
        at_prior = (
            float(rev[1]) / float(ta_vals[1]) if len(rev) > 1 and rev[1] and ta_vals[1] else None
        )
        checks["improving_asset_turnover"] = bool(at_curr and at_prior and at_curr > at_prior)
    except (TypeError, ZeroDivisionError):
        checks["improving_asset_turnover"] = False

    score = sum(1 for v in checks.values() if v)

    # Verdict
    if score >= 8:
        verdict, conviction, contribution = "BUY", "HIGH", 1.5
        headline = f"Financially strong — {score}/9 health checks passed"
        why = (
            "Company shows improving profitability, declining debt load, and rising "
            "efficiency. F-Score ≥ 8 has historically preceded 12-month outperformance."
        )
        action = "Supports entering or adding to a long-term position."
        key_risk = "Score reflects trailing data — watch next earnings for deterioration."
    elif score >= 6:
        verdict, conviction, contribution = "BUY", "MODERATE", 0.8
        headline = f"Solid financial health — {score}/9 checks passed"
        why = "More positive signals than negative. Company is in reasonable financial shape."
        action = "Acceptable to hold or build gradually. Not a red flag."
        key_risk = "A few checks are failing — monitor for trend."
    elif score >= 4:
        verdict, conviction, contribution = "HOLD", "MODERATE", 0.0
        headline = f"Mixed financial signals — {score}/9 checks passed"
        why = "Roughly equal positive and negative signals. No clear directional edge."
        action = "Hold existing position. Avoid large new entry until signals improve."
        key_risk = "Borderline score — one bad quarter could push into sell territory."
    elif score >= 2:
        verdict, conviction, contribution = "SELL", "MODERATE", -1.0
        headline = f"Financial weakness detected — only {score}/9 checks passed"
        why = "Company is failing on profitability, leverage, or efficiency measures."
        action = "Consider reducing position. Do not add at current levels."
        key_risk = "Weakness may worsen before it improves."
    else:
        verdict, conviction, contribution = "AVOID", "HIGH", -2.0
        headline = f"Severe financial deterioration — {score}/9 checks passed"
        why = (
            "Company is failing nearly all financial health checks. Strong historical short signal."
        )
        action = "Do not enter. Exit existing positions."
        key_risk = "Score this low often precedes earnings disappointments or credit events."

    check_labels = {
        "positive_roa": "Return on assets is positive",
        "positive_cfo": "Operating cash flow is positive",
        "improving_roa": "ROA improving year-over-year",
        "cfo_gt_net_income": "Cash earnings exceed accrual earnings",
        "declining_leverage": "Long-term debt ratio declining",
        "improving_liquidity": "Current ratio above 1.0",
        "no_dilution": "No share dilution vs prior year",
        "improving_gross_margin": "Gross margin improving",
        "improving_asset_turnover": "Asset turnover improving",
    }

    return {
        "score": score,
        "max_score": 9,
        "checks": {k: {"passed": v, "label": check_labels[k]} for k, v in checks.items()},
        "signal": build_signal(
            value=f"{score}/9",
            verdict=verdict,
            conviction=conviction,
            headline=headline,
            why=why,
            action=action,
            key_risk=key_risk,
            score_contribution=contribution,
        ),
    }


# ── Beneish M-Score ───────────────────────────────────────────────────────────


def _beneish(fin: dict, bs: dict, cf: dict) -> dict:
    """
    8-variable model for earnings manipulation probability.
    Score > -2.22 = probable manipulator.
    """
    try:
        rev = fin.get("Total Revenue", [None, None])
        ni = fin.get("Net Income", [None, None])
        gp = fin.get("Gross Profit", [None, None])
        ta = bs.get("Total Assets", [None, None])
        rec = bs.get("Accounts Receivable", [None, None])
        ppe = bs.get("Net PPE", [None, None])
        dep = cf.get("Depreciation And Amortization", [None, None])
        sga = fin.get("Selling General Administrative", [None, None])
        ltd = bs.get("Long Term Debt", [None, None])
        ca = bs.get("Current Assets", [None, None])
        cl = bs.get("Current Liabilities", [None, None])
        cfo = cf.get("Operating Cash Flow", [None, None])

        def f(x, i=0):
            try:
                return float(x[i]) if x and x[i] is not None else None
            except (TypeError, IndexError):
                return None

        r0, r1 = f(rev, 0), f(rev, 1)
        ni0 = f(ni, 0)
        gp0, gp1 = f(gp, 0), f(gp, 1)
        ta0, ta1 = f(ta, 0), f(ta, 1)
        rec0, rec1 = f(rec, 0), f(rec, 1)
        ppe0, ppe1 = f(ppe, 0), f(ppe, 1)
        dep0, dep1 = f(dep, 0), f(dep, 1)
        sga0, sga1 = f(sga, 0), f(sga, 1)
        ltd0 = f(ltd, 0)
        ca0, ca1 = f(ca, 0), f(ca, 1)
        cl0, cl1 = f(cl, 0), f(cl, 1)
        cfo0 = f(cfo, 0)

        components = {}

        # DSRI: Days Sales Receivables Index
        if all(v for v in [rec0, r0, rec1, r1]):
            dsri = (rec0 / r0) / (rec1 / r1)
            components["dsri"] = round(dsri, 3)

        # GMI: Gross Margin Index
        if all(v for v in [gp1, r1, gp0, r0]):
            gmi = ((gp1 / r1)) / ((gp0 / r0))
            components["gmi"] = round(gmi, 3)

        # AQI: Asset Quality Index
        if all(v for v in [ta0, ppe0, ca0, ta1, ppe1, ca1]):
            aqi = (1 - (ca0 + ppe0) / ta0) / (1 - (ca1 + ppe1) / ta1)
            components["aqi"] = round(aqi, 3)

        # SGI: Sales Growth Index
        if all(v for v in [r0, r1]):
            sgi = r0 / r1
            components["sgi"] = round(sgi, 3)

        # DEPI: Depreciation Index
        if all(v for v in [dep0, ppe0, dep1, ppe1]):
            depi = (dep1 / (dep1 + ppe1)) / (dep0 / (dep0 + ppe0))
            components["depi"] = round(depi, 3)

        # SGAI: SG&A Index
        if all(v for v in [sga0, r0, sga1, r1]):
            sgai = (sga0 / r0) / (sga1 / r1)
            components["sgai"] = round(sgai, 3)

        # TATA: Total Accruals to Total Assets
        if all(v for v in [ni0, cfo0, ta0]):
            tata = (ni0 - cfo0) / ta0
            components["tata"] = round(tata, 4)

        # LVGI: Leverage Index
        if all(v for v in [ltd0, cl0, ta0, ca0, cl1, ta1, ca1]):
            lvgi = ((ltd0 + cl0) / ta0) / ((f(ltd, 1) or 0 + cl1) / ta1)
            components["lvgi"] = round(lvgi, 3)

        if len(components) < 4:
            return {
                "score": None,
                "components": components,
                "signal": build_signal(
                    value=None,
                    verdict="HOLD",
                    conviction="LOW",
                    headline="Insufficient data to compute M-Score",
                    why="Not enough historical financial statement data available.",
                    action="Cannot assess earnings quality — use other signals.",
                    key_risk="Missing data may itself be a yellow flag.",
                    score_contribution=0.0,
                ),
            }

        # Beneish formula weights
        score = (
            -4.84
            + 0.920 * components.get("dsri", 1.0)
            + 0.528 * components.get("gmi", 1.0)
            + 0.404 * components.get("aqi", 1.0)
            + 0.892 * components.get("sgi", 1.0)
            + 0.115 * components.get("depi", 1.0)
            - 0.172 * components.get("sgai", 1.0)
            + 4.679 * components.get("tata", 0.0)
            - 0.327 * components.get("lvgi", 1.0)
        )
        score = round(score, 3)

        if score > -1.78:
            verdict, conviction, contribution = "RISK_FLAG", "HIGH", -2.0
            headline = "Earnings manipulation likely — do not trust reported EPS"
            why = (
                "M-Score above -1.78 matches companies that have historically "
                "restated earnings or committed accounting fraud. Treat all "
                "reported numbers with significant skepticism."
            )
            action = "Do not enter. If holding, reduce position immediately and investigate."
            key_risk = "This is a probabilistic model — not every high score is fraud, but the odds are not in your favour."
        elif score > -2.22:
            verdict, conviction, contribution = "SELL", "MODERATE", -1.0
            headline = "Elevated manipulation risk — earnings quality suspect"
            why = (
                "Score in the grey zone. Some financial ratios are moving in patterns "
                "associated with earnings management. Not definitive, but warrants caution."
            )
            action = "Avoid adding to position. Wait for cleaner quarter before acting."
            key_risk = "Could be legitimate accounting changes rather than manipulation."
        else:
            verdict, conviction, contribution = "BUY", "HIGH", 1.0
            headline = "No manipulation signals detected — earnings appear genuine"
            why = (
                "Financial ratios are in ranges consistent with clean reporting. "
                "Reported EPS is likely backed by real economic activity."
            )
            action = "Earnings quality supports the investment thesis."
            key_risk = "M-Score catches past patterns — new manipulation would not yet be visible."

        return {
            "score": score,
            "threshold_manipulator": -2.22,
            "threshold_likely_manipulator": -1.78,
            "components": components,
            "signal": build_signal(
                value=score,
                verdict=verdict,
                conviction=conviction,
                headline=headline,
                why=why,
                action=action,
                key_risk=key_risk,
                score_contribution=contribution,
            ),
        }

    except Exception as e:
        return {
            "score": None,
            "error": str(e),
            "signal": build_signal(
                value=None,
                verdict="HOLD",
                conviction="LOW",
                headline="Could not compute Beneish M-Score",
                why="Calculation failed due to missing or inconsistent financial data.",
                action="Use other quality signals until data is available.",
                key_risk="Missing data.",
                score_contribution=0.0,
            ),
        }


# ── Altman Z-Score ────────────────────────────────────────────────────────────


def _altman(info: dict, fin: dict, bs: dict, cf: dict) -> dict:
    """
    5-factor bankruptcy prediction model.
    < 1.81 = distress zone, 1.81–2.99 = grey zone, > 2.99 = safe.
    Uses the public-company (original) formula.
    """
    try:
        ta = bs.get("Total Assets", [None])[0]
        cl = bs.get("Current Liabilities", [None])[0]
        ca = bs.get("Current Assets", [None])[0]
        re = bs.get("Retained Earnings", [None])[0]
        ebit_val = fin.get("EBIT", [None])[0] or fin.get("Operating Income", [None])[0]
        rev = fin.get("Total Revenue", [None])[0]
        market_cap = info.get("marketCap")
        ltd = bs.get("Long Term Debt", [None])[0]
        cl_val = float(cl) if cl else 0
        book_debt = (float(ltd) if ltd else 0) + cl_val

        if not all([ta, rev, market_cap]):
            raise ValueError("Core inputs missing")

        ta_f = float(ta)
        x1 = (float(ca) - float(cl)) / ta_f if ca and cl else 0  # working capital / TA
        x2 = float(re) / ta_f if re else 0  # retained earnings / TA
        x3 = float(ebit_val) / ta_f if ebit_val else 0  # EBIT / TA
        x4 = float(market_cap) / book_debt if book_debt > 0 else 5  # mkt equity / book debt
        x5 = float(rev) / ta_f  # sales / TA

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        z = round(z, 2)

        components = {
            "working_capital_ratio": round(x1, 3),
            "retained_earnings_ratio": round(x2, 3),
            "ebit_ratio": round(x3, 3),
            "market_to_book_debt": round(x4, 3),
            "asset_turnover": round(x5, 3),
        }

        if z > 2.99:
            zone = "SAFE"
            verdict, conviction, contribution = "BUY", "HIGH", 1.0
            headline = f"Financially sound — Z-Score {z} is in the safe zone"
            why = (
                "Company is well above bankruptcy risk thresholds. Strong working "
                "capital, earnings power, and equity cushion relative to debt."
            )
            action = "No financial distress risk. Safe to invest."
            key_risk = (
                "Z-Score uses trailing data — a sudden credit event could change this quickly."
            )
        elif z > 1.81:
            zone = "GREY"
            verdict, conviction, contribution = "HOLD", "MODERATE", -0.3
            headline = f"Grey zone — Z-Score {z} warrants monitoring"
            why = (
                "Company is between safe and distress thresholds. Not in immediate danger "
                "but financial flexibility is limited. Watch debt levels and cash flow."
            )
            action = "Hold but do not add until score moves clearly above 2.99."
            key_risk = "Grey zone companies can deteriorate quickly in a downturn."
        else:
            zone = "DISTRESS"
            verdict, conviction, contribution = "AVOID", "HIGH", -2.0
            headline = f"Distress zone — Z-Score {z} signals elevated bankruptcy risk"
            why = (
                "Score below 1.81 has historically predicted corporate distress. "
                "Company has insufficient earnings power or equity buffer to cover obligations."
            )
            action = "Do not enter. Exit existing positions. Serious credit risk."
            key_risk = (
                "Not every low Z-Score ends in bankruptcy, but the odds strongly favor avoiding."
            )

        return {
            "score": z,
            "zone": zone,
            "thresholds": {"distress": 1.81, "grey_zone": 2.99},
            "components": components,
            "signal": build_signal(
                value=z,
                verdict=verdict,
                conviction=conviction,
                headline=headline,
                why=why,
                action=action,
                key_risk=key_risk,
                score_contribution=contribution,
            ),
        }

    except Exception as e:
        return {
            "score": None,
            "zone": "UNKNOWN",
            "error": str(e),
            "signal": build_signal(
                value=None,
                verdict="HOLD",
                conviction="LOW",
                headline="Could not compute Altman Z-Score",
                why="Missing financial data required for the calculation.",
                action="Use other signals to assess financial health.",
                key_risk="Missing data.",
                score_contribution=0.0,
            ),
        }


# ── Accruals Ratio (Sloan) ────────────────────────────────────────────────────


def _accruals(fin: dict, bs: dict, cf: dict) -> dict:
    """
    Sloan accrual anomaly: (Net Income - CFO - CFI) / Avg Total Assets.
    High accruals = paper earnings not backed by cash. > 5% = red flag.
    """
    try:
        ni = fin.get("Net Income", [None])[0]
        cfo = cf.get("Operating Cash Flow", [None])[0]
        cfi = cf.get("Investing Cash Flow", [None])[0]
        ta_curr = bs.get("Total Assets", [None, None])[0]
        ta_prior = bs.get("Total Assets", [None, None])[1]

        if not all([ni, cfo, ta_curr]):
            raise ValueError("Core inputs missing")

        ni_f = float(ni)
        cfo_f = float(cfo)
        cfi_f = float(cfi) if cfi else 0
        ta_f = float(ta_curr)
        ta_avg = (ta_f + float(ta_prior)) / 2 if ta_prior else ta_f

        accruals = ni_f - cfo_f - cfi_f
        ratio = (accruals / ta_avg) * 100
        ratio = round(ratio, 2)

        cash_pct = round((cfo_f / ni_f) * 100, 1) if ni_f != 0 else None

        if ratio < -5:
            verdict, conviction, contribution = "BUY", "HIGH", 1.5
            headline = "Exceptional earnings quality — cash far exceeds reported income"
            why = (
                "Operating cash flow significantly exceeds net income. This is the "
                "gold standard of earnings quality — the company is converting profits "
                "to cash even faster than it books them."
            )
            action = "High-quality earnings strongly support the long-term investment case."
            key_risk = "Highly negative accruals can occasionally reflect aggressive depreciation policies."
            direction = "IMPROVING"
        elif ratio < 0:
            verdict, conviction, contribution = "BUY", "MODERATE", 0.8
            headline = "Cash-backed earnings — accruals ratio is clean"
            why = (
                "Cash flow exceeds net income. Reported earnings are backed by real "
                "cash generation — not accounting adjustments."
            )
            action = "Earnings quality supports the thesis. Safe to trust reported numbers."
            key_risk = "Small accrual buffer — monitor for reversal."
            direction = "STABLE"
        elif ratio < 5:
            verdict, conviction, contribution = "HOLD", "MODERATE", 0.0
            headline = "Borderline earnings quality — modest accrual build"
            why = (
                "A small portion of earnings is accrual-based rather than cash-backed. "
                "Not alarming, but watch for the ratio rising further."
            )
            action = "Acceptable. Hold position but monitor accruals trend."
            key_risk = "Rising accruals over multiple quarters is an early warning sign."
            direction = "STABLE"
        elif ratio < 10:
            verdict, conviction, contribution = "SELL", "MODERATE", -1.0
            headline = "Elevated accruals — earnings quality deteriorating"
            why = (
                "A meaningful portion of reported net income is accounting-based, not "
                "cash-backed. Companies with high accruals systematically underperform "
                "over the following 12 months (Sloan, 1996)."
            )
            action = "Reduce position. Do not add. Reported EPS is likely overstated vs economic reality."
            key_risk = "May reflect timing differences rather than outright manipulation."
            direction = "DETERIORATING"
        else:
            verdict, conviction, contribution = "RISK_FLAG", "HIGH", -2.0
            headline = "Severe earnings quality problem — most income is paper, not cash"
            why = (
                "Accruals ratio above 10% is a serious red flag. Most of the reported "
                "net income is accounting adjustments, not real cash generation. "
                "This pattern precedes earnings restatements and price collapses."
            )
            action = (
                "Do not enter. Exit existing position and investigate balance sheet aggressively."
            )
            key_risk = "High accruals can persist for several quarters before unwinding — usually painfully."
            direction = "DETERIORATING"

        return {
            "accruals_ratio_pct": ratio,
            "net_income": ni_f,
            "operating_cash_flow": cfo_f,
            "investing_cash_flow": cfi_f,
            "cash_earnings_pct_of_net_income": cash_pct,
            "interpretation": "negative = cash exceeds income (good) | positive = income exceeds cash (risk)",
            "signal": build_signal(
                value=f"{ratio}%",
                verdict=verdict,
                conviction=conviction,
                headline=headline,
                why=why,
                action=action,
                key_risk=key_risk,
                direction=direction,
                score_contribution=contribution,
            ),
        }

    except Exception as e:
        return {
            "accruals_ratio_pct": None,
            "error": str(e),
            "signal": build_signal(
                value=None,
                verdict="HOLD",
                conviction="LOW",
                headline="Could not compute Accruals Ratio",
                why="Missing cash flow or balance sheet data.",
                action="Use other quality signals.",
                key_risk="Missing data.",
                score_contribution=0.0,
            ),
        }


# ── Main tool ─────────────────────────────────────────────────────────────────


@tool
def get_earnings_quality(ticker: str) -> dict:
    """
    Compute four institutional earnings quality models for a stock:
    Piotroski F-Score, Beneish M-Score, Altman Z-Score, and Accruals Ratio.

    Each model returns a direct verdict (STRONG_BUY / BUY / HOLD / SELL /
    AVOID / RISK_FLAG) with plain-English explanation and action guidance.
    A composite verdict aggregates all four into a single earnings quality call.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        # Pull two years of annual financials for YoY comparisons
        fin = (
            stock.financials.to_dict("list")
            if stock.financials is not None and not stock.financials.empty
            else {}
        )
        bs = (
            stock.balance_sheet.to_dict("list")
            if stock.balance_sheet is not None and not stock.balance_sheet.empty
            else {}
        )
        cf = (
            stock.cashflow.to_dict("list")
            if stock.cashflow is not None and not stock.cashflow.empty
            else {}
        )

        piotroski = _piotroski(info, fin, bs, cf)
        beneish = _beneish(fin, bs, cf)
        altman = _altman(info, fin, bs, cf)
        accruals = _accruals(fin, bs, cf)

        signals = [
            piotroski.get("signal"),
            beneish.get("signal"),
            altman.get("signal"),
            accruals.get("signal"),
        ]
        overall = composite_verdict([s for s in signals if s])

        return {
            "ticker": ticker.upper(),
            "overall": overall,
            "piotroski": piotroski,
            "beneish": beneish,
            "altman": altman,
            "accruals": accruals,
        }

    except Exception as e:
        return {"error": f"Failed to compute earnings quality for {ticker}: {str(e)}"}
