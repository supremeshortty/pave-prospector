"""Turns raw public evidence into the signals that matter for Pave: which gap, how strong, and why now."""
from __future__ import annotations

import re
from datetime import date, timedelta

SNIPPET_CHARS = 180


def _sentence_with(text: str, needle: str) -> str:
    """The sentence around the first keyword hit, trimmed for a brief (short excerpt, not the full review)."""
    low = text.lower()
    left = r"\b" if needle[:1].isalnum() else ""
    right = r"\b" if needle.strip()[-1:].isalnum() else ""
    m = re.search(left + re.escape(needle.strip()) + right, low)
    if not m:
        return ""
    i = m.start()
    start = max(low.rfind(".", 0, i), low.rfind("!", 0, i), low.rfind("?", 0, i)) + 1
    end_candidates = [p for p in (low.find(".", i), low.find("!", i), low.find("?", i)) if p != -1]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    s = re.sub(r"\s+", " ", text[start:end]).strip()
    s = re.sub(r"X{2,}", "[redacted]", s)  # CFPB masks personal details as XXXX
    if len(s) > SNIPPET_CHARS:
        j = max(0, s.lower().find(needle) - 60)
        s = ("..." if j else "") + s[j:j + SNIPPET_CHARS].rstrip() + "..."
    return s


def _has(low: str, keyword: str) -> bool:
    """Whole-word match, so "nsf" doesn't fire inside "transfer"."""
    kw = keyword.lower().strip()
    left = r"\b" if kw[:1].isalnum() else ""
    right = r"\b" if kw[-1:].isalnum() else ""
    return re.search(left + re.escape(kw) + right, low) is not None


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def matching_sentence(text: str, gap: dict) -> str:
    """The first sentence that has a keyword, a required context word, and no excluded word."""
    for sent in SENTENCE_RE.split(text or ""):
        low = sent.lower()
        if not any(_has(low, k) for k in gap["keywords"]):
            continue
        if gap.get("requires") and not any(_has(low, k) for k in gap["requires"]):
            continue
        if any(k.lower() in low for k in gap.get("excludes", [])):
            continue
        return sent.strip()
    return ""


def _trim(sent: str) -> str:
    s = re.sub(r"\s+", " ", sent).strip()
    s = re.sub(r"X{2,}", "[redacted]", s)  # CFPB masks personal details as XXXX
    return s if len(s) <= SNIPPET_CHARS else s[:SNIPPET_CHARS].rstrip() + "..."


def gap_evidence(items: list[dict], icp: dict) -> dict:
    """Count reviews/complaints that describe each gap, judged sentence by sentence.

    Only complaints and 1-3 star reviews count: a 5-star review that mentions "approved" isn't a gap.
    """
    out = {k: {"hits": 0, "examples": []} for k in icp["gaps"]}
    for it in items:
        if it.get("rating") is not None and it["rating"] > 3:
            continue
        text = f"{it.get('title', '')}. {it.get('text', '')}"
        for key, gap in icp["gaps"].items():
            sent = matching_sentence(it.get("text", ""), gap) or matching_sentence(text, gap)
            if not sent:
                continue
            out[key]["hits"] += 1
            if len(out[key]["examples"]) < 3:
                out[key]["examples"].append({
                    "quote": _trim(sent), "source": it.get("source", ""), "date": it.get("date", ""),
                    "url": it.get("url", ""), "rating": it.get("rating"),
                })
    return out


def primary_gap(evidence: dict, icp: dict, hiring: list) -> tuple[str, float]:
    """The gap with the most weighted evidence. Falls back to model capacity when only hiring shows a need."""
    best, best_score = "", 0.0
    for key, ev in evidence.items():
        s = min(ev["hits"], 5) / 5 * icp["gaps"][key]["weight"]
        if s > best_score:
            best, best_score = key, s
    if not best and hiring:
        return "model_capacity", 0.0
    return best, best_score


def hiring_signal(roles: list[dict], icp: dict) -> list[dict]:
    pats = [p.lower() for p in icp["credit_role_patterns"]]
    return [r for r in roles if any(p in r.get("title", "").lower() for p in pats)]


def news_signal(headlines: list[dict], icp: dict) -> list[dict]:
    out = []
    for h in headlines:
        t = h["title"].lower()
        for kind, words in icp["news_triggers"].items():
            if any(w in t for w in words):
                out.append({**h, "trigger": kind})
                break
    return out


def filing_signal(filings: list[dict], days: int = 365) -> list[dict]:
    """Form D = they raised money; ABS/SF/424B = they securitize loans; 8-K = a material event."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    keep = []
    for f in filings:
        form = (f.get("form") or "").upper()
        if f.get("date", "") < cutoff:
            continue
        if form.startswith("D"):
            keep.append({**f, "meaning": "raised capital (Form D)"})
        elif form.startswith(("ABS", "SF-", "424B")):
            keep.append({**f, "meaning": "securitization or debt offering"})
        elif form.startswith("8-K"):
            keep.append({**f, "meaning": "material event (8-K)"})
    return keep[:5]


def investor_overlap(texts: list[str], icp: dict, seeded: list | None = None) -> list[str]:
    blob = " ".join(texts).lower()
    found = [inv for inv in icp.get("pave_investors", []) if inv.lower() in blob]
    for inv in seeded or []:
        if inv in icp.get("pave_investors", []) and inv not in found:
            found.append(inv)
    return found
