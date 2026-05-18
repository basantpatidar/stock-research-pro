"""Stock universes for the screener.

The screener used to walk a 30-symbol hardcoded list (`large_cap_tickers[:30]`).
This module replaces that with named universes spanning ~150 highly-liquid US
equities/ETFs across all 11 GICS sectors, plus a focused NASDAQ-100 list and
the major broad-market ETFs. Lists are hand-picked rather than scraped so the
screener works offline and on the deploy laptop without needing a network
call to build its ticker universe.

Why not the full S&P 500? Each ticker is one yfinance fetch (~200 ms). 500
tickers ≈ 100 s per screen and would time-out the API. 150 keeps a single
screen under ~30 s with parallel fetching disabled, ~10 s with it.

Adding new symbols: keep the per-sector lists alphabetised; bias toward
names with avg daily volume > 5M to keep yfinance fetches healthy.
"""

from __future__ import annotations

# ── Sector buckets (GICS-aligned, large + mid cap, US listings) ───────────────

_TECH = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "GOOG",
    "AMZN",
    "META",
    "NVDA",
    "AVGO",
    "ORCL",
    "ADBE",
    "CRM",
    "CSCO",
    "AMD",
    "INTC",
    "QCOM",
    "TXN",
    "INTU",
    "NOW",
    "IBM",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "ADI",
    "PANW",
    "SNPS",
    "CDNS",
]

_FINANCIALS = [
    "JPM",
    "BAC",
    "WFC",
    "C",
    "GS",
    "MS",
    "BLK",
    "AXP",
    "USB",
    "PNC",
    "TFC",
    "SCHW",
    "COF",
    "BX",
    "KKR",
    "V",
    "MA",
    "PYPL",
]

_HEALTHCARE = [
    "JNJ",
    "UNH",
    "LLY",
    "PFE",
    "ABBV",
    "MRK",
    "TMO",
    "ABT",
    "DHR",
    "BMY",
    "AMGN",
    "GILD",
    "ISRG",
    "CVS",
    "CI",
    "ELV",
    "VRTX",
]

_CONSUMER_DISCRETIONARY = [
    "TSLA",
    "HD",
    "NKE",
    "MCD",
    "LOW",
    "SBUX",
    "TJX",
    "BKNG",
    "ABNB",
    "DIS",
    "GM",
    "F",
    "MAR",
    "EBAY",
]

_CONSUMER_STAPLES = [
    "WMT",
    "COST",
    "PG",
    "KO",
    "PEP",
    "PM",
    "MO",
    "MDLZ",
    "TGT",
    "CL",
    "KMB",
    "GIS",
]

_INDUSTRIALS = [
    "BA",
    "CAT",
    "HON",
    "LMT",
    "RTX",
    "DE",
    "UNP",
    "UPS",
    "FDX",
    "GE",
    "MMM",
    "ETN",
    "EMR",
    "ITW",
    "NOC",
]

_ENERGY = [
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "EOG",
    "MPC",
    "PSX",
    "VLO",
    "OXY",
    "HES",
]

_COMMUNICATION_SERVICES = [
    "NFLX",
    "T",
    "VZ",
    "TMUS",
    "CMCSA",
    "DIS",
    "EA",
    "TTWO",
]

_UTILITIES = [
    "NEE",
    "DUK",
    "SO",
    "AEP",
    "D",
    "EXC",
    "SRE",
]

_MATERIALS = [
    "LIN",
    "SHW",
    "APD",
    "ECL",
    "FCX",
    "NEM",
    "DOW",
    "DD",
]

_REAL_ESTATE = [
    "PLD",
    "AMT",
    "CCI",
    "EQIX",
    "PSA",
    "O",
    "SPG",
]

_ETFS_BROAD = [
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "VTI",
    "VOO",
]

_ETFS_SECTOR = [
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLU",
    "XLRE",
    "XLC",
]

_ETFS_FACTOR = [
    "GLD",
    "SLV",
    "TLT",
    "HYG",
    "LQD",
    "VIXY",
    "UUP",
]


# ── Named universes (deduped, preserving insertion order) ─────────────────────


def _dedup(*lists) -> list[str]:
    """Flatten + dedupe while preserving first-occurrence order. Cheaper than
    set() + sort because callers want a stable per-screen order — keeps the
    same ticker at the same array index across runs, which matters for the
    'top N' truncation logic in run_screener."""
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for t in lst:
            if t not in seen:
                out.append(t)
                seen.add(t)
    return out


SP500_LIQUID: list[str] = _dedup(
    _TECH,
    _FINANCIALS,
    _HEALTHCARE,
    _CONSUMER_DISCRETIONARY,
    _CONSUMER_STAPLES,
    _INDUSTRIALS,
    _ENERGY,
    _COMMUNICATION_SERVICES,
    _UTILITIES,
    _MATERIALS,
    _REAL_ESTATE,
)
"""~150 large/mid-cap S&P 500 names spanning all 11 GICS sectors. Default
universe for the screener — broad coverage without timeouts."""


NASDAQ100_LIQUID: list[str] = _dedup(
    _TECH,
    _COMMUNICATION_SERVICES,
    ["TSLA", "AMZN", "META", "GOOGL", "GOOG", "PEP", "COST", "NFLX", "PYPL"],
)
"""NASDAQ-100 large names — tech-and-growth focus."""


ETFS: list[str] = _dedup(_ETFS_BROAD, _ETFS_SECTOR, _ETFS_FACTOR)
"""Major broad-market, sector, and factor ETFs."""


MEGA_CAP: list[str] = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "BRK-B",
    "AVGO",
    "JPM",
    "LLY",
    "V",
    "UNH",
    "XOM",
    "MA",
    "WMT",
    "JNJ",
    "PG",
]
"""$200B+ market cap — the smallest, fastest screen for quick scans."""


# Legacy 30-symbol list preserved for back-compat with cached presets that
# baked in the old behavior. Do not extend; new presets get a named universe.
LEGACY_TOP30 = _dedup(
    _TECH[:15],
    _FINANCIALS[:6],
    _HEALTHCARE[:5],
    _ENERGY[:4],
)


# ── Public dispatcher ─────────────────────────────────────────────────────────

UNIVERSES: dict[str, list[str]] = {
    "sp500": SP500_LIQUID,
    "nasdaq100": NASDAQ100_LIQUID,
    "etfs": ETFS,
    "mega": MEGA_CAP,
    "legacy": LEGACY_TOP30,
}


def get_universe(name: str = "sp500") -> list[str]:
    """Resolve a universe name to its ticker list. Falls back to sp500 on
    unknown name — the screener should never crash on a typo."""
    return UNIVERSES.get(name.lower(), SP500_LIQUID)
