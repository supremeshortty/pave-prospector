"""Apple App Store: find a company's app and read its recent reviews.

Uses Apple's free iTunes Search API and the public customer-reviews RSS feed. No key needed.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

SEARCH_URL = "https://itunes.apple.com/search"
REVIEWS_URL = "https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"


def _domain_of(url: str) -> str:
    url = (url or "").lower()
    for prefix in ("https://", "http://", "www."):
        url = url.replace(prefix, "")
    return url.split("/")[0]


def _norm(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalnum())


def find_app(fetcher, term: str, domain: str = "", name: str = "") -> Optional[dict]:
    """Best App Store match for a company: same seller website first, then name match, then most ratings."""
    data = fetcher.get_json(SEARCH_URL, params={"term": term, "entity": "software", "country": "us", "limit": 15})
    results = (data or {}).get("results", [])
    if not results:
        return None

    def rank(r):
        same_site = bool(domain) and domain.lower() in _domain_of(r.get("sellerUrl", ""))
        hay = _norm(r.get("trackName", "") + " " + r.get("sellerName", ""))
        name_hit = bool(name) and _norm(name.split(" (")[0]) in hay  # whole name, so "Credit Strong" != "Credit Karma"
        return (same_site, name_hit, r.get("userRatingCount", 0))

    # Lenders often have a separate investor app; its reviews are about returns, not borrowing.
    results = [r for r in results if "invest" not in r.get("trackName", "").lower()]
    if not results:
        return None
    best = max(results, key=rank)
    if not (rank(best)[0] or rank(best)[1]):
        return None  # nothing that is clearly this company's app
    return {
        "app_id": best.get("trackId"),
        "name": best.get("trackName"),
        "seller": best.get("sellerName"),
        "ratings": best.get("userRatingCount", 0),
        "rating": round(best.get("averageUserRating", 0.0), 2),
        "url": best.get("trackViewUrl"),
        "genre": best.get("primaryGenreName"),
    }


def reviews(fetcher, app_id, pages: int = 2, max_age_days: int = 365) -> list[dict]:
    """Most recent reviews (50 per page) from the last `max_age_days`. Low-star reviews are where the gaps show up."""
    cutoff = (date.today() - timedelta(days=max_age_days)).isoformat()
    out = []
    for page in range(1, pages + 1):
        data = fetcher.get_json(REVIEWS_URL.format(page=page, app_id=app_id))
        entries = ((data or {}).get("feed") or {}).get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        for e in entries:
            if "im:rating" not in e:
                continue  # the first entry on older feeds describes the app, not a review
            if e.get("updated", {}).get("label", "")[:10] < cutoff:
                continue
            out.append({
                "source": "app_store",
                "rating": int(e["im:rating"]["label"]),
                "title": e.get("title", {}).get("label", ""),
                "text": e.get("content", {}).get("label", ""),
                "date": e.get("updated", {}).get("label", "")[:10],
                "url": f"https://apps.apple.com/us/app/id{app_id}?see-all=reviews",
            })
        if len(entries) < 50:
            break
    return out
