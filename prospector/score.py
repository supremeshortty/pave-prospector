"""Scores an enriched account out of 100 using the weights in config/icp.yaml.

fit (40)      how closely it matches Pave's current customers
evidence (30) how much public evidence shows the gap Pave solves
timing (20)   reasons to reach out now
reach (10)    whether we found the right person and a way to contact them
"""
from __future__ import annotations


def fit_score(acc: dict, icp: dict) -> float:
    w = icp["score_weights"]["fit"]
    seg = icp["segments"].get(acc["segment"], {"fit": 10})
    pts = seg["fit"]
    bonus = icp["fit_bonus"]
    site = acc.get("site") or {}
    if site.get("aggregators"):
        pts += bonus["uses_bank_data_aggregator"]
    if site.get("pave_partners"):
        pts += bonus["uses_pave_partner"]
    if acc.get("hiring"):
        pts += bonus["credit_team_hiring"]
    return min(pts, w)


def evidence_score(acc: dict, icp: dict) -> float:
    """Each gap saturates at 5 matching reviews/complaints; strongest gaps count most."""
    w = icp["score_weights"]["evidence"]
    ev = acc.get("evidence") or {}
    total_weight = sum(g["weight"] for g in icp["gaps"].values())
    raw = sum(min(ev.get(k, {}).get("hits", 0), 5) / 5 * g["weight"] for k, g in icp["gaps"].items())
    # Any one well-evidenced gap is enough to sell on, so scale against the top two gaps, not all four.
    top_two = sum(sorted((g["weight"] for g in icp["gaps"].values()), reverse=True)[:2])
    return round(min(raw / top_two, 1.0) * w, 1) if total_weight else 0.0


def timing_score(acc: dict, icp: dict) -> float:
    w = icp["score_weights"]["timing"]
    pts = 0
    if acc.get("hiring"):
        pts += 8
    kinds = {n["trigger"] for n in acc.get("news") or []}
    pts += 8 if "capital" in kinds else 6 if "funding" in kinds else 0
    pts += 4 if "launch" in kinds else 0
    pts += 4 if "pressure" in kinds else 0
    if acc.get("filings"):
        pts += 4
    return min(pts, w)


def reach_score(acc: dict, icp: dict) -> float:
    w = icp["score_weights"]["reach"]
    people = acc.get("people") or []
    if not people:
        return 1 if (acc.get("site") or {}).get("emails", {}).get("role") else 0
    top = people[0]
    pts = 4 if top["persona"] == "credit_leader" else 2
    method = (top.get("email") or {}).get("method")
    pts += 3 if method in ("published", "apollo", "hunter", "exa") else 1 if method == "guess" else 0
    pts += 2 if top.get("linkedin") else 0
    pts += 1 if acc.get("warm_paths") else 0
    return min(pts, w)


def score(acc: dict, icp: dict) -> dict:
    parts = {
        "fit": fit_score(acc, icp),
        "evidence": evidence_score(acc, icp),
        "timing": timing_score(acc, icp),
        "reach": reach_score(acc, icp),
    }
    parts["total"] = round(sum(parts.values()), 1)
    return parts
