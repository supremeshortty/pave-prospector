"""Command line.

  python -m prospector doctor                       check that every free data source is reachable
  python -m prospector run                          score every seed account, write output/
  python -m prospector run --segments cash_advance --limit 10 --briefs 5
  python -m prospector sample "Dave"                write a redacted public example from the last run
  python -m prospector check-pii                    scan files tracked by git for emails, phones, profile URLs
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from prospector import pipeline, report
from prospector.config import ROOT, load_accounts, load_env, load_icp
from prospector.http import Fetcher


def _fetcher(env: dict, no_cache: bool) -> Fetcher:
    return Fetcher(cache_dir=None if no_cache else ROOT / "output" / ".cache",
                   contact=env.get("PROSPECTOR_CONTACT", ""))


def cmd_run(args) -> int:
    env, icp = load_env(), load_icp()
    segments = [s.strip() for s in args.segments.split(",")] if args.segments else None
    accounts = load_accounts(segments=segments)
    if args.only:
        wanted = {w.strip().lower() for w in args.only.split(",")}
        accounts = [a for a in accounts if a.name.lower() in wanted or a.domain in wanted]
    if args.limit:
        accounts = accounts[: args.limit]
    if not env.get("PROSPECTOR_CONTACT"):
        print("note: set PROSPECTOR_CONTACT in .env (an email); the SEC asks every client to identify itself.")
    keys = [k for k in ("GOOGLE_CSE_KEY", "APOLLO_API_KEY", "HUNTER_API_KEY", "EXA_API_KEY") if env.get(k)]
    print(f"{len(accounts)} accounts | optional keys: {', '.join(keys) or 'none (free public sources only)'}")

    result = pipeline.run(accounts, _fetcher(env, args.no_cache), icp, env, deep=args.deep,
                          log=lambda *a, **k: print(*a, **k, flush=True))
    out = ROOT / args.out
    pipeline.save(result["rows"], out / "accounts.json")
    sender = env.get("PROSPECTOR_SENDER", "[Your name], Pave")
    written = report.write_outputs(result["rows"], icp, out, briefs=args.briefs, sender=sender)
    print(f"\nWrote {out/'targets.csv'}, {out/'summary.md'} and {min(args.briefs, len(written['rows']))} briefs.")
    blocked = [line for line in result["fetch_log"] if "failed" in line or "-> 403" in line or "-> 429" in line]
    if blocked:
        print(f"{len(blocked)} requests failed or were refused; first few:")
        for line in blocked[:5]:
            print("  " + line)
    print("\n" + (out / "summary.md").read_text())
    return 0


DOCTOR_CHECKS = [
    ("App Store search", "https://itunes.apple.com/search", {"term": "dave", "entity": "software", "limit": 1}),
    ("CFPB complaints", "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
                        "_suggest_company", {"text": "dave"}),
    ("SEC EDGAR search", "https://efts.sec.gov/LATEST/search-index", {"q": '"MoneyLion"', "forms": "D"}),
    ("Google News RSS", "https://news.google.com/rss/search", {"q": "fintech", "hl": "en-US", "gl": "US",
                                                               "ceid": "US:en"}),
    ("Greenhouse jobs", "https://boards-api.greenhouse.io/v1/boards/dave/jobs", None),
    ("Public DNS (MX check)", "https://dns.google/resolve", {"name": "dave.com", "type": "MX"}),
]


def cmd_doctor(args) -> int:
    env = load_env()
    f = Fetcher(cache_dir=None, contact=env.get("PROSPECTOR_CONTACT", ""), delay=0)
    bad = 0
    for label, url, params in DOCTOR_CHECKS:
        status, text = f.get(url, params=params, headers={"Accept": "application/json"} if "RSS" not in label else None)
        # A 404 from a job board still proves the board API is reachable (that company just isn't on it).
        ok = (status == 200 and bool(text)) or (status == 404 and "jobs" in label.lower())
        note = ""
        if ok and status == 200 and "RSS" not in label:
            try:
                json.loads(text)
            except ValueError:
                ok, note = False, "  (got a web page instead of data)"
                if "CFPB" in label:
                    ok, note = True, "  (no data: CFPB stopped publishing complaint text in Aug 2026; skipped)"
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {label:24} {status or 'no response'}{note}")
    for k in ("PROSPECTOR_CONTACT", "GOOGLE_CSE_KEY", "GOOGLE_CSE_ID", "APOLLO_API_KEY", "HUNTER_API_KEY",
              "EXA_API_KEY"):
        print(f"{'set ' if env.get(k) else '--  '} {k}")
    if bad:
        print("\nSome sources failed. On a work or VPN network, try again from a home connection.")
    return 1 if bad else 0


def cmd_sample(args) -> int:
    icp = load_icp()
    rows = json.loads((ROOT / args.out / "accounts.json").read_text())
    match = [r for r in rows if r["name"].lower() == args.company.lower()]
    if not match:
        print(f"{args.company} isn't in the last run. Try one of: {', '.join(r['name'] for r in rows[:10])}")
        return 1
    row = match[0]
    brief = (ROOT / args.out / "briefs" / f"{report.slug(row['name'])}.md")
    if not brief.exists():
        report.write_brief(row, icp, ROOT / args.out / "briefs", "[Your name], Pave")
    text = report.redact(brief.read_text(), row.get("people") or [], icp)
    dest = ROOT / "examples" / "sample_report_redacted.md"
    dest.parent.mkdir(exist_ok=True)
    note = ("<!-- Generated by `python -m prospector sample`. Names, personal emails and profile URLs are "
            "replaced with roles. Run the tool to see the full version locally. -->\n\n")
    dest.write_text(note + text)
    print(f"Wrote {dest}. Check it with: python -m prospector check-pii")
    return 0


PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "linkedin profile": re.compile(r"linkedin\.com/in/[A-Za-z0-9\-_%]+"),
    "phone": re.compile(r"(?:\+1[\s.-]?)?\(?\b[2-9]\d{2}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
}
PII_ALLOW = re.compile(r"(example\.(com|org)|\.example\b|555[\s.-]01\d\d|@domain|\{first\}|\{f\}|first\.last@|press@|partnerships@|"
                       r"you@|noreply@|hello@|info@|support@)", re.I)


def cmd_check_pii(args) -> int:
    try:
        files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    hits = []
    for rel in files:
        p = ROOT / rel
        if p.suffix in (".png", ".jpg", ".gif", ".pyc") or not p.exists():
            continue
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            for kind, rx in PII_PATTERNS.items():
                for m in rx.finditer(line):
                    if not PII_ALLOW.search(m.group(0)) and not PII_ALLOW.search(line):
                        hits.append(f"{rel}:{n}: {kind}: {m.group(0)}")
    if hits:
        print("Possible personal data in files that would be committed:")
        print("\n".join(hits))
        return 1
    print(f"Clean: {len(files)} files checked, no emails, phone numbers or profile URLs.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prospector", description="Find lenders with a gap Pave solves.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="enrich and score accounts")
    r.add_argument("--segments", help="comma list, e.g. cash_advance,personal_loans")
    r.add_argument("--only", help="comma list of company names or domains")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--deep", type=int, default=15, help="accounts that get people and email lookups")
    r.add_argument("--briefs", type=int, default=10)
    r.add_argument("--out", default="output")
    r.add_argument("--no-cache", action="store_true")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("doctor", help="check that each data source is reachable")
    d.set_defaults(func=cmd_doctor)

    s = sub.add_parser("sample", help="write a redacted public example from the last run")
    s.add_argument("company")
    s.add_argument("--out", default="output")
    s.set_defaults(func=cmd_sample)

    c = sub.add_parser("check-pii", help="scan files git would commit for personal data")
    c.set_defaults(func=cmd_check_pii)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
