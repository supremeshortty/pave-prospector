# Outbound playbook

How to turn the tool's output into meetings. The tool finds the account, the gap, the evidence and the people. This is what to do with them.

## The core motion

**Lead with what their customers are saying, offer a backtest, and let the numbers sell.**

Pave's real sales motion is a backtest: the lender sends a sample of past applications, declines and repayment outcomes, and Pave shows the lift on their own book. Every first touch points there. A free, no-integration backtest is a low-risk yes for a credit leader, and it turns a cold email into a technical evaluation.

## Pain hooks by segment

| Segment | Lead with | Proof point to pair it with | Who feels it most |
|---|---|---|---|
| Cash advance and earned wage access | Failed repayment pulls: NSFs, ACH returns, NACHA's return-rate thresholds (0.5% unauthorized, 3% administrative, 15% overall) | ACH returns cut from 35% to 13%; NSFs down 27% | Payments or operations lead, then Head of Credit |
| Cash advance (growth-stage) | Advance sizes and "only approved for $25" reviews | Super.com raised advance amounts while lowering defaults; another provider +74% | CEO / Head of Credit |
| Near-prime personal loans | Good applicants being declined; the marginal-decline band | About 90% of marginal declines approvable without adding risk | Head of Credit / CRO |
| Thin-file cards and credit builders | Starting limits and line increases | Approvals from the low 70s to 91% | Head of Credit, data science |
| Small-business lending | Revenue volatility that bureau data misses; renewals | Custom scores trained on their own book | Chief Credit Officer, underwriting lead |
| BNPL and lease-to-own | Real-time affordability at checkout | First-payment prediction | Head of Risk |
| Debt capital providers | Portfolio monitoring on fintech books they fund | Near-term repayment scores across the book | Portfolio manager, CRO |
| Channel partners | Pave as a module their clients already ask for | Existing Taktile, Oscilar, Alloy, LendAPI integrations | Partnerships lead |

## Multi-threading

Single-threaded deals stall in credit. For every account in the top 25, reach at least two personas:

1. **Economic buyer:** Head of Credit, CRO or Chief Credit Officer. Owns loss rates and approval targets.
2. **Champion:** the credit data scientist who would run the backtest. Wants features and lift, not a pitch.
3. **Pain owner:** at cash advance and earned wage access apps, the payments or operations lead who gets the ACH return reports.
4. **Capital view:** the CFO or capital markets lead, when the account just raised a facility or securitized. Their capital partners care about asset performance.

Message each one about their part of the same gap. The brief's "Who to contact and how" section lists who was found and every route to them.

## Sequence (12 business days, 7 touches)

| Day | Channel | Touch |
|---|---|---|
| 1 | Email | The observation + one proof point + backtest offer (the brief's draft) |
| 1 | LinkedIn | Connection request with a short note, or follow + engage if note credits are used up |
| 3 | Phone | Call opener from the brief. Leave a 20-second voicemail referencing the email |
| 4 | Email | New fact: a job posting, a filing or a headline from "Why now" |
| 6 | Second persona | Email the champion or pain owner about their side of the same gap |
| 8 | X / LinkedIn | Comment on or reply to something they posted; DM only if they engage |
| 12 | Email | Close the loop: "Should I send this to someone else on your credit team?" |

Lead with email. LinkedIn connection notes are capped on free accounts, and X works best for founders and data scientists who post publicly.

## Warm paths (check before going cold)

- **Shared investors.** The tool flags targets whose funding news names Bessemer, 8VC or Better Tomorrow Ventures. Ask for a portfolio intro first.
- **Partner co-sell.** If a target's site shows Taktile, Oscilar, LendAPI or Alloy, or its partner bank is Cross River, the partner's account team is the warmest route and the integration is already built.
- **Bank-data aggregator in place.** Plaid, MX or Finicity on their site means they already collect the data Pave scores. Say so: no new consent flow, no new vendor for the borrower to see.

## Events

Credit and fintech conferences put the buyers in one room. Check each event's speaker and sponsor list against the top 25 and book meetings before you go:

- **Fintech Meetup** (Las Vegas, usually March): built around pre-booked 15-minute meetings
- **Lend360** (usually fall): online lenders and their credit teams
- **Money20/20 USA** (Las Vegas, usually October)
- **Bank Automation Summit**, credit union and community bank events for segment 6

Verify dates on each event's site before planning.

## Content hooks

- Pave's published research and case studies (approvals, advance sizes, ACH returns). Link the one that matches the gap.
- Any CFPB or NACHA rule change affecting small-dollar repayment, earned wage access or cash advances is a reason to reach the whole cash-advance segment in one week.

## Hygiene and compliance

- Verify any email marked **guess - verify** before sending, or reach the person through LinkedIn first.
- Use a real unsubscribe line and honor opt-outs (CAN-SPAM).
- Don't paste review text into outreach. Summarize it ("a run of recent reviews about pulls landing before payday").
- Contact data lives only in `output/`, which git ignores. Run `python -m prospector check-pii` before every commit.
