"""Polite HTTP: one shared session, a per-host rate limit, robots.txt for websites, and a disk cache."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.robotparser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

DEFAULT_DELAY = 1.0          # seconds between requests to the same host
CACHE_TTL = 3 * 24 * 3600    # reuse responses for 3 days


class Fetcher:
    """Fetches URLs once, slowly, and remembers the answer.

    `cache_dir=None` turns the cache off. Tests replace `transport` with a fake.
    """

    def __init__(self, cache_dir: Optional[Path] = None, contact: str = "", delay: float = DEFAULT_DELAY,
                 transport=None):
        contact = contact or os.environ.get("PROSPECTOR_CONTACT", "")
        ua = "pave-prospector/0.1 (public-data research tool"
        ua += f"; contact: {contact})" if contact else ")"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": ua, "Accept-Language": "en-US,en;q=0.8"})
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.transport = transport
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.log: list[str] = []

    # ---------- public helpers ----------
    def get_json(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None):
        status, text = self.get(url, params=params, headers=headers)
        if status != 200 or not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def post_json(self, url: str, body: dict, headers: Optional[dict] = None):
        status, text = self._request("POST", url, json_body=body, headers=headers)
        if status != 200 or not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def get(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
            respect_robots: bool = False) -> tuple[int, str]:
        if respect_robots and not self.allowed(url):
            self.log.append(f"robots.txt disallows {url}")
            return 0, ""
        return self._request("GET", url, params=params, headers=headers)

    def allowed(self, url: str) -> bool:
        """True if the site's robots.txt lets a generic crawler fetch this URL."""
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            status, text = self._request("GET", root + "/robots.txt")
            if status == 200 and text:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(text.splitlines())
                self._robots[root] = rp
            else:
                self._robots[root] = None  # no robots.txt: allowed
        rp = self._robots[root]
        return True if rp is None else rp.can_fetch("*", url)

    # ---------- internals ----------
    def _cache_key(self, method: str, url: str, params, body) -> str:
        raw = json.dumps([method, url, params or {}, body or {}], sort_keys=True)
        return hashlib.sha1(raw.encode()).hexdigest()

    def _request(self, method: str, url: str, params=None, json_body=None, headers=None) -> tuple[int, str]:
        key = self._cache_key(method, url, params, json_body)
        if self.cache_dir:
            path = self.cache_dir / f"{key}.json"
            if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
                cached = json.loads(path.read_text())
                return cached["status"], cached["text"]
        self._wait(url)
        try:
            if self.transport:
                status, text = self.transport(method, url, params=params, json=json_body, headers=headers)
            else:
                resp = self.session.request(method, url, params=params, json=json_body, headers=headers,
                                            timeout=20)
                status, text = resp.status_code, resp.text
        except requests.RequestException as exc:
            self.log.append(f"{method} {url} failed: {exc.__class__.__name__}")
            return 0, ""
        if status != 200:
            self.log.append(f"{method} {url} -> {status}")
        if self.cache_dir and status in (200, 404):
            (self.cache_dir / f"{key}.json").write_text(json.dumps({"status": status, "text": text}))
        return status, text

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_hit.get(host)
        if last is not None:
            gap = time.time() - last
            if gap < self.delay:
                time.sleep(self.delay - gap)
        self._last_hit[host] = time.time()
