"""A company's own website: tech stack, partner bank, leadership names, and published contact routes.

Fetches a handful of standard pages and obeys robots.txt. Nothing behind a login, no crawling beyond these paths.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

PAGES = ["/", "/about", "/about-us", "/company", "/team", "/leadership", "/press", "/contact", "/legal",
         "/disclosures"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+1[\s.-]?)?\(?\b[2-9]\d{2}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
BANK_RE = re.compile(
    r"(?:issued|provided|offered|originated|made)\s+by\s+([A-Z][A-Za-z&.,' ]{2,60}?(?:Bank|Bancorp|N\.A\.|Trust))",
)
ROLE_INBOXES = ("press", "media", "pr", "partnerships", "partners", "bd", "bizdev", "sales", "hello", "info",
                "contact", "support", "help", "legal", "compliance", "privacy", "careers", "jobs")


def scan(fetcher, domain: str, icp: dict, max_pages: int = 7) -> dict:
    """Read up to `max_pages` standard pages and pull out everything useful for outreach."""
    base = f"https://{domain}"
    seen_text, pages_read = [], []
    html_by_url = {}
    for path in PAGES:
        if len(pages_read) >= max_pages:
            break
        url = urljoin(base, path)
        status, html = fetcher.get(url, respect_robots=True)
        if status != 200 or not html:
            continue
        pages_read.append(url)
        html_by_url[url] = html
        seen_text.append(html)

    blob = "\n".join(seen_text)
    lower = blob.lower()
    result = {
        "pages_read": pages_read,
        "aggregators": _markers(lower, icp["tech_markers"]["aggregators"]),
        "pave_partners": _markers(lower, icp["tech_markers"]["pave_partners"]),
        "partner_bank": _partner_bank(blob),
        "emails": _emails(blob, domain),
        "phones": sorted(set(PHONE_RE.findall(_visible_text(blob))))[:3],
        "socials": _socials(html_by_url),
        "people": [],
    }
    for url, html in html_by_url.items():
        if any(seg in url for seg in ("/press", "/newsroom")):
            continue  # press pages list articles, not people
        for person in extract_people(html, icp):
            person["source"] = url
            result["people"].append(person)
    return result


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _markers(lower_html: str, table: dict) -> list[str]:
    return [name for name, needles in table.items() if any(n.lower() in lower_html for n in needles)]


def _partner_bank(blob: str) -> str:
    text = _visible_text(blob)
    m = BANK_RE.search(text)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip(" ,")
    m = re.search(r"([A-Z][A-Za-z&.' ]{2,40}Bank),?\s+(?:N\.A\.,?\s+)?Member FDIC", text)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _emails(blob: str, domain: str) -> dict:
    """Emails published on the company's own pages, split into personal and role inboxes."""
    root = domain.lower().removeprefix("www.")
    found = {e.lower().rstrip(".") for e in EMAIL_RE.findall(blob)}
    found = {e for e in found if e.split("@")[1].endswith(root) and not e.endswith((".png", ".jpg", ".svg"))}
    role, personal = [], []
    for e in sorted(found):
        local = e.split("@")[0]
        (role if local.split(".")[0] in ROLE_INBOXES or local in ROLE_INBOXES else personal).append(e)
    return {"role": role, "personal": personal}


def _socials(html_by_url: dict) -> dict:
    out = {}
    for html in html_by_url.values():
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            host = urlparse(href).netloc.lower()
            if "linkedin.com" in host and "/company/" in href:
                out.setdefault("linkedin_company", href.split("?")[0])
            elif host in ("twitter.com", "www.twitter.com", "x.com", "www.x.com"):
                path = urlparse(href).path.strip("/")
                if path and "/" not in path and path not in ("share", "intent", "home"):
                    out.setdefault("x", f"https://x.com/{path}")
    return out


TITLE_WORDS = {"chief", "officer", "head", "vp", "president", "director", "founder", "cofounder", "ceo", "cfo",
               "coo", "cto", "cro", "manager", "lead", "partner", "counsel", "general", "senior", "vice", "team",
               "board", "leadership", "our", "the", "credit", "risk", "operations", "finance", "about", "contact",
               "careers", "press", "news", "company", "investors", "advisors", "management"}
NAME_RE = re.compile(r"^[A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-zA-Z'\-]+){1,2}$")


def extract_people(html: str, icp: dict) -> list[dict]:
    """Name + title pairs from a leadership or team page, kept only if the title matches a persona.

    Team pages almost always put a short name line right next to a title line, so this walks the
    page's text lines and pairs each name-looking line with the line after (or before) it.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]
    def is_name(k):
        if not (0 <= k < len(lines)) or len(lines[k]) > 40 or not NAME_RE.match(lines[k]):
            return False
        return not (set(re.findall(r"[a-z]+", lines[k].lower())) & TITLE_WORDS)

    people, seen, used_titles = [], set(), set()
    for i, line in enumerate(lines):
        if not is_name(i) or line in seen:
            continue
        # Most pages put the title right after the name. Only look at the line before when the next
        # line is missing or is itself another name (title-above-name layouts).
        j = i + 1 if (i + 1 < len(lines) and not is_name(i + 1)) else i - 1
        if j < 0 or j in used_titles or is_name(j) or len(lines[j]) > 60:
            continue
        persona = match_persona(lines[j], icp)
        used_titles.add(j)
        if persona:
            seen.add(line)
            people.append({"name": line, "title": lines[j][:90], "persona": persona})
    return people


def match_persona(title: str, icp: dict):
    t = f" {title.lower()} "
    if len(t) > 100:
        return None
    for p in icp["personas"]:
        for needle in p["titles"]:
            n = needle.lower()
            # short tokens like "ceo" or "coo" must stand alone
            if len(n) <= 4:
                if re.search(rf"\b{re.escape(n)}\b", t):
                    return p["key"]
            elif n in t:
                return p["key"]
    return None
