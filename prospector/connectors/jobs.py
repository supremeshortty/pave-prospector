"""Open roles from public job boards (Greenhouse, Lever, Ashby). Free, no key.

The board slug is usually the domain name without the TLD ('dave.com' -> 'dave').
Set `ats: greenhouse:<slug>` in seeds.yaml when it isn't.
"""
from __future__ import annotations

from typing import Optional

BOARDS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def _candidates(domain: str, name: str, ats: Optional[str]) -> list[tuple[str, str]]:
    if ats and ":" in ats:
        board, slug = ats.split(":", 1)
        return [(board, slug)]
    stem = domain.split(".")[0].lower()
    name_slug = "".join(c for c in name.lower() if c.isalnum())
    slugs = list(dict.fromkeys([stem, name_slug]))
    return [(b, s) for s in slugs for b in BOARDS]


def open_roles(fetcher, domain: str, name: str, ats: Optional[str] = None) -> dict:
    """Every open role on the first board that answers, as {board, slug, roles: [...]}."""
    for board, slug in _candidates(domain, name, ats):
        data = fetcher.get_json(BOARDS[board].format(slug=slug))
        roles = _parse(board, data)
        if roles:
            return {"board": board, "slug": slug, "roles": roles}
    return {"board": None, "slug": None, "roles": []}


def _parse(board: str, data) -> list[dict]:
    if not data:
        return []
    if board == "greenhouse":
        return [{"title": j.get("title", ""), "url": j.get("absolute_url", ""),
                 "location": (j.get("location") or {}).get("name", "")} for j in data.get("jobs", [])]
    if board == "lever" and isinstance(data, list):
        return [{"title": j.get("text", ""), "url": j.get("hostedUrl", ""),
                 "location": (j.get("categories") or {}).get("location", "")} for j in data]
    if board == "ashby":
        return [{"title": j.get("title", ""), "url": j.get("jobUrl", ""),
                 "location": j.get("location", "")} for j in data.get("jobs", [])]
    return []
