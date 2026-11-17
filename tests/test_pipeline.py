import csv

from prospector import pipeline, report, signals
from prospector.config import Account, exclusion_reason, load_accounts
from prospector.connectors import appstore, cfpb
from prospector.score import score


def test_gap_evidence_ignores_happy_reviews_and_counts_each_gap(fetcher, icp):
    items = appstore.reviews(fetcher, 222, pages=1) + cfpb.complaints(fetcher, "Testlend Inc.")["items"]
    ev = signals.gap_evidence(items, icp)
    assert ev["approvals"]["hits"] == 2      # "denying" review + "not eligible" complaint; 5-star "never denied" ignored
    assert ev["amounts"]["hits"] == 1
    assert ev["nsf_timing"]["hits"] == 2
    q = ev["nsf_timing"]["examples"][0]["quote"]
    assert "before payday" in q and len(q) <= 190
    assert ev["repayment"]["hits"] == 0


def test_cfpb_masking_is_redacted_in_quotes(fetcher, icp):
    ev = signals.gap_evidence(cfpb.complaints(fetcher, "Testlend Inc.")["items"], icp)
    assert "XX" not in ev["nsf_timing"]["examples"][0]["quote"]


def test_exclusions_use_exact_names_and_domains(icp):
    assert exclusion_reason(Account("Self", "self.inc", "cards"), icp) == "existing Pave customer"
    assert exclusion_reason(Account("Self-Help Credit Union", "self-help.org", "credit_union"), icp) is None
    assert exclusion_reason(Account("Anything", "sofi.com", "personal_loans"), icp) == "existing Pave customer"
    assert exclusion_reason(Account("Taktile", "taktile.com", "channel"), icp) == "Pave partner"


def test_seed_list_has_no_current_customers(icp):
    for acc in load_accounts():
        assert exclusion_reason(acc, icp) is None, acc.name
        assert acc.segment in icp["segments"], acc.name


def test_scores_stay_in_bounds(icp):
    empty = {"segment": "channel"}
    s = score(empty, icp)
    assert 0 <= s["total"] <= 100
    maxed = {"segment": "cash_advance", "site": {"aggregators": ["Plaid"], "pave_partners": ["Taktile"]},
             "hiring": [{"title": "Head of Credit"}],
             "evidence": {k: {"hits": 50} for k in icp["gaps"]},
             "news": [{"trigger": t} for t in ("capital", "launch", "pressure")], "filings": [{}],
             "people": [{"persona": "credit_leader", "linkedin": "x", "email": {"method": "published"}}],
             "warm_paths": ["x"]}
    s = score(maxed, icp)
    assert s == {"fit": 40, "evidence": 30.0, "timing": 20, "reach": 10, "total": 100.0}


def test_end_to_end_run_writes_csv_briefs_and_redacts(fetcher, icp, account, tmp_path):
    result = pipeline.run([account, Account("SoFi", "sofi.com", "personal_loans")], fetcher, icp, env={},
                          deep=5, log=lambda *a, **k: None)
    assert result["skipped"] == [("SoFi", "existing Pave customer")]
    row = result["rows"][0]
    assert row["gap"] in ("approvals", "nsf_timing")
    assert row["hiring"][0]["title"] == "Senior Credit Risk Analyst"
    assert row["news"][0]["trigger"] == "funding"
    assert any("Bessemer" in w for w in row["warm_paths"])
    assert any("Taktile" in w for w in row["warm_paths"])
    top = row["people"][0]
    assert top["name"] == "Priya Raman" and top["email"]["method"] == "published"

    out = report.write_outputs(result["rows"], icp, tmp_path, briefs=1, sender="Alex, Pave")
    rows = list(csv.DictReader(open(tmp_path / "targets.csv")))
    assert rows[0]["company"] == "Testlend" and rows[0]["contact_email"] == "priya.raman@testlend.example"
    brief = (tmp_path / "briefs" / "testlend.md").read_text()
    for must in ("The gap Pave solves", "Matching Pave proof point", "Why now", "Who to contact",
                 "Priya Raman", "Warm intro", "First touches", "Subject:"):
        assert must in brief, must

    public = report.redact(brief, row["people"], icp)
    assert "Priya" not in public and "priya.raman@" not in public and "Jordan Avery" not in public
    assert "[Head of Credit / Chief Risk Officer]" in public
    assert "Hi [first name]" in public


def test_keywords_match_whole_words_only(icp):
    items = [{"rating": 1, "title": "", "text": "I transferred money in and it took a week.", "source": "app_store"}]
    assert signals.gap_evidence(items, icp)["nsf_timing"]["hits"] == 0


def test_card_declines_and_disputes_are_not_approval_gaps(icp):
    items = [{"rating": 1, "title": "", "source": "app_store",
              "text": "My card was declined at the store. They denied my dispute claim. Applied for a loan and got denied."}]
    ev = signals.gap_evidence(items, icp)
    assert ev["approvals"]["hits"] == 1
    assert ev["approvals"]["examples"][0]["quote"] == "Applied for a loan and got denied."
