import re
import time

import requests
from langchain_core.tools import tool

_HEADERS = {"User-Agent": "StockResearchPro research@stockresearchpro.local"}
_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms=10-K&hits.hits._source=period_of_report,file_date,entity_name,file_num"
_FILING_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_ticker_cik_cache: dict[str, str] = {}


def _get_cik(ticker: str) -> str | None:
    global _ticker_cik_cache
    if not _ticker_cik_cache:
        try:
            r = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
            if r.ok:
                data = r.json()
                _ticker_cik_cache = {
                    v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()
                }
        except Exception:
            pass
    return _ticker_cik_cache.get(ticker.upper())


def _get_recent_10k_filings(cik: str, limit: int = 2) -> list[dict]:
    """Get accession numbers + filenames for the 2 most recent 10-K filings."""
    time.sleep(0.15)
    r = requests.get(_FILING_URL.format(cik=cik), headers=_HEADERS, timeout=15)
    if not r.ok:
        return []
    data = r.json()
    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    accessions = filings.get("accessionNumber", [])
    dates = filings.get("filingDate", [])
    docs = filings.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form in ("10-K", "10-K/A") and len(results) < limit:
            results.append(
                {
                    "accession": accessions[i].replace("-", ""),
                    "accession_raw": accessions[i],
                    "date": dates[i],
                    "primary_doc": docs[i],
                }
            )
    return results


def _fetch_risk_factors(cik: str, accession: str, filename: str) -> str:
    """Download filing and extract Item 1A Risk Factors section (up to 4000 chars)."""
    try:
        url = _DOC_URL.format(cik=cik.lstrip("0"), accession=accession, filename=filename)
        time.sleep(0.15)
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if not r.ok:
            return ""
        text = r.text
        # Strip HTML
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text)

        # Find Item 1A
        match = re.search(r"(?i)item\s+1a[\.\s]+risk\s+factors", text)
        if not match:
            return text[:3000]  # fallback to beginning
        start = match.start()
        # Find next major item (Item 1B, Item 2, etc.)
        end_match = re.search(r"(?i)item\s+1b|item\s+2[\.\s]+", text[start + 200 :])
        end = start + 200 + end_match.start() if end_match else start + 6000
        return text[start:end][:5000]
    except Exception:
        return ""


def _llm_diff(current_text: str, prior_text: str, ticker: str) -> dict:
    try:
        from app.config import Settings
        from app.llm.factory import get_llm_with_fallback

        settings = Settings()
        llm = get_llm_with_fallback(settings)
        prompt = f"""You are analyzing SEC 10-K risk factor changes for {ticker}.

CURRENT YEAR RISK FACTORS (excerpt):
{current_text[:2500]}

PRIOR YEAR RISK FACTORS (excerpt):
{prior_text[:2500]}

Identify:
1. NEW risks added this year (not in prior year)
2. REMOVED risks (in prior year but dropped this year)
3. MATERIALLY CHANGED risks (same topic but significantly different language or severity)
4. Overall risk trajectory: INCREASING / STABLE / DECREASING

Respond in this exact JSON format:
{{
  "new_risks": ["risk 1", "risk 2"],
  "removed_risks": ["risk 1", "risk 2"],
  "changed_risks": [{{"topic": "...", "change": "..."}}],
  "trajectory": "INCREASING|STABLE|DECREASING",
  "trajectory_color": "red|neutral|green",
  "summary": "2-sentence overall assessment"
}}"""
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        import json

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"summary": content[:500], "trajectory": "STABLE", "trajectory_color": "neutral"}
    except Exception as e:
        return {
            "error": f"LLM diff failed: {str(e)}",
            "trajectory": "UNKNOWN",
            "trajectory_color": "neutral",
        }


@tool
def get_risk_factor_changes(ticker: str) -> dict:
    """
    Compare this year's 10-K risk factors to last year's using SEC EDGAR + LLM diff.
    Identifies newly added risks, removed risks, and changed severity. ~2000 tokens.
    """
    try:
        cik = _get_cik(ticker)
        if not cik:
            return {"error": f"CIK not found for {ticker}"}

        filings = _get_recent_10k_filings(cik, limit=2)
        if len(filings) < 2:
            return {
                "error": f"Need at least 2 10-K filings for {ticker} to compare — only found {len(filings)}"
            }

        current_filing = filings[0]
        prior_filing = filings[1]

        current_text = _fetch_risk_factors(
            cik.lstrip("0"), current_filing["accession"], current_filing["primary_doc"]
        )
        prior_text = _fetch_risk_factors(
            cik.lstrip("0"), prior_filing["accession"], prior_filing["primary_doc"]
        )

        if not current_text or not prior_text:
            return {"error": f"Could not extract risk factors from EDGAR filings for {ticker}"}

        diff = _llm_diff(current_text, prior_text, ticker)

        return {
            "ticker": ticker.upper(),
            "current_filing_date": current_filing["date"],
            "prior_filing_date": prior_filing["date"],
            "new_risks": diff.get("new_risks", []),
            "removed_risks": diff.get("removed_risks", []),
            "changed_risks": diff.get("changed_risks", []),
            "trajectory": diff.get("trajectory", "UNKNOWN"),
            "trajectory_color": diff.get("trajectory_color", "neutral"),
            "summary": diff.get("summary", ""),
            "source": "SEC EDGAR 10-K full-text",
        }
    except Exception as e:
        return {"error": f"Risk factor analysis failed for {ticker}: {str(e)}"}
