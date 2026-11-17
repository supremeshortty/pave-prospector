"""Recent headlines from Google News RSS (free, no key)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

RSS = "https://news.google.com/rss/search"
CONTEXT_WORDS = ("fintech", "cash advance", "advance", "loan", "lend", "credit", "earned wage", "paycheck", "payday",
                 "banking", "bank", "neobank", "card", "app", "debt", "securitiz", "funding", "raises", "cfpb",
                 "borrow", "money", "financial", "payments")


def headlines(fetcher, name: str, context: str = "", days: int = 120) -> list[dict]:
    """Headlines about the company from the last `days`.

    `context` narrows ambiguous names (e.g. 'Grid' -> 'Grid cash advance').
    """
    q = f'"{name}" {context}'.strip() + f" when:{days}d"
    status, text = fetcher.get(RSS, params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    if status != 200 or not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        try:
            when = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            when = None
        if when and when < cutoff:
            continue
        low = title.lower()
        if not re.search(rf"\b{re.escape(name.lower())}\b", low):
            continue  # keep only headlines that actually name the company
        if len(name.split()) == 1 and not any(re.search(rf"\b{re.escape(w)}", low) for w in CONTEXT_WORDS):
            continue  # one-word names (Grid, Current, Branch) need a lending/fintech word in the headline
        out.append({"title": title, "url": link, "source": source,
                    "date": when.date().isoformat() if when else ""})
    return out[:15]
