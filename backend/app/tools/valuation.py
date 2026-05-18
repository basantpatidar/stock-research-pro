import numpy as np
import yfinance as yf
from langchain_core.tools import tool

from app.tools._yf_client import get_ticker

# Top 5 sector peers by GICS sector (yfinance sector name → tickers)
_SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
    "Healthcare": ["JNJ", "UNH", "LLY", "ABBV", "MRK"],
    "Financial Services": ["JPM", "BAC", "GS", "V", "MA"],
    "Financials": ["JPM", "BAC", "GS", "V", "MA"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST"],
    "Industrials": ["CAT", "HON", "UPS", "GE", "RTX"],
    "Communication Services": ["NFLX", "GOOGL", "META", "DIS", "CMCSA"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "NEM"],
    "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA"],
}


def _dcf(
    fcf_history: list[float],
    growth_rate: float,
    discount_rate: float,
    terminal_growth: float = 0.025,
    years: int = 5,
) -> dict:
    if not fcf_history or fcf_history[-1] <= 0:
        return {}
    base_fcf = fcf_history[-1]
    scenarios = {}
    for label, g in [
        ("bear", growth_rate * 0.5),
        ("base", growth_rate),
        ("bull", growth_rate * 1.5),
    ]:
        pv = 0.0
        for n in range(1, years + 1):
            pv += base_fcf * (1 + g) ** n / (1 + discount_rate) ** n
        terminal = (
            base_fcf * (1 + g) ** years * (1 + terminal_growth) / (discount_rate - terminal_growth)
        )
        pv += terminal / (1 + discount_rate) ** years
        scenarios[label] = round(pv, 0)
    return scenarios


@tool
def get_valuation(ticker: str) -> dict:
    """
    DCF intrinsic value, Graham Number, PEG fair value, and peer comparable analysis.
    All computed from free yfinance data — no paid sources.
    """
    try:
        stock = get_ticker(ticker)
        info = stock.info

        # ── FCF history ──────────────────────────────────────────────────────────
        fcf_history = []
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                for col in cf.columns:
                    row = cf.get("Free Cash Flow") if "Free Cash Flow" in cf.index else None
                    if row is None:
                        ocf = (
                            cf.loc["Operating Cash Flow"].get(col, 0)
                            if "Operating Cash Flow" in cf.index
                            else 0
                        )
                        capex = (
                            cf.loc["Capital Expenditure"].get(col, 0)
                            if "Capital Expenditure" in cf.index
                            else 0
                        )
                        fcf = float(ocf or 0) + float(capex or 0)
                    else:
                        fcf = float(row.get(col, 0) or 0)
                    fcf_history.append(fcf)
                fcf_history = list(reversed(fcf_history))  # oldest first
        except Exception:
            pass

        # ── Revenue CAGR for growth estimate ────────────────────────────────────
        rev_cagr = None
        try:
            inc = stock.income_stmt
            if inc is not None and not inc.empty and "Total Revenue" in inc.index:
                revs = [float(v) for v in inc.loc["Total Revenue"].values if v and not np.isnan(v)]
                if len(revs) >= 2:
                    oldest, newest = revs[-1], revs[0]
                    n = len(revs) - 1
                    rev_cagr = (newest / oldest) ** (1 / n) - 1 if oldest > 0 else None
        except Exception:
            pass

        # ── DCF ─────────────────────────────────────────────────────────────────
        shares = info.get("sharesOutstanding") or 1
        growth = min(max(rev_cagr or 0.08, 0.03), 0.30)
        wacc = 0.10
        dcf_total = _dcf(fcf_history, growth, wacc)
        dcf_per_share = (
            {k: round(v / shares, 2) for k, v in dcf_total.items()} if dcf_total and shares else {}
        )

        # ── Graham Number ────────────────────────────────────────────────────────
        eps = info.get("trailingEps") or info.get("epsCurrentYear")
        bvps = info.get("bookValue")
        graham_number = None
        if eps and bvps and eps > 0 and bvps > 0:
            graham_number = round(np.sqrt(22.5 * eps * bvps), 2)

        # ── PEG fair value ───────────────────────────────────────────────────────
        peg_fair_value = None
        peg_ratio = info.get("pegRatio")
        if eps and rev_cagr and eps > 0:
            growth_pct = (rev_cagr or 0) * 100
            peg_fair_value = round(eps * growth_pct, 2) if growth_pct > 0 else None

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        # ── Peer comps ───────────────────────────────────────────────────────────
        sector = info.get("sector", "")
        peer_tickers = [t for t in _SECTOR_PEERS.get(sector, []) if t != ticker.upper()][:5]
        peers = []
        if peer_tickers:
            try:
                yf.download(peer_tickers, period="1d", auto_adjust=True, progress=False)
                for pt in peer_tickers:
                    try:
                        pi = yf.Ticker(pt).info
                        peers.append(
                            {
                                "ticker": pt,
                                "pe_ratio": pi.get("trailingPE"),
                                "ps_ratio": pi.get("priceToSalesTrailing12Months"),
                                "ev_ebitda": pi.get("enterpriseToEbitda"),
                                "peg_ratio": pi.get("pegRatio"),
                                "market_cap_b": (
                                    round(pi.get("marketCap", 0) / 1e9, 1)
                                    if pi.get("marketCap")
                                    else None
                                ),
                            }
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        # Compute whether stock looks cheap/fair/expensive vs peers
        peer_pes = [p["pe_ratio"] for p in peers if p.get("pe_ratio") and p["pe_ratio"] > 0]
        target_pe = info.get("trailingPE")
        peer_median_pe = float(np.median(peer_pes)) if peer_pes else None
        peer_verdict = None
        peer_verdict_color = "neutral"
        if target_pe and peer_median_pe:
            discount_pct = (peer_median_pe - target_pe) / peer_median_pe * 100
            if discount_pct > 15:
                peer_verdict = f"CHEAP vs peers ({discount_pct:.0f}% P/E discount)"
                peer_verdict_color = "green"
            elif discount_pct < -15:
                peer_verdict = f"PREMIUM vs peers ({-discount_pct:.0f}% P/E premium)"
                peer_verdict_color = "red"
            else:
                peer_verdict = "FAIR VALUE vs peers (P/E within 15% of median)"
                peer_verdict_color = "neutral"

        return {
            "ticker": ticker.upper(),
            "current_price": current_price,
            "sector": sector,
            "dcf_per_share": dcf_per_share,
            "dcf_growth_assumed_pct": round(growth * 100, 1),
            "dcf_wacc_pct": round(wacc * 100, 1),
            "graham_number": graham_number,
            "peg_fair_value": peg_fair_value,
            "peg_ratio": peg_ratio,
            "eps_trailing": eps,
            "book_value_per_share": bvps,
            "revenue_cagr_pct": round(rev_cagr * 100, 1) if rev_cagr else None,
            "peers": peers,
            "peer_median_pe": round(peer_median_pe, 1) if peer_median_pe else None,
            "peer_verdict": peer_verdict,
            "peer_verdict_color": peer_verdict_color,
        }
    except Exception as e:
        return {"error": f"Valuation failed for {ticker}: {str(e)}"}
