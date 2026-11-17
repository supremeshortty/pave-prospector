"""SEC EDGAR full-text search: recent filings that name the company.

Free. The SEC asks every client to send a User-Agent with a contact email (set PROSPECTOR_CONTACT).
Form D = a private fundraise; 8-K/10-Q/10-K/ABS = public-company events, credit facilities, securitizations.
"""
from __future__ import annotations

from datetime import date, timedelta

SEARCH = "https://efts.sec.gov/LATEST/search-index"
FORMS = "D,8-K,10-K,10-Q,ABS-15G,SF-3,424B5"


def filings(fetcher, name: str, days: int = 365, extra: str = "") -> list[dict]:
    """Filings in the last `days` whose text contains the exact company name (and `extra`, if given)."""
    q = f'"{name}"' + (f" {extra}" if extra else "")
    params = {
        "q": q, "forms": FORMS, "dateRange": "custom",
        "startdt": (date.today() - timedelta(days=days)).isoformat(), "enddt": date.today().isoformat(),
    }
    data = fetcher.get_json(SEARCH, params=params) or {}
    out = []
    for h in ((data.get("hits") or {}).get("hits") or [])[:20]:
        s = h.get("_source") or {}
        adsh = (s.get("adsh") or h.get("_id", "").split(":")[0]).replace("-", "")
        file_name = h.get("_id", ":").split(":", 1)[-1]
        cik = (s.get("ciks") or [""])[0].lstrip("0")
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/{file_name}"
               if cik and adsh else "https://efts.sec.gov/LATEST/search-index?q=" + q)
        out.append({
            "form": s.get("form") or s.get("file_type", ""),
            "date": s.get("file_date", ""),
            "filer": ", ".join(s.get("display_names") or [])[:120],
            "url": url,
        })
    return out
