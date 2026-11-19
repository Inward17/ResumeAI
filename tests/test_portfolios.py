"""Portfolio and community profiles: URL extraction and validation, fetchers, cross-checks, scoring, pipeline, API.

All HTTP is mocked with httpx.MockTransport (Firecrawl included); fixtures are fictional.
"""
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.portfolios import (
    check_portfolios, detect_claims, extract_portfolios, public_url, skill_evidence, website_url,
)
from app.services.portfolios import fetchers
from app.services.portfolios.fetchers import clean_kaggle, clean_portfolio, fetch_portfolio
from app.services.portfolios.links import parse_profile_url
from app.services.unified_verification import UnifiedVerificationService, VerificationCache
from tests.test_coding_profiles import _github_ok


# ── Extraction ───────────────────────────────────────────────────────

class TestExtraction:
    def test_all_sources(self):
        text = """Ada Lovelace | ada@adalovelace.example.com
        behance.net/ada_designs  https://dribbble.com/shots/123-logo https://dribbble.com/ada-d
        https://www.kaggle.com/adalove/competitions  https://stackoverflow.com/users/123456/ada-l
        https://github.com/ada https://bit.ly/xyz https://ada.github.io/"""
        assert extract_portfolios([text]) == {
            "behance": "ada_designs", "dribbble": "ada-d", "kaggle": "adalove", "stackoverflow": "123456",
            "website": "https://ada.github.io/",
        }

    def test_pdf_link_targets_and_first_website_wins(self):
        found = extract_portfolios(["no links", "mailto:ada@example.com", "https://ada.dev/work?ref=cv#top",
                                    "https://second-site.dev/"])
        assert found == {"website": "https://ada.dev/work"}

    def test_reserved_paths_are_not_profiles(self):
        for url in ("https://www.behance.net/gallery/1/x", "https://dribbble.com/shots/1", "https://www.kaggle.com/c/titanic",
                    "https://www.kaggle.com/code/ada/nb", "https://stackoverflow.com/questions/1/x",
                    "https://stackoverflow.com/users/abc/x"):
            assert parse_profile_url(url) is None, url

    def test_bare_domain_only_on_a_site_line(self):
        assert extract_portfolios(["Portfolio: adalovelace.dev"]) == {"website": "https://adalovelace.dev/"}
        assert extract_portfolios(["Worked at acme.com on billing"]) == {}
        # Tech names and degrees are not sites, even on a portfolio line
        assert extract_portfolios(["Portfolio website built with Node.js and Socket.io, B.Tech 2021"]) == {}
        assert extract_portfolios(["Website: ada@adalovelace.dev"]) == {}

    @pytest.mark.parametrize("url", [
        "https://bit.ly/abc", "https://linktr.ee/ada", "https://www.linkedin.com/in/ada", "https://github.com/ada",
        "https://leetcode.com/u/ada", "https://docs.google.com/document/d/1", "https://drive.google.com/file/d/1",
        "https://ada.dev/resume.pdf", "https://ada.dev/photo.JPG", "https://medium.com/@ada",
    ])
    def test_not_a_personal_site(self, url):
        assert website_url(url) is None

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/", "http://10.0.0.5/admin", "http://[::1]/", "https://2130706433/", "https://0x7f000001/",
        "https://localhost/", "https://printer.local/", "https://api.internal/", "https://db.corp/", "https://intranet/",
        "https://user:pw@ada.dev/", "https://ada.dev@evil.example.com/", "https://ada.dev:8443/", "http://ada.dev:80/",
        "ftp://ada.dev/", "file:///etc/passwd", "javascript:alert(1)", "data:text/html,x", "https://ädä.de/",
        "https://ada.dev/" + "a" * 400, "https://ada .dev/",
    ])
    def test_unsafe_urls_rejected(self, url):
        assert public_url(url) is None
        assert extract_portfolios([url]) == {}

    def test_https_only_for_links(self):
        assert public_url("http://ada.dev/x", https_only=True) is None
        assert public_url("https://ada.dev/x", https_only=True) == "https://ada.dev/x"


# ── Fetchers ─────────────────────────────────────────────────────────

SO_USER = {"items": [{"display_name": "Ada &amp; Lovelace", "reputation": 12500, "location": "London",
                      "badge_counts": {"gold": 3, "silver": 20, "bronze": 40}}], "quota_remaining": 250}
SO_TAGS = {"items": [{"tag_name": "python"}, {"tag_name": "reactjs"}, {"tag_name": "python-3.x"}]}

BEHANCE_JSON = {"name": "Ada Lovelace", "headline": "Product designer", "location": "London", "followers": "1.2k",
                "appreciations": 340, "skills": ["Figma", "Illustrator"],
                "projects": [{"title": "Banking app", "tools": ["Figma", "React"], "dates": "2023",
                              "url": "https://www.behance.net/gallery/1/banking"}],
                "experience": [{"role": "Designer", "organisation": "Acme Studio", "dates": "2021 - 2023"}],
                "education": [{"degree": "B.Des", "institution": "National Institute of Design", "dates": "2017-2021"}]}
KAGGLE_JSON = {"name": "Ada Lovelace", "tiers": {"competitions": "Expert", "notebooks": "Master", "datasets": "wizard"},
               "medals": {"gold": 1, "silver": 4, "bronze": "7"}, "competitions": 12}


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _firecrawl(json_data, status_code=200):
    return httpx.Response(200, json={"success": True, "data": {"json": json_data, "metadata": {"statusCode": status_code}}})


@pytest.fixture()
def firecrawl_env(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-placeholder")
    monkeypatch.setenv("FIRECRAWL_API_URL", "https://firecrawl.test")
    monkeypatch.delenv("PORTFOLIO_CHECKS_ENABLED", raising=False)


@pytest.fixture(autouse=True)
def _reset_backoff():
    fetchers._se_backoff_until = 0.0
    yield
    fetchers._se_backoff_until = 0.0


class TestStackOverflow:
    async def test_found(self):
        def handler(req):
            assert req.url.host == "api.stackexchange.com" and req.url.params["site"] == "stackoverflow"
            return httpx.Response(200, json=SO_TAGS if req.url.path.endswith("/top-tags") else SO_USER)
        async with _client(handler) as c:
            p = await fetch_portfolio(c, "stackoverflow", "123456")
        assert p["status"] == "found" and p["name"] == "Ada & Lovelace" and p["reputation"] == 12500
        assert p["badges"] == {"gold": 3, "silver": 20, "bronze": 40}
        assert p["top_tags"] == ["python", "reactjs", "python-3.x"]
        assert p["profile_url"] == "https://stackoverflow.com/users/123456"

    async def test_not_found_and_error(self):
        async with _client(lambda req: httpx.Response(200, json={"items": []})) as c:
            assert (await fetch_portfolio(c, "stackoverflow", "999"))["status"] == "not_found"
        async with _client(lambda req: httpx.Response(400, json={"error_id": 502, "error_name": "throttle_violation"})) as c:
            assert (await fetch_portfolio(c, "stackoverflow", "999"))["status"] == "unavailable"

    async def test_backoff_is_respected(self):
        calls = []

        def handler(req):
            calls.append(req.url.path)
            return httpx.Response(200, json={**SO_USER, "backoff": 30})
        async with _client(handler) as c:
            assert (await fetch_portfolio(c, "stackoverflow", "1"))["status"] == "found"
            n = len(calls)
            assert (await fetch_portfolio(c, "stackoverflow", "2"))["status"] == "unavailable"
        assert len(calls) == n  # nothing sent while backing off


class TestFirecrawlSources:
    async def test_behance_found(self, firecrawl_env):
        sent = []

        def handler(req):
            sent.append(req)
            return _firecrawl(BEHANCE_JSON)
        async with _client(handler) as c:
            p = await fetch_portfolio(c, "behance", "ada_designs")
        assert p["status"] == "found" and p["followers"] == 1200 and p["projects"][0]["tools"] == ["Figma", "React"]
        assert len(sent) == 1 and str(sent[0].url) == "https://firecrawl.test/v2/scrape"
        assert sent[0].headers["Authorization"] == "Bearer fc-test-placeholder"
        body = json.loads(sent[0].content)
        assert body["url"] == "https://www.behance.net/ada_designs" and body["formats"][0]["type"] == "json"

    async def test_website_goes_only_to_firecrawl(self, firecrawl_env):
        hosts = []

        def handler(req):
            hosts.append(req.url.host)
            return _firecrawl(BEHANCE_JSON)
        async with _client(handler) as c:
            p = await fetch_portfolio(c, "website", "https://ada.dev/")
        assert p["status"] == "found" and hosts == ["firecrawl.test"]
        # A stored URL that fails validation is never sent anywhere
        async with _client(handler) as c:
            assert (await fetch_portfolio(c, "website", "http://127.0.0.1/"))["status"] == "unavailable"
        assert hosts == ["firecrawl.test"]

    @pytest.mark.parametrize("response, status", [
        (_firecrawl({}), "unavailable"),                        # empty extraction
        (_firecrawl(None, status_code=404), "not_found"),
        (httpx.Response(500, json={"success": False}), "unavailable"),
        (httpx.Response(402, json={"error": "Payment required"}), "unavailable"),
    ])
    async def test_empty_missing_and_errors(self, firecrawl_env, response, status):
        async with _client(lambda req: response) as c:
            assert (await fetch_portfolio(c, "dribbble", "ada-d"))["status"] == status

    async def test_timeout_is_unavailable(self, firecrawl_env):
        def handler(req):
            raise httpx.ReadTimeout("slow")
        async with _client(handler) as c:
            assert (await fetch_portfolio(c, "behance", "ada"))["status"] == "unavailable"

    @pytest.mark.parametrize("env", [{"FIRECRAWL_API_KEY": ""}, {"PORTFOLIO_CHECKS_ENABLED": "false"}])
    async def test_not_configured_sends_nothing(self, firecrawl_env, monkeypatch, env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        sent = []
        async with _client(lambda req: sent.append(req) or _firecrawl(BEHANCE_JSON)) as c:
            for platform, handle in (("behance", "ada"), ("dribbble", "ada"), ("website", "https://ada.dev/")):
                p = await fetch_portfolio(c, platform, handle)
                assert p["status"] == "not_configured" and p["note"]
        assert sent == []


class TestKaggle:
    async def test_missing_user_costs_no_firecrawl_credit(self, firecrawl_env):
        hosts = []

        def handler(req):
            hosts.append(req.url.host)
            return httpx.Response(404)
        async with _client(handler) as c:
            assert (await fetch_portfolio(c, "kaggle", "nobody"))["status"] == "not_found"
        assert hosts == ["www.kaggle.com"]

    async def test_found_through_firecrawl(self, firecrawl_env):
        def handler(req):
            return httpx.Response(200, text="<html></html>") if req.url.host == "www.kaggle.com" else _firecrawl(KAGGLE_JSON)
        async with _client(handler) as c:
            p = await fetch_portfolio(c, "kaggle", "adalove")
        assert p["status"] == "found"
        assert p["tiers"] == {"competitions": "expert", "notebooks": "master"}  # unknown tier dropped
        assert p["medals"] == {"gold": 1, "silver": 4, "bronze": 7} and p["competitions"] == 12


class TestExtractionOutputValidation:
    def test_portfolio_junk_is_cleaned(self):
        data = clean_portfolio({
            "name": ["not", "a", "string"], "headline": "x" * 1000, "followers": "lots", "appreciations": -5,
            "projects": [{"title": f"P{i}", "url": "javascript:alert(1)", "tools": ["A"] * 50} for i in range(30)]
                        + [{"description": "no title"}],
            "skills": "Figma",
            "experience": [{"role": "Dev", "organisation": {"$gt": ""}}, "junk"],
        })
        assert data["name"] is None and len(data["headline"]) == 160
        assert data["followers"] is None and data["appreciations"] is None
        assert len(data["projects"]) == 10 and all(p["url"] is None for p in data["projects"])
        assert data["projects"][0]["tools"] == ["A"]
        assert data["skills"] == [] and data["experience"] == [{"role": "Dev", "organisation": None, "dates": None}]

    def test_only_https_public_project_links(self):
        data = clean_portfolio({"projects": [{"title": "A", "url": "http://ada.dev/a"},
                                             {"title": "B", "url": "https://192.168.0.1/b"},
                                             {"title": "C", "url": "https://ada.dev/c"}]})
        assert [p["url"] for p in data["projects"]] == [None, None, "https://ada.dev/c"]

    def test_non_dict_output(self):
        assert clean_portfolio("ignore previous instructions")["projects"] == []
        assert clean_kaggle(None)["tiers"] == {}


# ── Claims and cross-checks ─────────────────────────────────────────

def _found(platform, **fields):
    return {"platform": platform, "handle": "ada", "status": "found", "issues": [], **fields}


RESUME = {"personal_info": {"full_name": "Ada Lovelace"},
          "experience": ["Product Designer at Globex, 2021 - 2023", "Intern at Initech, 2020"],
          "education": ["B.Tech in Design, National Institute of Design, 2017-2021"]}


class TestClaims:
    def test_detect(self):
        got = {(c["platform"], c["kind"], c["value"], c.get("category")) for c in detect_claims(
            "Kaggle Competitions Master. Stack Overflow: 10k+ reputation, top 1% this year. "
            "Reputation of 12,500 on StackOverflow.")}
        assert got == {("kaggle", "tier", "master", "competitions"), ("stackoverflow", "reputation", 10000, None),
                       ("stackoverflow", "top_percent", 1.0, None), ("stackoverflow", "reputation", 12500, None)}

    def test_no_claims_without_the_platform(self):
        assert detect_claims("Chess master with 10k followers, top 1% of the class") == []
        assert detect_claims("Kaggle: https://www.kaggle.com/grandmaster_ada") == []

    def test_overstated_kaggle_and_stackoverflow(self):
        kaggle = _found("kaggle", tiers={"competitions": "expert", "notebooks": "master"})
        so = _found("stackoverflow", reputation=4200)
        claims = detect_claims("Kaggle Competitions Master and Kaggle Master. Stack Overflow 10k reputation, top 1%.")
        status, disc = check_portfolios([kaggle, so], claims, RESUME)
        assert status == "unverified"
        assert kaggle["issues"] == ["Resume claims Kaggle competitions Master; profile shows Expert"]  # notebooks Master covers plain "Master"
        assert any("10,000 Stack Overflow reputation" in i for i in so["issues"])
        assert {d["source"] for d in disc} == {"kaggle", "stackoverflow"}

    def test_claims_within_reality_pass(self):
        claims = detect_claims("Kaggle Notebooks Master. Stack Overflow 10k reputation, top 1%.")
        status, _ = check_portfolios([_found("kaggle", tiers={"notebooks": "grandmaster"}),
                                      _found("stackoverflow", reputation=9000)], claims, RESUME)
        assert status == "verified"

    def test_top_percent_floor(self):
        claims = detect_claims("Top 1% on Stack Overflow.")
        assert check_portfolios([_found("stackoverflow", reputation=150)], claims, RESUME)[0] == "unverified"
        assert check_portfolios([_found("stackoverflow", reputation=1500)], claims, RESUME)[0] == "verified"

    def test_name_mismatch_only_for_real_names(self):
        p = _found("dribbble", name="Grace Hopper")
        status, disc = check_portfolios([p], [], RESUME)
        assert status == "unverified" and disc[0]["field"] == "name" and disc[0]["severity"] == "major"
        # Handles and single words are display names, not real names
        for name in ("ada_dev", "pixelqueen", "Ada"):
            assert check_portfolios([_found("stackoverflow", name=name)], [], RESUME)[0] == "verified"

    def test_different_employer_for_the_same_dates(self):
        p = _found("website", experience=[{"role": "Designer", "organisation": "Acme Studio", "dates": "2021 - 2023"}])
        status, disc = check_portfolios([p], [], RESUME)
        assert status == "unverified" and "Acme Studio" in p["issues"][0] and "Globex" in p["issues"][0]
        assert disc[0]["source"] == "website"

    def test_consistent_or_extra_experience_is_fine(self):
        same = _found("behance", experience=[{"role": "Designer", "organisation": "Globex", "dates": "2021-2023"}])
        extra = _found("behance", experience=[{"role": "Freelance", "organisation": "Self", "dates": "2019"}])
        assert check_portfolios([same], [], RESUME)[0] == "verified"
        assert check_portfolios([extra], [], RESUME)[0] == "verified"

    def test_different_degree(self):
        p = _found("behance", education=[{"degree": "B.Des", "institution": "National Institute of Design"}])
        status, _ = check_portfolios([p], [], RESUME)
        assert status == "unverified" and "B.Des" in p["issues"][0]
        ok = _found("behance", education=[{"degree": "Bachelor of Technology", "institution": "National Institute of Design"}])
        other = _found("behance", education=[{"degree": "M.Des", "institution": "Some Other School"}])
        assert check_portfolios([ok, other], [], RESUME)[0] == "verified"

    def test_statuses(self):
        missing = {"platform": "kaggle", "handle": "typo", "status": "not_found"}
        status, disc = check_portfolios([missing], [], RESUME)
        assert status == "not_found" and disc[0]["severity"] == "minor" and "doesn't exist" in disc[0]["description"]
        assert check_portfolios([_found("kaggle"), missing], [], RESUME)[0] == "verified"
        nc = {"platform": "behance", "handle": "ada", "status": "not_configured"}
        assert check_portfolios([nc], [], RESUME) == ("not_configured", [])
        assert check_portfolios([nc, {"platform": "kaggle", "status": "unavailable"}], [], RESUME)[0] == "pending"

    def test_skill_evidence(self):
        entries = [_found("behance", projects=[{"title": "x", "tools": ["React.js", "Figma"]}], skills=["UX research"]),
                   _found("stackoverflow", top_tags=["python-3.x", "node.js"]),
                   {"platform": "dribbble", "status": "not_found", "skills": ["Java"]}]
        got = skill_evidence(entries, ["React", "Python", "Node.js", "Figma", "Java", "Go"])
        assert got == [{"skill": "React", "sources": ["behance"]}, {"skill": "Python", "sources": ["stackoverflow"]},
                       {"skill": "Node.js", "sources": ["stackoverflow"]}, {"skill": "Figma", "sources": ["behance"]}]


# ── Scoring and pipeline ────────────────────────────────────────────

def _service(mock_db):
    with patch.object(UnifiedVerificationService, "__init__", lambda self, **kwargs: None):
        service = UnifiedVerificationService.__new__(UnifiedVerificationService)
        service.db = mock_db
        service.cache = VerificationCache()
        return service


FETCHED = [{"platform": "stackoverflow", "handle": "123456", "profile_url": "https://stackoverflow.com/users/123456",
            "status": "found", "name": "Ada Lovelace", "reputation": 4200, "top_tags": ["python"], "issues": []},
           {"platform": "behance", "handle": "ada", "status": "not_configured", "note": "Firecrawl not configured",
            "issues": []}]


class TestPipeline:
    @patch("app.services.unified_verification.fetch_portfolios", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    async def test_scores_identical_with_and_without_portfolios(self, mock_gh, mock_fetch, mock_db):
        mock_gh.return_value = _github_ok()
        mock_fetch.return_value = [dict(p) for p in FETCHED]
        without = await _service(mock_db).run_unified_verification(
            candidate_id="pf-a", github_username="ada", parsed_resume=RESUME)
        with_pf = await _service(mock_db).run_unified_verification(
            candidate_id="pf-b", github_username="ada", parsed_resume=RESUME,
            portfolios={"stackoverflow": "123456", "behance": "ada"},
            portfolio_claims=detect_claims("Stack Overflow 10k reputation"))
        assert with_pf.verificationStatus.portfolios == "unverified"
        assert with_pf.matchScore.model_dump() == without.matchScore.model_dump()
        doc = await mock_db.verification_data.find_one({"candidateId": "pf-b"})
        assert doc["portfoliosData"][0]["reputation"] == 4200
        assert doc["verificationStatus"]["discrepancies"][0]["source"] == "stackoverflow"

    @patch("app.services.unified_verification.fetch_portfolios", new_callable=AsyncMock)
    async def test_portfolios_alone_give_no_score(self, mock_fetch, mock_db):
        mock_fetch.return_value = [dict(p) for p in FETCHED]
        result = await _service(mock_db).run_unified_verification(candidate_id="pf-c", portfolios={"stackoverflow": "1"})
        assert result.verificationStatus.portfolios == "verified" and result.matchScore is None

    @patch("app.services.unified_verification.fetch_portfolios", new_callable=AsyncMock)
    async def test_fetch_failure_does_not_break_pipeline(self, mock_fetch, mock_db):
        mock_fetch.side_effect = RuntimeError("boom")
        result = await _service(mock_db).run_unified_verification(candidate_id="pf-d", portfolios={"kaggle": "ada"})
        assert result.verificationStatus.portfolios == "pending"

    async def test_parse_stores_portfolios_and_claims(self, mock_db, tmp_path):
        from app.routes import resume
        (tmp_path / "r.txt").write_text("Ada Lovelace\nPortfolio: https://ada.dev | kaggle.com/adalove | Kaggle Expert\n",
                                        encoding="utf-8")
        parsed = {"personal_info": {"full_name": "Ada Lovelace"}, "skills": "Python"}
        with patch.object(resume, "RESUMES_DIR", str(tmp_path)), \
             patch.object(resume, "parse_resume", AsyncMock(return_value=parsed)), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0]):
            cid = await resume._parse_and_store("r.txt", "task-pf")
        doc = await mock_db.candidates.find_one({"candidate_id": cid})
        assert doc["portfolios"] == {"website": "https://ada.dev/", "kaggle": "adalove"}
        assert doc["portfolio_claims"][0]["value"] == "expert"


# ── API ──────────────────────────────────────────────────────────────

class TestCandidatesApi:
    async def test_candidates_include_portfolios(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "p1", "job_id": owned_job_id})
        await mock_db.applications.insert_one({"candidate_id": "p2", "job_id": owned_job_id})
        await mock_db.candidates.insert_one({"candidate_id": "p1", "parsed": {}, "portfolios": {"stackoverflow": "123456"}})
        await mock_db.candidates.insert_one({"candidate_id": "p2", "parsed": {},
                                             "portfolios": {"website": "https://ada.dev/", "behance": "ada"}})
        await mock_db.verification_data.insert_one({"candidateId": "p1", "portfoliosData": [
            {**FETCHED[0], "issues": ["Resume claims 10,000 Stack Overflow reputation; profile shows 4,200"],
             "projects": [{"title": "A", "url": "javascript:alert(1)"}, {"title": "B", "url": "https://ada.dev/b"}]},
            {"platform": "website", "handle": "http://127.0.0.1/", "status": "found"},
        ]})
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        by_id = {c["candidate_id"]: c for c in resp.json()["candidates"]}
        pf = by_id["p1"]["portfolios"]
        assert len(pf) == 1  # the unsafe stored URL is dropped
        assert pf[0]["profile_url"] == "https://stackoverflow.com/users/123456" and pf[0]["reputation"] == 4200
        assert [p["url"] for p in pf[0]["projects"]] == [None, "https://ada.dev/b"]
        assert pf[0]["issues"][0].startswith("Resume claims 10,000")
        # The job requires Python; the Stack Overflow tag shows it (evidence only)
        assert by_id["p1"]["portfolio_skill_evidence"] == [{"skill": "Python", "sources": ["stackoverflow"]}]
        # Not checked yet: listed sources show as pending
        assert [(p["platform"], p["status"], p["profile_url"]) for p in by_id["p2"]["portfolios"]] == [
            ("website", "pending", "https://ada.dev/"), ("behance", "pending", "https://www.behance.net/ada")]

    async def test_no_portfolios_is_empty_list(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "p3", "job_id": owned_job_id})
        await mock_db.candidates.insert_one({"candidate_id": "p3", "parsed": {}})
        c = (await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")).json()["candidates"][0]
        assert c["portfolios"] == [] and c["portfolio_skill_evidence"] == []


# ── Fact checker ─────────────────────────────────────────────────────

class TestFactChecker:
    def test_router_sends_portfolio_questions_to_general_qa(self):
        from app.services.fact_checker_service import ROUTER_SYSTEM_PROMPT
        for name in ("Behance", "Dribbble", "portfolio website", "Kaggle", "Stack Overflow"):
            assert name in ROUTER_SYSTEM_PROMPT
        assert '"general_qa"' in ROUTER_SYSTEM_PROMPT.split("Stack Overflow", 1)[1]

    @pytest.mark.parametrize("handler", ["_handle_general_qa", "_handle_verify_tech",
                                         "_handle_verify_project", "_handle_verify_authenticity"])
    async def test_summary_reaches_prompt(self, handler):
        from app.services import fact_checker_service as fc
        verification = {"portfoliosData": [
            {**FETCHED[0], "badges": {"gold": 1, "silver": 2, "bronze": 3},
             "issues": ["Resume claims 10,000 Stack Overflow reputation; profile shows 4,200"]},
            _found("behance", projects=[{"title": "Banking app", "tools": ["Figma"]}]),
            FETCHED[1]]}
        groq = AsyncMock(return_value="ok")
        with patch.object(fc, "_call_groq", groq):
            await getattr(fc, handler)("Stack Overflow?", {"parsed": {}}, verification, "Ada")
        prompt = groq.call_args.args[1]
        assert "stackoverflow 123456" in prompt and "reputation 4200" in prompt and "top tags python" in prompt
        assert "Banking app (Figma)" in prompt and "Resume claims 10,000" in prompt
        assert "behance ada: " in prompt and "Firecrawl" not in prompt  # unchecked sources are left out
