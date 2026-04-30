"""
Shared verdict/signal types used by every tool in the app.

Every metric resolves to a SignalResult. The `score_contribution` field
(-2.0 to +2.0) feeds the composite ticker-level verdict.

Composite thresholds:
  >= 1.5  → STRONG_BUY
  >= 0.5  → BUY
  >= -0.5 → HOLD
  >= -1.5 → SELL
  <  -1.5 → AVOID
"""

from __future__ import annotations
from typing import Literal

Verdict = Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "AVOID", "RISK_FLAG"]
Conviction = Literal["HIGH", "MODERATE", "LOW", "MIXED"]
Direction = Literal["IMPROVING", "DETERIORATING", "STABLE", "UNKNOWN"]


def build_signal(
    value,
    verdict: Verdict,
    conviction: Conviction,
    headline: str,
    why: str,
    action: str,
    key_risk: str,
    direction: Direction = "UNKNOWN",
    direction_note: str = "",
    score_contribution: float = 0.0,
) -> dict:
    """Return a fully-structured signal dict ready for JSON serialisation."""
    return {
        "value": value,
        "verdict": verdict,
        "conviction": conviction,
        "headline": headline,
        "why": why,
        "action": action,
        "key_risk": key_risk,
        "direction": direction,
        "direction_note": direction_note,
        "score_contribution": round(score_contribution, 2),
    }


def composite_verdict(signals: list[dict]) -> dict:
    """
    Aggregate a list of SignalResult dicts into a single ticker-level verdict.
    Returns verdict, conviction, score, and signal counts.
    """
    contributions = [s.get("score_contribution", 0.0) for s in signals if s]
    if not contributions:
        return {"verdict": "HOLD", "conviction": "LOW", "score": 0.0, "signal_count": 0, "agree_count": 0}

    score = sum(contributions) / len(contributions)
    score = round(score, 2)

    if score >= 1.5:
        verdict: Verdict = "STRONG_BUY"
    elif score >= 0.5:
        verdict = "BUY"
    elif score >= -0.5:
        verdict = "HOLD"
    elif score >= -1.5:
        verdict = "SELL"
    else:
        verdict = "AVOID"

    # Conviction = how many signals agree with the composite direction
    direction_score = 1 if score > 0 else -1 if score < 0 else 0
    agree = sum(1 for c in contributions if (c > 0) == (direction_score > 0) and direction_score != 0)
    agree_pct = agree / len(contributions) if contributions else 0

    if agree_pct >= 0.8:
        conviction: Conviction = "HIGH"
    elif agree_pct >= 0.6:
        conviction = "MODERATE"
    elif agree_pct >= 0.4:
        conviction = "MIXED"
    else:
        conviction = "LOW"

    return {
        "verdict": verdict,
        "conviction": conviction,
        "score": score,
        "signal_count": len(contributions),
        "agree_count": agree,
    }


# Convenience: map verdict to human label and colour
VERDICT_META = {
    "STRONG_BUY": {"label": "▲▲ STRONG BUY", "color": "#00ff88"},
    "BUY":        {"label": "▲ BUY",          "color": "#22cc66"},
    "HOLD":       {"label": "→ HOLD",          "color": "#ffaa00"},
    "SELL":       {"label": "▼ SELL",          "color": "#ff6644"},
    "AVOID":      {"label": "▼▼ AVOID",        "color": "#ff2222"},
    "RISK_FLAG":  {"label": "⚠ RISK",          "color": "#ff4400"},
}
