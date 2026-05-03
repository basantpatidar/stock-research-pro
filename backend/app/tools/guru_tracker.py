from langchain_core.tools import tool
import requests
import re
import time
from datetime import datetime

_HEADERS = {"User-Agent": "StockResearchPro research@stockresearchpro.local"}
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_IDX_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&dateb=&owner=include&count=3&search_text=&output=atom"
_XBRL_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/NumberOfSharesHeldInSecurityByInvestment/shares/CY{year}Q{quarter}I.json"

# Known institutional gurus: name → CIK
_GURUS: dict[str, str] = {
    "Berkshire Hathaway (Buffett)": "0001067294",
    "Pershing Square (Ackman)": "0001336528",
    "Appaloosa (Tepper)": "0001006438",
    "Third Point (Loeb)": "0001040273",
    "Duquesne (Druckenmiller)": "0001040570",
    "Baupost (Klarman)": "0001061219",
    "Viking Global (Halvorsen)": "0001103804",
    "Citadel (Griffin)": "0001423298",
}


def _get_latest_13f_accession(cik: str) -> tuple[str, str] | tuple[None, None]:
    """Returns (accession_no, filing_date) of latest 13F-HR."""
    try:
        time.sleep(0.12)
        r = requests.get(_SUBMISSIONS_URL.format(cik=cik.lstrip("0").zfill(10)), headers=_HEADERS, timeout=12)
        if not r.ok:
            return None, None
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        for i, form in enumerate(forms):
            if form == "13F-HR":
                return accessions[i], dates[i]
        return None, None
    except Exception:
        return None, None


def _search_13f_for_ticker(cik_raw: str, accession: str, target_ticker: str) -> dict | None:
    """Download 13F filing index and search for target ticker holding."""
    try:
        cik = cik_raw.lstrip("0")
        acc_clean = accession.replace("-", "")
        idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{accession}-index.htm"
        time.sleep(0.12)
        r = requests.get(idx_url, headers=_HEADERS, timeout=12)
        if not r.ok:
            # Try direct XML search
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/infotable.xml"
            r = requests.get(xml_url, headers=_HEADERS, timeout=15)
            if not r.ok:
                return None
            content = r.text
        else:
            # Find the primary infotable document
            links = re.findall(r'href="([^"]+infotable[^"]*)"', r.text, re.IGNORECASE)
            if not links:
                return None
            xml_url = "https://www.sec.gov" + links[0]
            time.sleep(0.12)
            xr = requests.get(xml_url, headers=_HEADERS, timeout=15)
            if not xr.ok:
                return None
            content = xr.text

        # Search for ticker in XML
        ticker_upper = target_ticker.upper()
        # 13F XML has <nameOfIssuer> and holdings
        entries = re.findall(
            r'<nameOfIssuer>([^<]+)</nameOfIssuer>.*?<value>(\d+)</value>.*?<sshPrnamt>(\d+)</sshPrnamt>',
            content, re.DOTALL | re.IGNORECASE
        )
        for entry in entries:
            name, value_thousands, shares = entry
            # Match by known ticker aliases (crude but works for large names)
            name_clean = name.upper().strip()
            if ticker_upper in name_clean or name_clean.startswith(ticker_upper):
                return {
                    "market_value_k": int(value_thousands),
                    "shares": int(shares),
                    "issuer_name": name.strip(),
                }
        return None
    except Exception:
        return None


@tool
def get_guru_holdings(ticker: str) -> dict:
    """
    Check if any major institutional gurus (Buffett, Ackman, Druckenmiller, etc.)
    hold this stock via SEC 13F-HR filings. Free from EDGAR — no API key.
    """
    try:
        sym = ticker.upper().strip()
        holdings = []

        for guru_name, cik in _GURUS.items():
            accession, filing_date = _get_latest_13f_accession(cik)
            if not accession:
                continue
            holding = _search_13f_for_ticker(cik, accession, sym)
            if holding:
                holdings.append({
                    "guru": guru_name,
                    "filing_date": filing_date,
                    "shares": holding["shares"],
                    "market_value_m": round(holding["market_value_k"] / 1000, 1),
                    "issuer_name": holding["issuer_name"],
                })

        if holdings:
            verdict = f"Held by {len(holdings)} guru(s)"
            verdict_color = "green"
        else:
            verdict = "No major guru holdings found"
            verdict_color = "neutral"

        return {
            "ticker": sym,
            "gurus_holding": holdings,
            "holding_count": len(holdings),
            "verdict": verdict,
            "verdict_color": verdict_color,
            "data_source": "SEC EDGAR 13F-HR filings",
            "note": "13F filed quarterly with 45-day lag — may not reflect current positions",
        }
    except Exception as e:
        return {"error": f"Guru tracker failed for {ticker}: {str(e)}"}
