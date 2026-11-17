from prospector.connectors import email

PERSON = {"name": "Priya Raman", "persona": "credit_leader"}
SITE_NONE = {"emails": {"role": [], "personal": []}}


def _budget(**kw):
    return email.Budget({"APOLLO_MAX_CALLS": 5, "HUNTER_MAX_CALLS": 5, "EXA_MAX_CALLS": 5, **kw})


def test_published_email_wins_and_no_api_is_called(fetcher, transport):
    site = {"emails": {"role": [], "personal": ["priya.raman@testlend.example"]}}
    env = {"APOLLO_API_KEY": "k", "HUNTER_API_KEY": "k"}
    r = email.find_email(fetcher, PERSON, "testlend.example", site, env, _budget())
    assert r["method"] == "published" and r["confidence"] == "high"
    assert not any("apollo" in c[1] or "hunter" in c[1] for c in transport.calls)


def test_apollo_before_hunter(fetcher, transport):
    transport.routes["people/match"] = {"person": {"email": "priya@testlend.example", "email_status": "verified"}}
    transport.routes["hunter.io"] = {"data": {"email": "p.raman@testlend.example", "score": 99}}
    r = email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE,
                         {"APOLLO_API_KEY": "k", "HUNTER_API_KEY": "k"}, _budget())
    assert r["method"] == "apollo" and r["email"] == "priya@testlend.example" and r["confidence"] == "high"


def test_hunter_when_apollo_has_nothing(fetcher, transport):
    transport.routes["people/match"] = {"person": {"email": "email_not_unlocked@domain.com"}}
    transport.routes["hunter.io"] = {"data": {"email": "p.raman@testlend.example", "score": 75, "sources": [1, 2]}}
    r = email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE,
                         {"APOLLO_API_KEY": "k", "HUNTER_API_KEY": "k"}, _budget())
    assert r["method"] == "hunter" and r["confidence"] == "medium"


def test_exa_finds_address_printed_on_a_public_page(fetcher, transport):
    transport.routes["api.exa.ai"] = {"results": [{"url": "https://conf.example.org/speakers",
                                                   "text": "Contact: priya.raman@testlend.example"}]}
    r = email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE, {"EXA_API_KEY": "k"}, _budget())
    assert r["method"] == "exa" and r["source"] == "https://conf.example.org/speakers"


def test_guess_only_when_every_source_fails_and_is_labeled(fetcher):
    r = email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE, {}, _budget())
    assert r["method"] == "guess"
    assert r["confidence"] == "guess - verify"
    assert r["email"] == "priya.raman@testlend.example"
    assert "also try" in r["source"]


def test_guess_uses_pattern_learned_from_site(fetcher):
    pattern = email.pattern_from_examples(["jordan@testlend.example"], [{"name": "Jordan Avery"}])
    assert pattern == "{first}"
    r = email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE, {}, _budget(), pattern)
    assert r["email"] == "priya@testlend.example" and "pattern seen on company site" in r["source"]


def test_budget_stops_credit_spend(fetcher, transport):
    transport.routes["hunter.io"] = {"data": {"email": "p.raman@testlend.example", "score": 95}}
    b = _budget(HUNTER_MAX_CALLS=1)
    env = {"HUNTER_API_KEY": "k"}
    assert email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE, env, b)["method"] == "hunter"
    assert email.find_email(fetcher, PERSON, "testlend.example", SITE_NONE, env, b)["method"] == "guess"


def test_mx_check(fetcher):
    assert email.mail_domain_ok(fetcher, "testlend.example") == {"accepts_mail": True,
                                                                 "provider": "Google Workspace"}


def test_split_name_handles_accents_and_suffixes():
    assert email.split_name("José A. García-López Jr.") == ("jose", "garcialopez")
