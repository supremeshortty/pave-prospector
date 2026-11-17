# pave-prospector

Finds lenders that have a problem Pave solves, shows the public evidence, and names who to contact and every way to reach them.

Built by Nathan Shortt as a working start on the first 90 days of Pave's founding Account Executive role: a target account list and an outbound motion that uses automation to research accounts and personalize outreach. It runs on free public data, and costs nothing to run.

## What you get

For each target account:

- **The gap.** Which Pave proof point fits, backed by evidence: the last 12 months of App Store reviews from their own customers about declines, small advances, or repayment pulls hitting before payday.
- **Why now.** Open credit-risk roles, recent funding or credit facilities, product launches, and SEC filings.
- **Who to contact.** The Head of Credit, the credit data scientist, the payments lead and the CFO, from the company's own leadership pages, SEC filings and (optionally) search.
- **Every way in.** LinkedIn, work email (with how it was found and how sure we are), company X and inboxes, phone, shared investors with Pave, and partner co-sell routes.
- **First touches.** An email, LinkedIn note, X DM and call opener built from that account's evidence.

Output is a ranked `output/targets.csv`, a `summary.md`, and one brief per top account, all written to `output/` on your machine. No prospect data is stored in this repo.

## How it works

```
config/seeds.yaml (about 90 lenders across 8 segments)
        │
        ├─ drop current Pave customers, partners and competitors (config/icp.yaml)
        │
  Pass 1, every account, free public sources
        ├─ company website ─ bank-data aggregator, Pave partners, partner bank, leaders, contact routes
        ├─ App Store ─────── recent 1-3 star reviews
        ├─ CFPB ─────────── complaint narratives (optional; see note below)
        ├─ job boards ────── open credit and risk roles (Greenhouse, Lever, Ashby)
        ├─ Google News ───── funding, credit facilities, launches, regulatory pressure
        └─ SEC EDGAR ─────── Form D raises, securitizations, 8-Ks
        │
        └─ score: fit 40 + evidence 30 + timing 20 + reach 10
        │
  Pass 2, top accounts only (protects free-tier quotas)
        ├─ people: leadership pages, Form D officers, optional Google / Apollo / Exa search
        └─ email:  published on their site → Apollo → Hunter → Exa → labeled pattern guess (last resort)
        │
        └─ output/targets.csv, summary.md, briefs/<company>.md
```

**Finding the gap.** Each gap in `config/icp.yaml` has keywords and the Pave proof point that answers it:

| Gap | Customers say things like | Pave proof point |
|---|---|---|
| Good applicants declined | "keeps denying me", "not eligible" | Approvals from the low 70s to 91% |
| Advances or limits too small | "only approved for $25", "raise my limit" | Super.com raised advance amounts; another provider +74% |
| Pulls before payday | "overdraft", "insufficient funds", "before payday" | ACH returns 35% → 13%; NSFs down 27% |
| Repayment trouble | "late fee", "collections" | First one to four repayments predicted |

Only 1-3 star reviews and complaints count. When a company has no public complaints but is hiring a credit team, the gap becomes "building credit models in-house."

**Scoring** (all weights in `config/icp.yaml`):
- **Fit (40):** segment priority, plus points for Plaid/MX/Finicity on their site, a Pave partner on their site, or an in-house credit team.
- **Evidence (30):** matching reviews and complaints, saturating at 5 per gap.
- **Timing (20):** credit hiring, capital or funding news, launches, regulatory pressure, recent filings.
- **Reach (10):** a named credit leader, a found email, a LinkedIn profile, a warm path.

## Run it

Needs Python 3.9+.

```bash
git clone https://github.com/supremeshortty/pave-prospector.git
cd pave-prospector
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your email as PROSPECTOR_CONTACT; other keys optional

python -m prospector doctor   # checks each data source is reachable
python -m prospector run      # about 30 minutes for the full list (polite rate limits)
```

Smaller runs:

```bash
python -m prospector run --segments cash_advance,personal_loans --briefs 5
python -m prospector run --only "Dave,Brigit,Klover"
```

Optional free-tier keys in `.env` add people and emails: Google Programmable Search (100 queries/day), Hunter (25/month), and your own Apollo or Exa account. Each has a per-run cap so one run can't spend a month of credits.

Tests run offline against saved sample data: `pytest`.

**A note on CFPB data.** The CFPB announced in August 2026 that it would stop publishing consumer complaint narratives, and its search API now returns a web page instead of data. The connector is still here and turns itself back on if the API returns, but today the evidence comes from App Store reviews. For lenders without a consumer app, the brief leans on hiring, funding and filings instead.

## Privacy and data rules

- **No prospect data in this repo.** Results, names, emails and cached responses go to `output/`, which git ignores. `python -m prospector check-pii` scans everything git would commit and fails on any email, phone number or profile URL.
- **LinkedIn is never scraped.** Profile URLs come only from search results.
- **No mailbox probing.** Emails come from public pages or the user's own enrichment accounts. A pattern guess is used only when nothing else finds an address, and it's labeled "guess - verify."
- **Polite fetching.** robots.txt is respected on company sites, requests are rate-limited per host, and responses are cached for 3 days.

## Repo layout

| Path | What's there |
|---|---|
| [ICP.md](ICP.md) | Research on Pave's customers, segments, buyers and proof points |
| [PLAYBOOK.md](PLAYBOOK.md) | Outreach strategy: pain hooks by segment, multi-threading, sequence, events, warm paths |
| `config/icp.yaml` | Segments, gaps, keywords, scoring weights, personas, exclusions |
| `config/seeds.yaml` | Starting account list |
| `prospector/connectors/` | One module per data source |
| `prospector/signals.py`, `score.py`, `report.py` | Evidence → gap → score → brief |
| `prompts/account_brief.md` | Optional prompt to polish a brief with an AI assistant |
| `tests/` | Offline tests with fixtures |

## Extending it

- **Add accounts:** append to `config/seeds.yaml` (name, domain, segment).
- **Tune the model:** change weights, keywords or proof points in `config/icp.yaml`. No code changes needed.
- **Add a source:** write a connector that takes the shared `Fetcher` and returns plain dicts, then call it in `prospector/pipeline.py`.
