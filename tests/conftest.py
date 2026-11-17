"""Offline test harness: a fake transport that answers from tests/fixtures instead of the network."""
from __future__ import annotations

import json as _json
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prospector.config import Account, load_icp
from prospector.http import Fetcher

FIX = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    text = (FIX / name).read_text()
    if name == "news.xml":
        text = text.replace("MOCKDATE", format_datetime(datetime.now(timezone.utc) - timedelta(days=10)))
    return text


class FakeTransport:
    """Routes a URL to a fixture by substring. Unknown URLs get a 404. Records every call."""

    def __init__(self, routes: dict | None = None):
        self.routes = routes or {}
        self.calls: list[tuple] = []

    def __call__(self, method, url, params=None, json=None, headers=None):
        self.calls.append((method, url, params, json))
        for needle, answer in self.routes.items():
            if needle in url:
                body = answer(method, url, params, json) if callable(answer) else answer
                if body is None:
                    return 404, ""
                return 200, body if isinstance(body, str) else _json.dumps(body)
        return 404, ""



SITE_ROUTES = {
    "testlend.example/robots.txt": "User-agent: *\nDisallow: /private\n",
    "testlend.example/leadership": fixture("site_team.html"),
    "testlend.example/": lambda m, u, p, j: fixture("site_home.html") if u.rstrip("/").endswith("testlend.example") else None,
}

ALL_ROUTES = {
    **SITE_ROUTES,
    "itunes.apple.com/search": fixture("itunes_search.json"),
    "customerreviews": fixture("itunes_reviews.json"),
    "_suggest_company": '["Testlend Inc.", "Testlend Holdings"]',
    "consumer-complaints/search/api/v1/": fixture("cfpb_complaints.json"),
    "boards-api.greenhouse.io/v1/boards/testlend/": fixture("greenhouse.json"),
    "news.google.com": fixture("news.xml"),
    "efts.sec.gov": {"hits": {"hits": []}},
    "dns.google": {"Status": 0, "Answer": [{"type": 15, "data": "1 aspmx.l.google.com."}]},
}


@pytest.fixture
def icp():
    return load_icp()


@pytest.fixture
def transport():
    return FakeTransport(dict(ALL_ROUTES))


@pytest.fixture
def fetcher(transport):
    return Fetcher(cache_dir=None, delay=0, transport=transport)


@pytest.fixture
def account():
    return Account(name="Testlend", domain="testlend.example", segment="cash_advance")
