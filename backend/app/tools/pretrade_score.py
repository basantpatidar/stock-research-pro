"""
Pre-Trade Checklist Scorecard — Sprint 6.
Pure aggregation of already-fetched T1 data. Zero new API calls.
"""


def _chk(label: str, passed: bool | None, value: str, tip: str = "") -> dict:
    return {"label": label, "pass": passed, "value": value, "tip": tip}


def compute_pretrade_score(
    price: dict,
    technicals: dict,
    short_interest: dict,
    news: dict,
    sectors: dict,
) -> dict:
    """
    Score 10 day-trading pre-conditions from T1 data.
    Returns {score, total:10, verdict, verdict_color, checks[]}.
    """
    checks: list[dict] = []
    curr = price.get("current_price")
    mas  = technicals.get("moving_averages") or {}

    # 1. Above 50d MA — short-term trend
    ma50 = mas.get("ma_50d")
    if ma50 and curr:
        checks.append(_chk("Above 50d MA", curr > ma50, f"${curr:.2f} vs ${ma50:.2f}"))
    else:
        checks.append(_chk("Above 50d MA", None, "N/A"))

    # 2. Above 200d MA — long-term trend direction
    ma200 = mas.get("ma_200d")
    if ma200 and curr:
        checks.append(_chk("Above 200d MA", curr > ma200, f"${curr:.2f} vs ${ma200:.2f}"))
    else:
        checks.append(_chk("Above 200d MA", None, "N/A"))

    # 3. MACD bullish crossover
    macd_crossover = (technicals.get("macd") or {}).get("crossover")
    if macd_crossover:
        checks.append(_chk("MACD Bullish", macd_crossover == "bullish", macd_crossover.capitalize()))
    else:
        checks.append(_chk("MACD Bullish", None, "N/A"))

    # 4. RSI in the sweet spot (40–70) — not overbought or chasing
    rsi = technicals.get("rsi_14")
    if rsi is not None:
        checks.append(_chk("RSI 40–70", 40 <= rsi <= 70, f"{rsi:.1f}", "Outside = chasing or exhaustion"))
    else:
        checks.append(_chk("RSI 40–70", None, "N/A"))

    # 5. Price above VWAP
    vwap = technicals.get("vwap_20d")
    if vwap and curr:
        checks.append(_chk("Above VWAP", curr > vwap, f"${curr:.2f} vs ${vwap:.2f}"))
    else:
        checks.append(_chk("Above VWAP", None, "N/A"))

    # 6. RVOL ≥ 1.5 (time-normalized during session; raw vol ratio otherwise)
    rvol_data = price.get("rvol") or {}
    rvol_val  = rvol_data.get("rvol")
    if rvol_val is not None and "extended" not in (rvol_data.get("signal") or ""):
        checks.append(_chk("RVOL ≥ 1.5x", rvol_val >= 1.5, f"{rvol_val:.2f}x"))
    else:
        vol_ratio = price.get("volume_ratio")
        if vol_ratio is not None:
            checks.append(_chk("Vol Ratio ≥ 1.5x", vol_ratio >= 1.5, f"{vol_ratio:.2f}x"))
        else:
            checks.append(_chk("RVOL ≥ 1.5x", None, "N/A"))

    # 7. Today's volume above 20d average
    vol = price.get("volume")
    avg_vol = price.get("avg_volume")
    if vol and avg_vol:
        checks.append(_chk(
            "Vol > Avg",
            vol > avg_vol,
            f"{vol / 1_000_000:.1f}M vs {avg_vol / 1_000_000:.1f}M avg",
        ))
    else:
        checks.append(_chk("Vol > Avg", None, "N/A"))

    # 8. Catalyst / news present
    news_items = (news or {}).get("news") or []
    n = len(news_items)
    checks.append(_chk("Catalyst/News", n > 0, f"{n} article{'s' if n != 1 else ''}"))

    # 9. Sector positive (5-day change > 0)
    stock_sector = price.get("sector", "")
    sector_passed: bool | None = None
    sector_val = "N/A"
    for s in ((sectors or {}).get("sectors") or []):
        name = s.get("sector", "")
        if stock_sector and (stock_sector.lower() in name.lower() or name.lower() in stock_sector.lower()):
            chg = s.get("change_5d_pct")
            if chg is not None:
                sector_passed = chg > 0
                sector_val = f"{chg:+.1f}% 5d"
            break
    checks.append(_chk("Sector Positive", sector_passed, sector_val))

    # 10. Short float < 20% (not a heavily shorted trap)
    si_float = (short_interest or {}).get("short_pct_of_float")
    if si_float is not None:
        checks.append(_chk("Short Float < 20%", si_float < 20, f"{si_float:.1f}%"))
    else:
        checks.append(_chk("Short Float < 20%", None, "N/A"))

    # Score: True=1, False=0, None=0 — always out of 10
    score = sum(1 for c in checks if c["pass"] is True)
    total = 10

    if score >= 8:
        verdict, verdict_color = "PROCEED", "green"
    elif score >= 5:
        verdict, verdict_color = "CAUTION", "amber"
    else:
        verdict, verdict_color = "AVOID", "red"

    return {
        "score":        score,
        "total":        total,
        "verdict":      verdict,
        "verdict_color": verdict_color,
        "checks":       checks,
    }
