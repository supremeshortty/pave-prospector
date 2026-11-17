"""Writes output/targets.csv, output/summary.md and one brief per account in output/briefs/.

Everything here goes to output/, which git ignores. `redact()` produces the public-safe version
(roles instead of names, no emails, no profile URLs) used for examples/.
"""
from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

GAP_PHRASE = {
    "approvals": "being declined",
    "amounts": "advance or credit amounts that are too small",
    "nsf_timing": "repayment pulls hitting before payday (overdrafts, NSFs, returned payments)",
    "repayment": "repayment and collections trouble",
    "model_capacity": "building credit models in-house",
}

PERSONA_ANGLE = {
    "credit_leader": "approve more of your marginal declines without moving loss rates",
    "data_science": "add near-term repayment features from bank data to your own models, backtested on your book",
    "payments_ops": "time repayment pulls to when the money is actually there, so returns and NSFs drop",
    "finance": "lift approvals and amounts while keeping the loss curve your capital partners underwrote",
    "founder": "grow approvals and amounts without adding risk",
}

SHORT_OBSERVATION = {
    "approvals": "a run of recent {name} reviews and complaints about declines",
    "amounts": "a run of recent {name} reviews asking for bigger advances or limits",
    "nsf_timing": "a run of recent {name} reviews about repayment pulls landing before payday",
    "repayment": "recent {name} complaints about repayment and collections",
    "model_capacity": "{name} is hiring for its credit team",
}

GAP_ANGLE = {
    "approvals": "approve more of your marginal declines without moving loss rates",
    "amounts": "size advances and limits to what each customer can actually repay",
    "nsf_timing": "time repayment pulls to when the money is actually there, so overdrafts and returns drop",
    "repayment": "spot which new accounts will miss their first payments before you fund them",
    "model_capacity": "ship stronger risk models faster without adding headcount",
}

GAP_SHORT_PROOF = {
    "approvals": "one lender went from low-70s to 91% new-user approvals with Pave",
    "amounts": "Super.com raised advance amounts with Pave while lowering defaults",
    "nsf_timing": "an earned wage access provider cut ACH returns from 35% to 13% with Pave",
    "repayment": "Self's SelfCash beat its first-advance repayment target on Pave's score",
    "model_capacity": "lenders use Pave's custom scores trained on their own book",
}

CTA = ("Pave can run a free backtest on a sample of your past declines and funded loans, "
       "so you see the lift on your own data before any integration. Worth 20 minutes?")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def evidence_line(acc: dict, gap: str) -> str:
    if gap == "model_capacity":
        roles = acc.get("hiring") or []
        return f"you're hiring for {roles[0]['title']}" if roles else "you're building out credit"
    ev = (acc.get("evidence") or {}).get(gap, {})
    n = ev.get("hits", 0)
    src = "customer reviews and CFPB complaints" if acc.get("cfpb_total") else "App Store reviews"
    return f"{n} of {acc['name']}'s recent {src} mention {GAP_PHRASE[gap]}"


def first_touches(acc: dict, person: dict | None, icp: dict, sender: str) -> dict:
    gap = acc.get("gap") or "approvals"
    proof = (icp["gaps"].get(gap) or icp.get("fallback_gaps", {}).get(gap, {})).get("proof", "")
    persona = (person or {}).get("persona", "credit_leader")
    first = (person or {}).get("name", "there").split()[0]
    angle = GAP_ANGLE.get(gap) or PERSONA_ANGLE.get(persona, PERSONA_ANGLE["credit_leader"])
    why = evidence_line(acc, gap)
    subject = {
        "approvals": f"{acc['name']} declines",
        "amounts": f"{acc['name']} advance sizes",
        "nsf_timing": f"{acc['name']} repayment timing",
        "repayment": f"{acc['name']} first-payment risk",
        "model_capacity": f"{acc['name']} credit team",
    }.get(gap, f"{acc['name']} underwriting")
    email = (f"Subject: {subject}\n\nHi {first},\n\n"
             f"I noticed {why}. {proof}\n\n"
             f"Pave builds near-term repayment scores from bank transactions, trained on a lender's own loans, "
             f"to help teams like yours {angle}.\n\n{CTA}\n\n{sender}")
    short = SHORT_OBSERVATION.get(gap, "{name} is growing its lending book").format(name=acc["name"])
    linkedin = (f"Hi {first}, I noticed {short}. I work with credit teams on cash-flow underwriting; "
                f"{GAP_SHORT_PROOF.get(gap, GAP_SHORT_PROOF['approvals'])}. Open to connect?")[:300]
    x_dm = (f"Hi {first}, noticed {short}. I think Pave could help you {angle}. "
            f"Free backtest on your own data if useful.")[:280]
    call = (f"\"Hi {first}, this is {sender.split(',')[0]} from Pave. I'm calling because {why}. "
            f"I think we can help you {angle}. How are you handling that today?\"")
    return {"email": email, "linkedin": linkedin, "x_dm": x_dm, "call": call}


def channels(acc: dict, person: dict) -> list[str]:
    site = acc.get("site") or {}
    out = []
    if person.get("linkedin"):
        out.append(f"LinkedIn: {person['linkedin']}")
    else:
        out.append(f"LinkedIn: search \"{person['name']} {acc['name']}\" (no profile URL found)")
    em = person.get("email") or {}
    if em.get("email"):
        out.append(f"Email: {em['email']} ({em['method']}, confidence {em['confidence']}; {em['source']})")
    if site.get("socials", {}).get("x"):
        out.append(f"X (company): {site['socials']['x']}")
    if site.get("socials", {}).get("linkedin_company"):
        out.append(f"LinkedIn (company page): {site['socials']['linkedin_company']}")
    for inbox in (site.get("emails") or {}).get("role", [])[:2]:
        out.append(f"Company inbox: {inbox}")
    for phone in site.get("phones", [])[:1]:
        out.append(f"Company phone: {phone}")
    for w in acc.get("warm_paths") or []:
        out.append(f"Warm intro: {w}")
    return out


def write_brief(acc: dict, icp: dict, out_dir: Path, sender: str) -> Path:
    gap = acc.get("gap") or ""
    gap_cfg = icp["gaps"].get(gap) or icp.get("fallback_gaps", {}).get(gap) or {}
    s = acc["score"]
    lines = [f"# {acc['name']} ({acc['domain']})", "",
             f"**Segment:** {icp['segments'][acc['segment']]['label']}  ",
             f"**Score:** {s['total']}/100 (fit {s['fit']}, evidence {s['evidence']}, timing {s['timing']}, "
             f"reach {s['reach']})  ", f"**Generated:** {date.today().isoformat()}", ""]
    if acc.get("notes"):
        lines += [f"> {acc['notes']}", ""]

    lines += ["## The gap Pave solves", ""]
    if gap:
        lines += [f"**{gap_cfg.get('label', gap)}.** {evidence_line(acc, gap)[0].upper() + evidence_line(acc, gap)[1:]}.",
                  "", f"**Matching Pave proof point:** {gap_cfg.get('proof', '')}", ""]
    else:
        lines += ["No public evidence of a gap found yet. Fit and timing only.", ""]

    ev = acc.get("evidence") or {}
    shown = [(k, e) for k, e in ev.items() if e["hits"]]
    if shown:
        lines += ["### Evidence", ""]
        for k, e in sorted(shown, key=lambda kv: -kv[1]["hits"]):
            lines.append(f"- **{icp['gaps'][k]['label']}:** {e['hits']} reviews/complaints")
            for ex in e["examples"]:
                stars = f"{ex['rating']}-star " if ex.get("rating") else ""
                src = {"app_store": "App Store review", "cfpb": "CFPB complaint"}.get(ex["source"], ex["source"])
                lines.append(f"  - \"{ex['quote']}\" ({stars}{src}, {ex['date']}) [link]({ex['url']})")
        lines.append("")
    if acc.get("app"):
        a = acc["app"]
        lines += [f"App Store: {a['name']}, {a['rating']} stars from {a['ratings']:,} ratings ({a['url']})", ""]
    if acc.get("cfpb_total"):
        lines += [f"CFPB complaints with narratives, last 12 months: {acc['cfpb_total']}", ""]

    lines += ["## Why now", ""]
    why = []
    for r in (acc.get("hiring") or [])[:3]:
        why.append(f"- Hiring: [{r['title']}]({r['url']})")
    for n in (acc.get("news") or [])[:4]:
        why.append(f"- {n['trigger'].title()} news ({n['date']}): [{n['title']}]({n['url']})")
    for f in (acc.get("filings") or [])[:3]:
        why.append(f"- SEC filing ({f['date']}): {f['meaning']} [link]({f['url']})")
    lines += (why or ["- No timing trigger found in the last 120 days."]) + [""]

    site = acc.get("site") or {}
    stack = []
    if site.get("aggregators"):
        stack.append(f"Bank data: {', '.join(site['aggregators'])} (already collecting the data Pave scores)")
    if site.get("pave_partners"):
        stack.append(f"Pave partner on site: {', '.join(site['pave_partners'])} (integration and co-sell path)")
    if site.get("partner_bank"):
        stack.append(f"Partner bank: {site['partner_bank']}")
    if stack:
        lines += ["## Stack and partners", ""] + [f"- {x}" for x in stack] + [""]

    lines += ["## Who to contact and how", ""]
    people = acc.get("people") or []
    if not people:
        lines += ["No named contacts found from public sources. Start with the company channels below, "
                  "or add a GOOGLE_CSE_KEY / APOLLO_API_KEY to find people.", ""]
        for c in channels(acc, {"name": acc["name"], "linkedin": ""})[1:]:
            lines.append(f"- {c}")
        lines.append("")
    for p in people[:4]:
        label = next(x["label"] for x in icp["personas"] if x["key"] == p["persona"])
        lines += [f"### {p['name']}, {p['title']}", f"*{label}* · found via {', '.join(p['sources'])}", ""]
        lines += [f"- {c}" for c in channels(acc, p)] + [""]

    t = first_touches(acc, people[0] if people else None, icp, sender)
    lines += ["## First touches", "", "**Email**", "", "```", t["email"], "```", "",
              "**LinkedIn connection note**", "", "```", t["linkedin"], "```", "",
              "**X DM**", "", "```", t["x_dm"], "```", "", "**Call opener**", "", t["call"], ""]
    path = out_dir / f"{slug(acc['name'])}.md"
    path.write_text("\n".join(lines))
    return path


CSV_FIELDS = ["rank", "company", "domain", "segment", "score", "fit", "evidence", "timing", "reach", "gap",
              "gap_hits", "credit_roles_open", "timing_trigger", "contact_name", "contact_title", "contact_email",
              "email_method", "email_confidence", "contact_linkedin", "warm_paths", "brief"]


def write_outputs(accounts: list[dict], icp: dict, out_dir: Path, briefs: int, sender: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "briefs").mkdir(exist_ok=True)
    for old in (out_dir / "briefs").glob("*.md"):
        old.unlink()  # keep only this run's briefs
    ranked = sorted(accounts, key=lambda a: -a["score"]["total"])
    rows = []
    for i, acc in enumerate(ranked, 1):
        p = (acc.get("people") or [{}])[0]
        em = p.get("email") or {}
        brief = ""
        if i <= briefs:
            brief = str(write_brief(acc, icp, out_dir / "briefs", sender).relative_to(out_dir))
        trig = (acc.get("news") or [{}])[0].get("trigger", "") or ("hiring" if acc.get("hiring") else "")
        rows.append({
            "rank": i, "company": acc["name"], "domain": acc["domain"], "segment": acc["segment"],
            "score": acc["score"]["total"], "fit": acc["score"]["fit"], "evidence": acc["score"]["evidence"],
            "timing": acc["score"]["timing"], "reach": acc["score"]["reach"], "gap": acc.get("gap", ""),
            "gap_hits": (acc.get("evidence") or {}).get(acc.get("gap", ""), {}).get("hits", 0),
            "credit_roles_open": len(acc.get("hiring") or []), "timing_trigger": trig,
            "contact_name": p.get("name", ""), "contact_title": p.get("title", ""),
            "contact_email": em.get("email", ""), "email_method": em.get("method", ""),
            "email_confidence": em.get("confidence", ""), "contact_linkedin": p.get("linkedin", ""),
            "warm_paths": "; ".join(acc.get("warm_paths") or []), "brief": brief,
        })
    with open(out_dir / "targets.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    (out_dir / "summary.md").write_text(summary_md(rows, icp))
    return {"ranked": ranked, "rows": rows}


def summary_md(rows: list[dict], icp: dict, top: int = 25) -> str:
    lines = [f"# Pave prospect list ({date.today().isoformat()})", "",
             "| # | Company | Segment | Score | Gap (hits) | Why now | Best contact |",
             "|---|---|---|---|---|---|---|"]
    for r in rows[:top]:
        gap = r["gap"] or "-"
        label = (icp["gaps"].get(gap) or icp.get("fallback_gaps", {}).get(gap) or {}).get("label", gap)
        contact = f"{r['contact_name']} ({r['contact_title']})" if r["contact_name"] else "-"
        lines.append(f"| {r['rank']} | {r['company']} | {icp['segments'][r['segment']]['label']} | {r['score']} | "
                     f"{label} ({r['gap_hits']}) | {r['timing_trigger'] or '-'} | {contact} |")
    return "\n".join(lines) + "\n"


# ---------- public-safe copies ----------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LI_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^\s)\]]+")


def redact(text: str, people: list[dict], icp: dict) -> str:
    """Replace names with roles, and remove personal emails and profile URLs."""
    labels = {p["key"]: p["label"] for p in icp["personas"]}
    for p in sorted(people, key=lambda x: -len(x["name"])):
        role = f"[{labels.get(p['persona'], 'Contact')}]"
        text = text.replace(p["name"], role)
        first = p["name"].split()[0]
        text = re.sub(rf"\bHi {re.escape(first)}\b", "Hi [first name]", text)
        text = re.sub(rf"\"Hi {re.escape(first)},", "\"Hi [first name],", text)
    text = LI_RE.sub("[LinkedIn profile URL]", text)
    text = EMAIL_RE.sub(lambda m: m.group(0) if m.group(0).split("@")[0] in
                        ("press", "media", "partnerships", "hello", "info", "support") else "[email]", text)
    return text
