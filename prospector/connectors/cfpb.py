"""CFPB Consumer Complaint Database: complaints with consumer narratives, last 12 months.

Free public API, no key: https://cfpb.github.io/api/ccdb/
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

BASE = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
SUGGEST = BASE + "_suggest_company"
JSON_HEADERS = {"Accept": "application/json"}


def resolve_company(fetcher, text: str) -> Optional[str]:
    """The legal company name the CFPB uses, e.g. 'Dave' -> 'Dave Inc.'."""
    data = fetcher.get_json(SUGGEST, params={"text": text}, headers=JSON_HEADERS)
    if isinstance(data, list) and data:
        lowered = text.lower()
        for name in data:
            if str(name).lower().startswith(lowered):
                return str(name)
        return str(data[0])
    return None


def complaints(fetcher, company: str, days: int = 365, size: int = 100) -> dict:
    """Total complaint count plus recent narratives for one company."""
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {
        "company": company, "date_received_min": since, "has_narrative": "true",
        "size": size, "sort": "created_date_desc", "no_aggs": "true",
    }
    data = fetcher.get_json(BASE, params=params, headers=JSON_HEADERS) or {}
    hits = data.get("hits") or {}
    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value", 0)
    out = []
    for h in hits.get("hits") or []:
        s = h.get("_source") or {}
        cid = s.get("complaint_id") or h.get("_id")
        out.append({
            "source": "cfpb",
            "rating": None,
            "title": f"{s.get('product', '')}: {s.get('issue', '')}".strip(": "),
            "text": s.get("complaint_what_happened", ""),
            "date": (s.get("date_received") or "")[:10],
            "url": f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{cid}",
        })
    return {"company": company, "total_with_narrative": total or len(out), "items": out}
