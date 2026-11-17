# Pave's ideal customer profile

Research notes behind the prospecting tool. Everything here comes from public sources, checked November 2026: pavefi.com (home, case studies, partners, blog) and Pave's Account Executive job posting.

## What Pave sells

Pave calls itself "the AI infrastructure for credit risk teams." Its near-term risk scores combine bank-transaction (cashflow) data, application data, credit bureau data and loan performance to predict whether a borrower makes their next payments. Its main products:

- **Cashflow Scores.** Built for a specific credit product: cash advances, small-dollar loans, personal loans, credit cards and charge cards. Custom versions are fine-tuned on the lender's own book.
- **Cashflow Attributes.** Thousands of pre-built features (income stability, affordability, balances, willingness to pay) that a lender drops into its own model.
- **Cashflow Analytics** through an API or Snowflake data sharing.
- **Underwriting and collections APIs.** Lenders send decisions and repayment outcomes back, which keeps improving the scores.
- **AI agents** that automate the credit model lifecycle.

Scale, per the job posting: nearly 2 billion underwriting events a year across 30+ customers. Pave is backed by Better Tomorrow Ventures, Bessemer and 8VC.

## Who already buys

**Named customers:** SoFi, Happy Money, Clair, Self (SelfCash), Super.com, True Financial and Ualett.

**Logos shown under "Customers and Trusted Partners":** FloatMe, ATM.com, Fizz, Ava, Atlas, Yendo, Arro, Lenme, Bloom Credit, GrailPay.

**Partners and integrations:**
- Decisioning: Taktile, Oscilar, LendAPI, Alloy
- Bank and data: Cross River Bank, Snowflake, Spinwheel, Method
- Bank-data aggregators: Plaid, MX, Finicity, Quiltt

All of these are excluded from the target list (see `config/icp.yaml`).

## What the customers have in common

1. **US, digital-first lenders** reaching borrowers through an app.
2. **Thin-file and near-prime borrowers**, the people FICO under-serves: gig workers, young adults, people rebuilding credit.
3. **Short-duration, high-frequency credit.** Advances, small-dollar loans and new card lines, where the first one to four payments decide whether a customer is profitable.
4. **They already collect bank data** through Plaid, MX or Finicity. Pave turns data they already have into a score, with no new consent flow for the borrower.
5. **An in-house credit or risk team** that owns a proprietary model. Pave adds lift to that model; it does not replace it.
6. **Growth funded by others.** Partner banks (Cross River) and debt facilities or loan buyers who want consistent asset performance.

## Ideal customer types, in priority order

| # | Segment | Examples of current customers | The pain Pave solves |
|---|---|---|---|
| 1 | Cash advance and earned wage access apps | Super.com, FloatMe, True, SelfCash, Ualett, Clair | Approval rates, advance sizes, failed ACH pulls (NACHA return thresholds), timing repayment to payday |
| 2 | Near-prime personal installment lenders | Happy Money, SoFi, Lenme | Approving marginal declines without adding risk; first four payments |
| 3 | Credit cards, charge cards and credit builders for thin files | Atlas, Yendo, Arro, Fizz, Ava | Setting and raising limits from income and affordability |
| 4 | Small-business lenders | (SMB scores, Taktile partnership) | Merchant cash advance, working capital, equipment, lines of credit, fleet cards |
| 5 | Buy-now-pay-later and lease-to-own | (named on Pave's consumer page) | Real-time repayment ability on short-term credit |
| 6 | Credit unions and community banks | (earlier Pave credit-union page) | Serving thin-file members safely |
| 7 | Debt capital providers | (named on Pave's site) | Portfolio risk on fintech loans they fund |
| 8 | Channel partners | Taktile, Oscilar, Cross River | Decisioning platforms and partner banks that can resell or co-sell |

## Who buys, and what each one cares about

| Persona | Role in the deal | What they care about |
|---|---|---|
| Head of Credit, Chief Risk Officer, VP Risk | Economic and technical buyer | Loss rates, approval rates, model lift, regulatory comfort |
| Credit data science or risk analytics lead | Champion: runs the backtest | Lift over their current model, data quality, how easy it is to integrate |
| Payments or operations lead (cash advance and earned wage access) | Pain owner | ACH return rate, NACHA thresholds, retry costs |
| CFO, capital markets | Cares about funding | Performance their debt facility or loan buyers will see |
| CEO or founder (smaller fintechs) | Final decision | Growth without blowing up losses |

## Proof points to use in outreach

From Pave's case studies, based on customer backtests and live use:

- A lender built a score on its own book and took new-user approvals **from the low 70s to 91%**, while repayment barely moved.
- **Super.com raised advance amounts** while lowering defaults; another provider raised advance amounts **74%**.
- **NSFs down 27%** at a leading small-dollar lender, by predicting income timing.
- An earned wage access provider **cut ACH returns from 35% to 13%**, back under the NACHA threshold.
- A personal lender could approve **about 90% of its marginal declines** without adding risk.
- Self's SelfCash beat its first-advance repayment target on Pave's Cash Advance Score.

## Competitors (excluded from targets)

Plaid (LendScore, Consumer Report), Nova Credit (Cash Atlas), Prism Data, Experian, Equifax, TransUnion, FICO (UltraFICO), Carrington Labs, Zest AI, Heron Data, Ocrolus, Inscribe, Argyle and Pinwheel. Some of these also sell bank data, so a target that uses one of them is still a target; we just don't prospect the vendors themselves.

## Where a fresh account list comes from

- App Store categories and search for cash advance, earned wage access, credit builder and loan apps (scale = number of ratings)
- CFPB complaint database: who gets complaints about advances, loans and cards
- Ecosystem pages: Plaid, MX, Taktile, Oscilar, Alloy and partner banks' fintech programs
- Conference speaker and sponsor lists: Fintech Meetup, Money20/20, Lend360, Bank Automation Summit
- Funding news: equity rounds, credit facilities, forward-flow deals and securitizations
