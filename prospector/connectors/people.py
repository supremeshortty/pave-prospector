"""Finds the people to contact at an account, from public sources only.

Sources, in the order they're tried:
  1. the company's own leadership / team pages (website.scan)
  2. SEC Form D "related persons" (executive officers named in a fundraise filing)
  3. Google Programmable Search for public LinkedIn profile URLs   (optional free key: GOOGLE_CSE_KEY + GOOGLE_CSE_ID)
  4. Apollo people search                                          (optional key: APOLLO_API_KEY)
  5. Exa people search                                             (optional key: EXA_API_KEY)

LinkedIn itself is never fetched or scraped: only profile URLs that a search engine already returns.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from prospector.connectors.website import match_persona

CSE_URL = "https://www.googleapis.com/customsearch/v1"
APOLLO_SEARCH_URLS = ["https://api.apollo.io/api/v1/mixed_people/api_search",
                      "https://api.apollo.io/api/v1/mixed_people/search"]
EXA_URL = "https://api.exa.ai/search"

LI_TITLE_RE = re.compile(r"^(?P<name>[^\-–|]+?)\s*[-–|]\s*(?P<rest>.+?)(?:\s*\|\s*LinkedIn)?$")


def persona_titles(icp: dict, keys=("credit_leader", "data_science", "payments_ops", "finance")) -> list[str]:
    out = []
    for p in icp["personas"]:
        if p["key"] in keys:
            out += [t for t in p["titles"] if len(t) > 4]
    return out


# ---------- 2. SEC Form D ----------
def form_d_people(fetcher, filing_url: str, icp: dict) -> list[dict]:
    """Executive officers listed in a Form D (primary_doc.xml). Titles aren't given, only the relationship."""
    if not filing_url.endswith(".xml"):
        return []
    status, text = fetcher.get(filing_url)
    if status != 200 or not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    people = []
    for rp in root.iter("relatedPersonInfo"):
        first = (rp.findtext("relatedPersonName/firstName") or "").strip()
        last = (rp.findtext("relatedPersonName/lastName") or "").strip()
        rels = [r.text for r in rp.iter("relationship") if r.text]
        clarify = (rp.findtext("relationshipClarification") or "").strip()
        if not (first and last) or "Executive Officer" not in rels:
            continue
        title = clarify or "Executive officer (SEC Form D)"
        people.append({"name": f"{first.title()} {last.title()}", "title": title,
                       "persona": match_persona(title, icp) or "founder", "source": filing_url})
    return people


# ---------- 3. Google Programmable Search -> LinkedIn URLs ----------
def linkedin_via_cse(fetcher, company: str, icp: dict, env: dict, max_queries: int = 1) -> list[dict]:
    key, cx = env.get("GOOGLE_CSE_KEY"), env.get("GOOGLE_CSE_ID")
    if not (key and cx):
        return []
    titles = ["head of credit", "chief risk officer", "chief credit officer", "vp credit", "credit risk",
              "head of risk", "data science", "cfo"]
    q = f'site:linkedin.com/in "{company}" (' + " OR ".join(f'"{t}"' for t in titles) + ")"
    data = fetcher.get_json(CSE_URL, params={"key": key, "cx": cx, "q": q, "num": 10})
    return _parse_profiles((data or {}).get("items", []), company, icp, "google_cse",
                           title_key="title", url_key="link", snippet_key="snippet")


# ---------- 4. Apollo ----------
def apollo_people(fetcher, domain: str, icp: dict, env: dict) -> list[dict]:
    key = env.get("APOLLO_API_KEY")
    if not key:
        return []
    body = {"q_organization_domains_list": [domain], "person_titles": persona_titles(icp)[:25],
            "page": 1, "per_page": 10}
    headers = {"X-Api-Key": key, "Content-Type": "application/json", "Cache-Control": "no-cache"}
    for url in APOLLO_SEARCH_URLS:
        data = fetcher.post_json(url, body, headers=headers)
        rows = (data or {}).get("people") or []
        if rows:
            out = []
            for r in rows:
                name = (r.get("name") or f"{r.get('first_name', '')} {r.get('last_name', '')}").strip()
                title = r.get("title") or ""
                persona = match_persona(title, icp)
                if name and persona:
                    out.append({"name": name, "title": title, "persona": persona, "source": "apollo",
                                "linkedin": r.get("linkedin_url") or "", "apollo_id": r.get("id", ""),
                                "first_name": r.get("first_name", ""), "last_name": r.get("last_name", "")})
            return out
    return []


# ---------- 5. Exa ----------
def exa_people(fetcher, company: str, icp: dict, env: dict) -> list[dict]:
    key = env.get("EXA_API_KEY")
    if not key:
        return []
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    body = {"query": f"head of credit or chief risk officer at {company}", "category": "linkedin profile",
            "numResults": 10}
    data = fetcher.post_json(EXA_URL, body, headers=headers)
    return _parse_profiles((data or {}).get("results", []), company, icp, "exa",
                           title_key="title", url_key="url", snippet_key="text")


def _parse_profiles(items, company, icp, source, title_key, url_key, snippet_key) -> list[dict]:
    out = []
    first_word = company.lower().split()[0]
    for it in items:
        url = it.get(url_key) or ""
        if "linkedin.com/in/" not in url:
            continue
        m = LI_TITLE_RE.match((it.get(title_key) or "").strip())
        if not m:
            continue
        name, rest = m.group("name").strip(), m.group("rest").strip()
        context = f"{rest} {it.get(snippet_key) or ''}".lower()
        if first_word not in context:
            continue  # profile isn't clearly at this company
        persona = match_persona(rest.split(" - ")[0].split(" at ")[0], icp) or match_persona(rest, icp)
        if persona and 1 < len(name.split()) <= 4:
            out.append({"name": name, "title": rest.split("|")[0].strip()[:90], "persona": persona,
                        "source": source, "linkedin": url.split("?")[0]})
    return out


# ---------- merge ----------
def merge(*groups: list[dict], icp: dict) -> list[dict]:
    """One row per person, best (highest-priority) persona first, sources combined."""
    order = {p["key"]: i for i, p in enumerate(icp["personas"])}
    by_name: dict[str, dict] = {}
    for group in groups:
        for p in group:
            k = re.sub(r"[^a-z]", "", p["name"].lower())
            if not k:
                continue
            cur = by_name.setdefault(k, {"name": p["name"], "title": p.get("title", ""), "persona": p["persona"],
                                          "sources": [], "linkedin": ""})
            if order.get(p["persona"], 99) < order.get(cur["persona"], 99):
                cur["persona"], cur["title"] = p["persona"], p.get("title", cur["title"])
            if p.get("source") and p["source"] not in cur["sources"]:
                cur["sources"].append(p["source"])
            for extra in ("linkedin", "apollo_id", "first_name", "last_name"):
                if p.get(extra) and not cur.get(extra):
                    cur[extra] = p[extra]
    return sorted(by_name.values(), key=lambda p: (order.get(p["persona"], 99), -len(p["sources"])))
