"""Runs the enrichment in two passes.

Pass 1 (every account, free sources only): website, App Store, CFPB, job boards, news, SEC filings.
          Gives each account a preliminary score.
Pass 2 (top `deep` accounts only): people search and email lookups, which use free-tier quotas
          (Google CSE 100/day, Hunter 25/month, Apollo/Exa credits), so they go where they matter.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from prospector import signals
from prospector.config import Account, exclusion_reason
from prospector.connectors import appstore, cfpb, edgar, email, jobs, news, people, website
from prospector.score import score

CONSUMER_SEGMENTS = {"cash_advance", "personal_loans", "cards", "bnpl", "credit_union"}
NEWS_CONTEXT = "(fintech OR lending OR loans OR credit OR \"cash advance\")"


def _first_word(name: str) -> str:
    return name.lower().replace("(", " ").split()[0]


def pass_one(acc: Account, fetcher, icp: dict, log=print) -> dict:
    row = asdict(acc)
    log(f"  website ...", end="")
    row["site"] = website.scan(fetcher, acc.domain, icp)

    items = []
    if acc.segment in CONSUMER_SEGMENTS or acc.app:
        log(" app store ...", end="")
        app = appstore.find_app(fetcher, acc.app or acc.name, acc.domain, acc.name)
        row["app"] = app
        if app:
            items += appstore.reviews(fetcher, app["app_id"], pages=5)
    if acc.segment in CONSUMER_SEGMENTS or acc.cfpb:
        log(" cfpb ...", end="")
        legal = cfpb.resolve_company(fetcher, acc.cfpb or acc.name)
        if legal:
            c = cfpb.complaints(fetcher, legal)
            row["cfpb_company"], row["cfpb_total"] = legal, c["total_with_narrative"]
            items += c["items"]
    row["evidence_items"] = len(items)
    row["evidence"] = signals.gap_evidence(items, icp)

    log(" jobs ...", end="")
    board = jobs.open_roles(fetcher, acc.domain, acc.name, acc.ats)
    row["jobs_board"] = board["board"]
    row["open_roles"] = len(board["roles"])
    row["hiring"] = signals.hiring_signal(board["roles"], icp)

    log(" news ...", end="")
    heads = news.headlines(fetcher, acc.name.split(" (")[0], NEWS_CONTEXT, days=icp.get("news_days", 120))
    row["news"] = signals.news_signal(heads, icp)

    log(" sec ...", end="")
    fw = _first_word(acc.name)
    raw = [f for f in edgar.filings(fetcher, acc.name.split(" (")[0]) if fw in f["filer"].lower()]
    row["filings"] = signals.filing_signal(raw)

    row["gap"], _ = signals.primary_gap(row["evidence"], icp, row["hiring"])
    row["warm_paths"] = warm_paths(row, heads, icp)
    row["people"] = people.merge(row["site"]["people"], icp=icp)
    row["score"] = score(row, icp)
    log(f" done ({row['score']['total']})")
    return row


def warm_paths(row: dict, headlines: list, icp: dict) -> list[str]:
    out = list(row.get("warm") or [])
    for inv in signals.investor_overlap([h["title"] for h in headlines], icp, row.get("investors")):
        out.append(f"Shared investor with Pave: {inv}")
    for partner in (row.get("site") or {}).get("pave_partners", []):
        out.append(f"Partner co-sell: {partner} is a Pave partner and appears on their site")
    bank = (row.get("site") or {}).get("partner_bank", "")
    if "cross river" in bank.lower():
        out.append("Partner bank: Cross River Bank is a Pave partner")
    return out


def pass_two(row: dict, fetcher, icp: dict, env: dict, budget: email.Budget, log=print) -> dict:
    name = row["name"].split(" (")[0]
    log(f"  people ...", end="")
    found = [row["site"]["people"]]
    for f in row.get("filings") or []:
        if f["meaning"].startswith("raised capital"):
            found.append(people.form_d_people(fetcher, f["url"], icp))
    found.append(people.linkedin_via_cse(fetcher, name, icp, env))
    found.append(people.apollo_people(fetcher, row["domain"], icp, env))
    found.append(people.exa_people(fetcher, name, icp, env))
    row["people"] = people.merge(*found, icp=icp)

    log(" email ...", end="")
    row["mail"] = email.mail_domain_ok(fetcher, row["domain"])
    pattern = email.pattern_from_examples(row["site"]["emails"]["personal"], row["people"])
    for p in row["people"][:2]:
        p["email"] = email.find_email(fetcher, p, row["domain"], row["site"], env, budget, pattern)
        if p["email"]["method"] == "guess" and not row["mail"]["accepts_mail"]:
            p["email"]["confidence"] = "guess - domain shows no mail server, verify"
    row["score"] = score(row, icp)
    log(f" done ({row['score']['total']})")
    return row


def run(accounts: list[Account], fetcher, icp: dict, env: dict, deep: int = 15, log=print) -> dict:
    kept, skipped = [], []
    for acc in accounts:
        why = exclusion_reason(acc, icp)
        (skipped if why else kept).append((acc, why))
    for acc, why in skipped:
        log(f"skip {acc.name}: {why}")

    rows = []
    for i, (acc, _) in enumerate(kept, 1):
        log(f"[{i}/{len(kept)}] {acc.name}")
        rows.append(pass_one(acc, fetcher, icp, log))

    rows.sort(key=lambda r: -r["score"]["total"])
    budget = email.Budget(env)
    for row in rows[:deep]:
        log(f"[deep] {row['name']}")
        pass_two(row, fetcher, icp, env, budget, log)
    return {"rows": rows, "skipped": [(a.name, w) for a, w in skipped], "fetch_log": fetcher.log}


def save(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, default=str))
