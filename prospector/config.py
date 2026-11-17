"""Loads config/icp.yaml, config/seeds.yaml and optional API keys from .env."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


@dataclass
class Account:
    name: str
    domain: str
    segment: str
    app: Optional[str] = None
    cfpb: Optional[str] = None
    ats: Optional[str] = None
    notes: str = ""
    investors: list = field(default_factory=list)
    warm: list = field(default_factory=list)


def load_icp(path: Optional[Path] = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "icp.yaml").read_text())


def load_accounts(path: Optional[Path] = None, segments: Optional[list] = None) -> list[Account]:
    data = yaml.safe_load((path or CONFIG_DIR / "seeds.yaml").read_text())
    accounts = []
    for row in data.get("accounts", []):
        acc = Account(**{k: v for k, v in row.items() if k in Account.__dataclass_fields__})
        if segments and acc.segment not in segments:
            continue
        accounts.append(acc)
    return accounts


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def exclusion_reason(acc: Account, icp: dict) -> Optional[str]:
    """Why this account must not be prospected, or None if it's fair game.

    Names must match exactly (after removing spaces and punctuation), so 'Self'
    excludes Self, not 'Self-Help Credit Union'.
    """
    ex = icp.get("exclude", {})
    name = _norm(acc.name)
    domain = (acc.domain or "").lower().removeprefix("www.")
    if domain in [d.lower() for d in ex.get("customer_domains", [])]:
        return "existing Pave customer"
    for kind, label in (("customers", "existing Pave customer"), ("partners", "Pave partner"),
                        ("competitors", "Pave competitor")):
        if name in {_norm(n) for n in ex.get(kind, [])}:
            return label
    return None


def load_env(path: Optional[Path] = None) -> dict:
    """Reads KEY=value lines from .env (if present) without adding a dependency."""
    env = dict(os.environ)
    p = path or ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env
