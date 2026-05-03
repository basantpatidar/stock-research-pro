from langchain_core.tools import tool
import requests
import time

_HEADERS = {"User-Agent": "StockResearchPro research@stockresearchpro.local"}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

_ticker_to_cik: dict[str, str] = {}


def _get_cik(ticker: str) -> str | None:
    global _ticker_to_cik
    if not _ticker_to_cik:
        try:
            r = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
            if r.ok:
                data = r.json()
                _ticker_to_cik = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}
        except Exception:
            pass
    return _ticker_to_cik.get(ticker.upper())


def _extract_series(facts: dict, taxonomy: str, concept: str, unit: str = "USD") -> list[dict]:
    """Pull annual (10-K) values for a given XBRL concept."""
    try:
        entries = facts.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {}).get(unit, [])
        annual = [e for e in entries if e.get("form") in ("10-K", "10-K/A") and e.get("val") is not None]
        # deduplicate by fiscal year end
        seen: dict[str, dict] = {}
        for e in annual:
            fy = e.get("end", "")[:4]
            if fy not in seen or e.get("filed", "") > seen[fy].get("filed", ""):
                seen[fy] = e
        return [{"year": int(fy), "value": v["val"]} for fy, v in sorted(seen.items()) if fy.isdigit()][-8:]
    except Exception:
        return []


@tool
def get_edgar_fundamentals(ticker: str) -> dict:
    """
    Pull 8 years of audited financial data from SEC EDGAR XBRL filings.
    No API key required. Returns revenue, net income, FCF, operating income, debt/equity.
    """
    try:
        cik = _get_cik(ticker)
        if not cik:
            return {"error": f"CIK not found for {ticker} — may not be SEC-listed"}

        time.sleep(0.12)  # respect EDGAR 10 req/s limit
        r = requests.get(_FACTS_URL.format(cik=cik), headers=_HEADERS, timeout=15)
        if not r.ok:
            return {"error": f"EDGAR returned {r.status_code} for {ticker}"}

        facts = r.json()
        entity_name = facts.get("entityName", ticker.upper())

        revenue = _extract_series(facts, "us-gaap", "Revenues") or \
                  _extract_series(facts, "us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax") or \
                  _extract_series(facts, "us-gaap", "SalesRevenueNet")

        net_income = _extract_series(facts, "us-gaap", "NetIncomeLoss")

        op_income = _extract_series(facts, "us-gaap", "OperatingIncomeLoss")

        # FCF proxy: operating cash flow - capex
        ocf = _extract_series(facts, "us-gaap", "NetCashProvidedByUsedInOperatingActivities")
        capex = _extract_series(facts, "us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment")
        fcf = []
        if ocf and capex:
            capex_map = {e["year"]: e["value"] for e in capex}
            for e in ocf:
                cap = capex_map.get(e["year"], 0)
                fcf.append({"year": e["year"], "value": e["value"] - cap})

        total_debt = _extract_series(facts, "us-gaap", "LongTermDebt") or \
                     _extract_series(facts, "us-gaap", "DebtCurrent")

        def _to_b(series: list[dict]) -> list[dict]:
            return [{"year": e["year"], "value": round(e["value"] / 1e9, 2)} for e in series]

        return {
            "ticker": ticker.upper(),
            "entity_name": entity_name,
            "cik": cik,
            "revenue_b": _to_b(revenue),
            "net_income_b": _to_b(net_income),
            "operating_income_b": _to_b(op_income),
            "fcf_b": _to_b(fcf),
            "total_debt_b": _to_b(total_debt),
            "years_available": max(
                len(revenue), len(net_income), len(op_income), len(fcf)
            ),
            "source": "SEC EDGAR XBRL",
        }
    except Exception as e:
        return {"error": f"EDGAR fundamentals failed for {ticker}: {str(e)}"}
