from prospector.connectors import appstore, cfpb, jobs, news, website


def test_find_app_prefers_same_seller_site_over_bigger_app(fetcher):
    app = appstore.find_app(fetcher, "Testlend", "testlend.example", "Testlend")
    assert app["app_id"] == 222
    assert app["rating"] == 4.41


def test_find_app_returns_none_when_nothing_matches(fetcher):
    assert appstore.find_app(fetcher, "Nobody", "nobody.example", "Nobody") is None


def test_reviews_parse_rating_text_and_date(fetcher):
    rows = appstore.reviews(fetcher, 222, pages=1)
    assert len(rows) == 4
    assert rows[0]["rating"] == 1 and rows[0]["date"] == "2026-10-30"
    assert rows[0]["source"] == "app_store"


def test_cfpb_resolves_legal_name_and_reads_narratives(fetcher):
    legal = cfpb.resolve_company(fetcher, "Testlend")
    assert legal == "Testlend Inc."
    c = cfpb.complaints(fetcher, legal)
    assert c["total_with_narrative"] == 2
    assert c["items"][0]["url"].endswith("/9001")


def test_jobs_finds_board_by_domain_stem(fetcher):
    board = jobs.open_roles(fetcher, "testlend.example", "Testlend")
    assert board["board"] == "greenhouse" and len(board["roles"]) == 2


def test_news_keeps_only_headlines_naming_the_company(fetcher):
    heads = news.headlines(fetcher, "Testlend")
    assert len(heads) == 1 and "Series B" in heads[0]["title"]


def test_website_scan_finds_stack_bank_people_and_contacts(fetcher, icp):
    site = website.scan(fetcher, "testlend.example", icp)
    assert site["aggregators"] == ["Plaid"]
    assert site["pave_partners"] == ["Taktile"]
    assert site["partner_bank"] == "Example Valley Bank"
    assert site["emails"]["role"] == ["press@testlend.example"]
    assert site["emails"]["personal"] == ["priya.raman@testlend.example"]
    assert site["socials"]["x"] == "https://x.com/testlend"
    assert site["socials"]["linkedin_company"].endswith("/company/testlend")
    names = {p["name"]: p["persona"] for p in site["people"]}
    assert names == {"Jordan Avery": "founder", "Priya Raman": "credit_leader"}  # VP Marketing is dropped


def test_website_respects_robots(transport, fetcher, icp):
    transport.routes["testlend.example/robots.txt"] = "User-agent: *\nDisallow: /\n"
    site = website.scan(fetcher, "testlend.example", icp)
    assert site["pages_read"] == []
    assert not any("leadership" in c[1] for c in transport.calls)


def test_persona_matching_short_titles_need_word_boundaries(icp):
    assert website.match_persona("CEO", icp) == "founder"
    assert website.match_persona("Account Executive", icp) is None  # contains "coo"? no; contains "ceo"? no
    assert website.match_persona("Cooper Lane Partners", icp) is None


def test_people_capitalized_titles_are_not_mistaken_for_names(icp):
    html = ("<div><h3>Jordan Avery</h3><p>Chief Executive Officer</p></div>"
            "<div><h3>Priya Raman</h3><p>Chief Risk Officer</p></div>"
            "<div><p>Chief Financial Officer</p><h3>Alex Kim</h3></div>")
    got = {p["name"]: p["persona"] for p in website.extract_people(html, icp)}
    assert got["Jordan Avery"] == "founder"
    assert got["Priya Raman"] == "credit_leader"
    assert "Chief Risk Officer" not in got
