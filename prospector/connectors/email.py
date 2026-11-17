"""Work email for a named person, found in this order (first hit wins):

  1. published  - the address appears on the company's own website
  2. apollo     - Apollo people/match        (optional key: APOLLO_API_KEY; uses Apollo credits)
  3. hunter     - Hunter email-finder        (optional key: HUNTER_API_KEY; free tier = 25 searches/month)
  4. exa        - a public page Exa finds that prints the address (optional key: EXA_API_KEY)
  5. guess      - the most likely pattern, labeled "guess - verify". Only used when 1-4 found nothing.

No mailbox is ever probed (no SMTP RCPT checks). The only network check is whether the domain accepts mail
at all, via a public DNS-over-HTTPS MX lookup.
"""
from __future__ import annotations

import re
import unicodedata

APOLLO_MATCH = "https://api.apollo.io/api/v1/people/match"
HUNTER_FINDER = "https://api.hunter.io/v2/email-finder"
EXA_URL = "https://api.exa.ai/search"
DOH = "https://dns.google/resolve"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class Budget:
    """Caps calls to tools that spend credits, so one run can't burn a month of free searches."""

    def __init__(self, env: dict):
        self.left = {
            "apollo": int(env.get("APOLLO_MAX_CALLS", 10)),
            "hunter": int(env.get("HUNTER_MAX_CALLS", 10)),
            "exa": int(env.get("EXA_MAX_CALLS", 20)),
        }

    def take(self, tool: str) -> bool:
        if self.left.get(tool, 0) <= 0:
            return False
        self.left[tool] -= 1
        return True


def split_name(full: str) -> tuple[str, str]:
    clean = unicodedata.normalize("NFKD", full).encode("ascii", "ignore").decode()
    parts = [re.sub(r"[^a-z\-']", "", p.lower()) for p in clean.split()]
    parts = [p for p in parts if p and p not in ("jr", "sr", "ii", "iii", "phd", "md", "cfa")]
    parts = [p for p in parts if len(p) > 1] or parts  # drop middle initials
    if not parts:
        return "", ""
    return parts[0].replace("'", ""), parts[-1].replace("'", "").replace("-", "") if len(parts) > 1 else ""


def mail_domain_ok(fetcher, domain: str) -> dict:
    """Does the domain publish MX records, and who hosts its mail? (Public DNS only.)"""
    data = fetcher.get_json(DOH, params={"name": domain, "type": "MX"}) or {}
    answers = [a.get("data", "") for a in data.get("Answer", []) if a.get("type") == 15]
    host = " ".join(answers).lower()
    provider = ("Google Workspace" if "google" in host else "Microsoft 365" if "outlook" in host
                else "other" if answers else "")
    return {"accepts_mail": bool(answers), "provider": provider}


def pattern_from_examples(emails: list[str], people: list[dict]) -> str:
    """Learn the company's pattern from any published personal address whose owner we can name."""
    for e in emails:
        local = e.split("@")[0].lower()
        for p in people:
            first, last = split_name(p["name"])
            if not first or not last:
                continue
            for pattern, value in candidates(first, last).items():
                if local == value:
                    return pattern
    return ""


def candidates(first: str, last: str) -> dict:
    """Common corporate patterns, most common first."""
    if not last:
        return {"{first}": first}
    return {
        "{first}": first,
        "{first}.{last}": f"{first}.{last}",
        "{f}{last}": f"{first[0]}{last}",
        "{first}{last}": f"{first}{last}",
        "{first}{l}": f"{first}{last[0]}",
        "{first}_{last}": f"{first}_{last}",
        "{f}.{last}": f"{first[0]}.{last}",
    }


def find_email(fetcher, person: dict, domain: str, site: dict, env: dict, budget: Budget,
               known_pattern: str = "") -> dict:
    """Best available email for one person, with how it was found and how sure we are."""
    first, last = split_name(person["name"])
    root = domain.lower().removeprefix("www.")

    # 1. published on the company's own site
    for e in site.get("emails", {}).get("personal", []):
        local = e.split("@")[0]
        if first and last and (last in local and (first in local or local.startswith(first[0]))):
            return {"email": e, "method": "published", "confidence": "high", "source": "company website"}

    # 2. Apollo
    if env.get("APOLLO_API_KEY") and budget.take("apollo"):
        body = {"first_name": person.get("first_name") or first.title(),
                "last_name": person.get("last_name") or last.title(), "domain": root,
                "reveal_personal_emails": False}
        if person.get("apollo_id"):
            body = {"id": person["apollo_id"], "reveal_personal_emails": False}
        data = fetcher.post_json(APOLLO_MATCH, body, headers={"X-Api-Key": env["APOLLO_API_KEY"],
                                                               "Content-Type": "application/json"})
        p = (data or {}).get("person") or {}
        email = p.get("email") or ""
        if email and "email_not_unlocked" not in email and email.lower().endswith(root):
            status = (p.get("email_status") or "").lower()
            return {"email": email.lower(), "method": "apollo",
                    "confidence": "high" if status == "verified" else "medium", "source": "Apollo"}

    # 3. Hunter
    if env.get("HUNTER_API_KEY") and first and last and budget.take("hunter"):
        data = fetcher.get_json(HUNTER_FINDER, params={"domain": root, "first_name": first, "last_name": last,
                                                       "api_key": env["HUNTER_API_KEY"]})
        d = (data or {}).get("data") or {}
        if d.get("email"):
            score = d.get("score") or 0
            return {"email": d["email"].lower(), "method": "hunter",
                    "confidence": "high" if score >= 90 else "medium" if score >= 70 else "low",
                    "source": "Hunter" + (f" ({len(d.get('sources') or [])} public sources)"
                                          if d.get("sources") else "")}

    # 4. Exa: a public page that prints this person's address
    if env.get("EXA_API_KEY") and first and last and budget.take("exa"):
        body = {"query": f'"{person["name"]}" email "@{root}"', "numResults": 5,
                "contents": {"text": {"maxCharacters": 4000}}}
        data = fetcher.post_json(EXA_URL, body, headers={"x-api-key": env["EXA_API_KEY"],
                                                         "Content-Type": "application/json"})
        for r in (data or {}).get("results", []):
            for e in EMAIL_RE.findall(r.get("text") or ""):
                e = e.lower()
                local = e.split("@")[0]
                if e.endswith("@" + root) and last in local:
                    return {"email": e, "method": "exa", "confidence": "medium",
                            "source": r.get("url", "public page via Exa")}

    # 5. Last resort: labeled guess
    if not first:
        return {"email": "", "method": "none", "confidence": "", "source": ""}
    options = candidates(first, last)
    pattern = known_pattern if known_pattern in options else ("{first}.{last}" if last else "{first}")
    guess = f"{options[pattern]}@{root}"
    alts = [f"{v}@{root}" for k, v in options.items() if k != pattern][:2]
    return {"email": guess, "method": "guess", "confidence": "guess - verify",
            "source": ("pattern seen on company site" if known_pattern else "common pattern") +
                      "; also try " + ", ".join(alts)}
