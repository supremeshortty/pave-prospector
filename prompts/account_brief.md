# Prompt: turn a run into outreach-ready briefs

The tool writes briefs with rule-based drafts and no paid AI. If you use an AI assistant (for example Claude Code on your own subscription), paste this prompt with one account's entry from `output/accounts.json` and its brief from `output/briefs/` to get a sharper, more personal version.

---

You're an account executive at Pave (pavefi.com). Pave builds near-term repayment scores from bank-transaction data, trained on each lender's own loan history. Lenders use it to approve more applicants, size advances and limits, and time repayment pulls without adding risk.

Below is public research on one target lender: its scores, the gap we found and the evidence behind it, why the timing is right, and the people we identified.

Write:

1. **Two sentences on the gap.** What's going wrong for this lender, in its customers' terms, citing the strongest evidence (count plus one short quote).
2. **The angle for each contact.** One line per person on why this gap matters to their role.
3. **A first email** to the top contact. Under 110 words. Open with the observation, not with Pave. Use one proof point from the brief, word for word. End by offering a free backtest on their own declines and funded loans. No flattery, no "I hope this finds you well."
4. **A LinkedIn connection note** under 280 characters.
5. **A follow-up** for day 4 that adds one new fact (a news item, a filing or a job posting from the brief) rather than "bumping."
6. **What to verify before sending.** Any email marked "guess - verify", any person whose title came from a single source, anything older than 6 months.

Rules: use only facts in the research below. If something is missing, say so; don't fill the gap. Quote reviews or complaints only briefly.

Research:

```
[paste the account from output/accounts.json and its brief here]
```
