def compute_smart_money_score(
    congressional: dict,
    analyst: dict,
    short_interest: dict,
) -> dict:
    """
    Synthesizes congressional trade direction, analyst upgrade momentum,
    and short squeeze positioning into a single Smart Money verdict.
    Pure T1 aggregation — 0 tokens.
    """
    signals = []

    # 1. Congressional trades (politicians with advance knowledge)
    if isinstance(congressional, dict) and not congressional.get("error"):
        sentiment = congressional.get("net_sentiment")
        total = congressional.get("total_trades", 0) or 0
        if sentiment == "bullish" and total > 0:
            signals.append(
                {
                    "label": "Congressional",
                    "direction": "bullish",
                    "detail": f"Net buying ({total} trade{'s' if total != 1 else ''})",
                }
            )
        elif sentiment == "bearish" and total > 0:
            signals.append(
                {
                    "label": "Congressional",
                    "direction": "bearish",
                    "detail": f"Net selling ({total} trade{'s' if total != 1 else ''})",
                }
            )

    # 2. Analyst rating momentum — upgrades vs downgrades
    if isinstance(analyst, dict) and not analyst.get("error"):
        changes = analyst.get("recent_rating_changes", []) or []
        upgrades = sum(
            1 for c in changes if c.get("action", "").lower() in ("upgrade", "init", "initiated")
        )
        downgrades = sum(1 for c in changes if c.get("action", "").lower() == "downgrade")
        if upgrades > downgrades:
            signals.append(
                {
                    "label": "Analyst Momentum",
                    "direction": "bullish",
                    "detail": f"{upgrades} upgrade{'s' if upgrades != 1 else ''} vs {downgrades} downgrade{'s' if downgrades != 1 else ''}",
                }
            )
        elif downgrades > upgrades:
            signals.append(
                {
                    "label": "Analyst Momentum",
                    "direction": "bearish",
                    "detail": f"{downgrades} downgrade{'s' if downgrades != 1 else ''} vs {upgrades} upgrade{'s' if upgrades != 1 else ''}",
                }
            )

    # 3. Short positioning — heavy short = institutional distribution; squeeze setup = potential reversal
    if isinstance(short_interest, dict) and not short_interest.get("error"):
        squeeze_score = short_interest.get("squeeze_score") or 0
        short_pct = short_interest.get("short_pct_of_float") or 0
        if squeeze_score >= 65:
            signals.append(
                {
                    "label": "Short Positioning",
                    "direction": "bullish",
                    "detail": f"High squeeze probability ({squeeze_score}/100)",
                }
            )
        elif short_pct > 20:
            signals.append(
                {
                    "label": "Short Positioning",
                    "direction": "bearish",
                    "detail": f"Heavy institutional short interest ({short_pct}% of float)",
                }
            )

    bullish = sum(1 for s in signals if s["direction"] == "bullish")
    bearish = sum(1 for s in signals if s["direction"] == "bearish")

    if bullish > bearish:
        verdict, color = "ACCUMULATING", "green"
    elif bearish > bullish:
        verdict, color = "DISTRIBUTING", "red"
    else:
        verdict, color = "NEUTRAL", "neutral"

    return {
        "verdict": verdict,
        "color": color,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "signals": signals,
    }
