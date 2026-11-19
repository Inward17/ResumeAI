"""Coding-profile verification: handle extraction, fetchers, claim checks, scoring, pipeline and API.

All HTTP is mocked with httpx.MockTransport; fixtures are fictional.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.coding_profiles import check_profiles, coding_bonus, detect_claims, extract_coding_profiles
from app.services.coding_profiles.fetchers import (
    HEADERS,
    fetch_profile,
    parse_codechef,
    parse_hackerearth,
)
from app.services.coding_profiles.handles import parse_profile_url, profile_url
from app.services.unified_verification import UnifiedVerificationService, VerificationCache
from app.models.verification_data_model import GitHubDataModel, WebSearchDataModel, WebSearchResult, EducationVerification


# ── Handle extraction ────────────────────────────────────────────────

class TestHandleExtraction:
    def test_all_platform_url_forms(self):
        text = """Profiles: https://leetcode.com/u/ada_dev/ | hackerrank.com/profile/ada.l
        www.hackerearth.com/@ada-l  https://codeforces.com/profile/ada_l99 codechef.com/users/ada.lovelace."""
        assert extract_coding_profiles([text]) == {
            "leetcode": "ada_dev", "hackerrank": "ada.l", "hackerearth": "ada-l",
            "codeforces": "ada_l99", "codechef": "ada.lovelace",
        }

    def test_short_forms_and_pdf_links(self):
        found = extract_coding_profiles(["no links here", "https://leetcode.com/ada_dev", "https://www.hackerrank.com/ada_l"])
        assert found == {"leetcode": "ada_dev", "hackerrank": "ada_l"}

    @pytest.mark.parametrize("url", [
        "https://leetcode.com/problems/two-sum/",           # site page, not a user
        "https://www.hackerrank.com/certificates/abc123",   # certificate, not a profile
        "https://leetcode.com/u/../admin",                  # path traversal
        "https://leetcode.com/u/%2e%2e/admin",              # encoded traversal
        "https://codeforces.com/profile/ab",                # too short for Codeforces
        "https://leetcode.com.evil.example/u/ada",          # other host
        "https://evil.example/leetcode.com/u/ada",          # other host
        "https://user:pw@leetcode.com/u/ada",               # credentials in URL
        "https://leetcode.com:8443/u/ada",                  # port
        "javascript:alert(1)//leetcode.com/u/ada",           # other scheme
        "https://codechef.com/users/a<b",                   # bad characters
    ])
    def test_rejects_tricks(self, url):
        assert parse_profile_url(url) is None

    def test_query_string_never_reaches_the_handle(self):
        assert parse_profile_url("https://leetcode.com/u/ada?x=../../etc") == ("leetcode", "ada")
        assert extract_coding_profiles(["mail me at bob@leetcode.com"]) == {}

    def test_profile_url_is_rebuilt_from_validated_handle(self):
        assert profile_url("codechef", "ada.lovelace") == "https://www.codechef.com/users/ada.lovelace"
        with pytest.raises(ValueError):
            profile_url("leetcode", "../x")


# ── Fetchers ─────────────────────────────────────────────────────────

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=HEADERS)


LEETCODE_FOUND = {"data": {
    "matchedUser": {"username": "ada_dev", "profile": {"realName": "Ada Lovelace"},
                    "submitStatsGlobal": {"acSubmissionNum": [{"difficulty": "All", "count": 412}, {"difficulty": "Easy", "count": 200}]}},
    "userContestRanking": {"rating": 1903.6, "attendedContestsCount": 18, "badge": {"name": "Knight"}},
}}

CODECHEF_HTML = """<html><body>
<div class="user-details-container plr10"><header><h1 class="h2-style">Ada Lovelace</h1></header>
<section><h3>Total Problems Solved: 321</h3></section></div>
<div id="rating-block-all"><div class="rating-header text-center">
<div class="rating-number">1845</div>
<div class="rating-star"><span>&#9733;</span><span>&#9733;</span><span>&#9733;</span><span>&#9733;</span></div>
<small>(Highest Rating 1912)</small></div></div>
<div class="contest-participated-count">Contests Participated: <b>40</b></div>
</body></html>"""

HACKEREARTH_HTML = (
    '<html><script>self.__next_f.push([1,"{\\"profileData\\":{\\"full_name\\":\\"Ada Lovelace\\",'
    '\\"global_badges\\":{\\"badges\\":[{\\"badge\\":{\\"name\\":\\"Novice\\",\\"description\\":\\"\\",\\"level\\":1,'
    '\\"points\\":40,\\"image_url\\":\\"x\\",\\"category\\":\\"he_level\\",\\"b_type\\":\\"global\\"}},'
    '{\\"badge\\":{\\"name\\":\\"Explorer\\",\\"description\\":\\"\\",\\"level\\":3,\\"points\\":800,'
    '\\"image_url\\":\\"x\\",\\"category\\":\\"he_level\\",\\"b_type\\":\\"global\\"}}]},'
    '\\"global_badge_progress\\":{\\"current_score\\":950}}}"])</script></html>'
)


class TestFetchers:
    async def test_leetcode_found(self):
        def handler(request):
            assert request.url.host == "leetcode.com"
            assert json.loads(request.content)["variables"] == {"u": "ada_dev"}
            return httpx.Response(200, json=LEETCODE_FOUND)
        async with _client(handler) as c:
            p = await fetch_profile(c, "leetcode", "ada_dev")
        assert p["status"] == "found"
        assert (p["name"], p["problems_solved"], p["rating"], p["title"], p["contests"]) == ("Ada Lovelace", 412, 1904, "Knight", 18)
        assert p["profile_url"] == "https://leetcode.com/u/ada_dev/"

    async def test_leetcode_not_found(self):
        async with _client(lambda r: httpx.Response(200, json={"data": {"matchedUser": None, "userContestRanking": None}})) as c:
            assert (await fetch_profile(c, "leetcode", "nobody"))["status"] == "not_found"

    async def test_timeout_is_unavailable(self):
        def handler(request):
            raise httpx.ReadTimeout("slow", request=request)
        async with _client(handler) as c:
            for platform in ("leetcode", "hackerrank", "codeforces", "hackerearth", "codechef"):
                p = await fetch_profile(c, platform, "ada_dev")
                assert p["status"] == "unavailable" and p["rating"] is None

    async def test_server_error_is_unavailable(self):
        async with _client(lambda r: httpx.Response(503, text="down")) as c:
            assert (await fetch_profile(c, "leetcode", "ada_dev"))["status"] == "unavailable"
            assert (await fetch_profile(c, "codechef", "ada_dev"))["status"] == "unavailable"

    async def test_invalid_handle_is_never_fetched(self):
        def handler(request):
            raise AssertionError("must not fetch")
        async with _client(handler) as c:
            p = await fetch_profile(c, "leetcode", "../admin")
        assert p["status"] == "unavailable" and p["profile_url"] is None

    async def test_hackerrank(self):
        def handler(request):
            if request.url.path.endswith("/profile"):
                return httpx.Response(200, json={"model": {"name": "Ada Lovelace"}})
            return httpx.Response(200, json={"models": [
                {"badge_name": "Problem Solving", "stars": 5, "solved": 120},
                {"badge_name": "Python", "stars": 3, "solved": 30},
            ]})
        async with _client(handler) as c:
            p = await fetch_profile(c, "hackerrank", "ada_l")
        assert p["status"] == "found" and p["stars"] == 5 and p["problems_solved"] == 150
        assert p["title"] == "5★ Problem Solving"

    async def test_hackerrank_not_found(self):
        async with _client(lambda r: httpx.Response(404, json={"error": "Not Found"})) as c:
            assert (await fetch_profile(c, "hackerrank", "nobody"))["status"] == "not_found"

    async def test_codeforces(self):
        def handler(request):
            if request.url.path == "/api/user.info":
                return httpx.Response(200, json={"status": "OK", "result": [{
                    "handle": "ada_l99", "firstName": "Ada", "lastName": "Lovelace", "rating": 1580,
                    "maxRating": 1650, "rank": "specialist", "maxRank": "expert"}]})
            return httpx.Response(200, json={"status": "OK", "result": [{}, {}, {}]})
        async with _client(handler) as c:
            p = await fetch_profile(c, "codeforces", "ada_l99")
        assert (p["name"], p["rating"], p["max_rating"], p["title"], p["max_title"], p["contests"]) == \
            ("Ada Lovelace", 1580, 1650, "specialist", "expert", 3)

    async def test_codeforces_not_found_and_rate_limit(self):
        async with _client(lambda r: httpx.Response(400, json={"status": "FAILED", "comment": "handles: User with handle x not found"})) as c:
            assert (await fetch_profile(c, "codeforces", "nobody"))["status"] == "not_found"
        async with _client(lambda r: httpx.Response(503, json={"status": "FAILED", "comment": "Call limit exceeded"})) as c:
            assert (await fetch_profile(c, "codeforces", "ada_l99"))["status"] == "unavailable"

    async def test_codechef_page(self):
        async with _client(lambda r: httpx.Response(200, text=CODECHEF_HTML)) as c:
            p = await fetch_profile(c, "codechef", "ada.lovelace")
        assert (p["name"], p["rating"], p["max_rating"], p["stars"], p["problems_solved"], p["contests"]) == \
            ("Ada Lovelace", 1845, 1912, 4, 321, 40)

    async def test_codechef_unknown_user_redirects(self):
        async with _client(lambda r: httpx.Response(302, headers={"location": "https://www.codechef.com/"})) as c:
            assert (await fetch_profile(c, "codechef", "nobody"))["status"] == "not_found"

    async def test_hackerearth_page(self):
        assert parse_hackerearth(HACKEREARTH_HTML) == {"name": "Ada Lovelace", "title": "Explorer", "rating": None, "points": 950}
        async with _client(lambda r: httpx.Response(404, text="missing")) as c:
            assert (await fetch_profile(c, "hackerearth", "nobody"))["status"] == "not_found"

    @pytest.mark.parametrize("platform", ["codechef", "hackerearth"])
    async def test_changed_layout_reads_nothing(self, platform):
        html = "<html><body><div class='new-design'>Rating 9999, 5000 problems</div></body></html>"
        async with _client(lambda r: httpx.Response(200, text=html)) as c:
            p = await fetch_profile(c, platform, "ada_l")
        assert p["status"] == "unavailable"
        assert p["rating"] is None and p["problems_solved"] is None
        assert p["note"] == "Could not read the profile page"

    def test_codechef_unrated_has_no_numbers(self):
        html = CODECHEF_HTML.replace("1845", "NA").replace("(Highest Rating 1912)", "").replace(
            '<div class="rating-star"><span>&#9733;</span><span>&#9733;</span><span>&#9733;</span><span>&#9733;</span></div>', "")
        p = parse_codechef(html)
        assert p["rating"] is None and p["max_rating"] is None and p["stars"] is None


# ── Claims ───────────────────────────────────────────────────────────

def _found(platform, **fields):
    return {"platform": platform, "handle": "ada", "status": "found", "name": None, "issues": [], **fields}


class TestClaims:
    def test_detects_claims(self):
        text = """Achievements
        LeetCode Guardian, max rating 2250
        5-star on CodeChef | Codeforces Expert (1650)
        HackerRank 5 stars in Problem Solving
        Solved 500+ problems across platforms"""
        got = {(c["platform"], c["kind"], c["value"]) for c in detect_claims(text)}
        assert {("leetcode", "title", "guardian"), ("leetcode", "rating", 2250), ("codechef", "stars", 5),
                ("codeforces", "title", "expert"), ("hackerrank", "stars", 5), (None, "problems", 500)} <= got
        hr = next(c for c in detect_claims(text) if c["platform"] == "hackerrank")
        assert hr["domain"].lower() == "problem solving"

    def test_ignores_unrelated_numbers(self):
        assert detect_claims("Led a team of 5 engineers; GPA 3.9; 2019-2023") == []

    def test_overstated_claims_are_flagged(self):
        profiles = [
            _found("leetcode", rating=1700, title="Knight", problems_solved=300),
            _found("codeforces", rating=1300, max_rating=1450, title="pupil", max_title="specialist"),
            _found("codechef", rating=1700, max_rating=1750, stars=3),
            _found("hackerrank", stars=3, badges=[{"name": "Problem Solving", "stars": 3}]),
        ]
        claims = detect_claims("""LeetCode Guardian with rating 2100, solved 600 problems on LeetCode
        Codeforces Expert
        5 star coder on CodeChef
        HackerRank 5 stars in Problem Solving""")
        status, disc = check_profiles(profiles, claims, "Ada Lovelace")
        assert status == "unverified"
        assert len(profiles[0]["issues"]) == 3            # badge, rating, problems
        assert profiles[1]["issues"] and profiles[2]["issues"] and profiles[3]["issues"]
        assert all(d["source"] in ("leetcode", "codeforces", "codechef", "hackerrank") for d in disc)

    def test_claims_within_margin_pass(self):
        profiles = [_found("leetcode", rating=1880, title="Knight", problems_solved=450),
                    _found("codeforces", rating=1500, max_rating=1620, title="specialist", max_title="expert")]
        claims = detect_claims("LeetCode Knight, rating 1950, 500+ problems on LeetCode\nCodeforces Expert, rated 1650")
        status, disc = check_profiles(profiles, claims, "Ada Lovelace")
        assert (status, disc) == ("verified", [])

    def test_combined_problem_total(self):
        claims = detect_claims("Solved 1000+ problems")
        status, disc = check_profiles([_found("leetcode", problems_solved=300), _found("codechef", problems_solved=200)], claims, None)
        assert status == "unverified" and disc[0]["source"] == "coding_profiles"
        # A profile without a count makes the total incomplete: no verdict
        status, disc = check_profiles([_found("leetcode", problems_solved=300), _found("codeforces")], claims, None)
        assert (status, disc) == ("verified", [])

    def test_name_check(self):
        p = [_found("leetcode", name="Bob Smith")]
        status, disc = check_profiles(p, [], "Ada Lovelace")
        assert status == "unverified" and p[0]["name_conflict"] and disc[0]["field"] == "name"
        # Partial name or missing name is not a conflict
        assert check_profiles([_found("leetcode", name="ada")], [], "Ada Lovelace")[0] == "verified"
        assert check_profiles([_found("leetcode", name=None)], [], "Ada Lovelace")[0] == "verified"

    def test_status_without_found_profiles(self):
        assert check_profiles([{"platform": "leetcode", "status": "not_found"}], [], "Ada")[0] == "not_found"
        assert check_profiles([{"platform": "leetcode", "status": "unavailable"}], [], "Ada")[0] == "pending"


# ── Scoring ──────────────────────────────────────────────────────────

def _service(mock_db=None):
    with patch.object(UnifiedVerificationService, "__init__", lambda self, **kwargs: None):
        service = UnifiedVerificationService.__new__(UnifiedVerificationService)
        service.db = mock_db
        service.cache = VerificationCache()
        return service


class TestScoring:
    def test_bonus_cap_and_env(self, monkeypatch):
        assert coding_bonus("verified") == 5
        assert coding_bonus("unverified") == 0 and coding_bonus("not_found") == 0
        monkeypatch.setenv("CODING_PROFILE_BONUS_MAX", "50")
        assert coding_bonus("verified") == 10
        monkeypatch.setenv("CODING_PROFILE_BONUS_MAX", "junk")
        assert coding_bonus("verified") == 5

    def test_bonus_added_on_top_of_github(self):
        gh = GitHubDataModel(success=True, score=70.0, score100=70.0)
        result = _service()._calculate_match_scores(gh, None, None, 5)
        assert result.overallCredibility == 75 and result.codingProfileBonus == 5

    def test_never_above_100(self):
        gh = GitHubDataModel(success=True, score=98.0, score100=98.0)
        assert _service()._calculate_match_scores(gh, None, None, 5).overallCredibility == 100

    def test_web_only_cap_kept(self):
        web = WebSearchDataModel(results=[WebSearchResult(education=EducationVerification(average_score=100))])
        result = _service()._calculate_match_scores(None, None, web, 5)
        assert result.overallCredibility == 50 and result.codingProfileBonus == 0


# ── Pipeline ─────────────────────────────────────────────────────────

FETCHED = [{"platform": "leetcode", "handle": "ada_dev", "profile_url": "https://leetcode.com/u/ada_dev/",
            "status": "found", "name": "Ada Lovelace", "rating": 1900, "title": "Knight",
            "problems_solved": 400, "issues": []}]


def _github_ok():
    gh = MagicMock()
    gh.success, gh.username, gh.score100, gh.score40, gh.confidenceLevel, gh.redFlags = True, "ada", 70.0, 28.0, "HIGH", []
    gh.to_mongo_dict.return_value = {"username": "ada"}
    return gh


class TestPipeline:
    @patch("app.services.unified_verification.fetch_coding_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    async def test_results_stored_with_bonus(self, mock_gh, mock_fetch, mock_db):
        mock_gh.return_value = _github_ok()
        mock_fetch.return_value = [dict(p) for p in FETCHED]
        await _service(mock_db).run_unified_verification(
            candidate_id="cand-cp", github_username="ada", parsed_resume={"personal_info": {"full_name": "Ada Lovelace"}},
            coding_profiles={"leetcode": "ada_dev"}, coding_claims=detect_claims("LeetCode Knight"))
        doc = await mock_db.verification_data.find_one({"candidateId": "cand-cp"})
        assert doc["verificationStatus"]["codingProfiles"] == "verified"
        assert doc["codingProfilesData"][0]["rating"] == 1900
        assert doc["matchScore"]["overallCredibility"] == 75 and doc["matchScore"]["codingProfileBonus"] == 5

    @patch("app.services.unified_verification.fetch_coding_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    async def test_overstated_claim_adds_discrepancy_and_no_bonus(self, mock_gh, mock_fetch, mock_db):
        mock_gh.return_value = _github_ok()
        mock_fetch.return_value = [dict(p) for p in FETCHED]
        result = await _service(mock_db).run_unified_verification(
            candidate_id="cand-cp2", github_username="ada", parsed_resume={"personal_info": {"full_name": "Ada Lovelace"}},
            coding_profiles={"leetcode": "ada_dev"}, coding_claims=detect_claims("LeetCode Guardian"))
        assert result.verificationStatus.codingProfiles == "unverified"
        assert result.verificationStatus.discrepancies[0].source == "leetcode"
        assert result.matchScore.overallCredibility == 70

    @patch("app.services.unified_verification.fetch_coding_profiles", new_callable=AsyncMock)
    async def test_coding_profiles_alone_give_no_score(self, mock_fetch, mock_db):
        mock_fetch.return_value = [dict(p) for p in FETCHED]
        result = await _service(mock_db).run_unified_verification(
            candidate_id="cand-cp3", coding_profiles={"leetcode": "ada_dev"})
        assert result.verificationStatus.codingProfiles == "verified"
        assert result.matchScore is None

    @patch("app.services.unified_verification.fetch_coding_profiles", new_callable=AsyncMock)
    async def test_fetch_failure_does_not_break_pipeline(self, mock_fetch, mock_db):
        mock_fetch.side_effect = RuntimeError("boom")
        result = await _service(mock_db).run_unified_verification(
            candidate_id="cand-cp4", coding_profiles={"leetcode": "ada_dev"})
        assert result.verificationStatus.codingProfiles == "pending"

    async def test_parse_stores_handles_and_claims(self, mock_db, tmp_path):
        from app.routes import resume
        (tmp_path / "r.txt").write_text("Ada Lovelace\nleetcode.com/u/ada_dev | LeetCode Knight\n", encoding="utf-8")
        parsed = {"personal_info": {"full_name": "Ada Lovelace"}, "skills": "Python"}
        with patch.object(resume, "RESUMES_DIR", str(tmp_path)), \
             patch.object(resume, "parse_resume", AsyncMock(return_value=parsed)), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0]):
            cid = await resume._parse_and_store("r.txt", "task-cp")
        doc = await mock_db.candidates.find_one({"candidate_id": cid})
        assert doc["coding_profiles"] == {"leetcode": "ada_dev"}
        assert doc["coding_claims"][0]["kind"] == "title"


# ── API ──────────────────────────────────────────────────────────────

class TestCandidatesApi:
    async def test_candidates_include_coding_profiles(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "c1", "job_id": owned_job_id, "status": "Under Review"})
        await mock_db.applications.insert_one({"candidate_id": "c2", "job_id": owned_job_id, "status": "Under Review"})
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {"personal_info": {"full_name": "Ada"}},
                                             "coding_profiles": {"leetcode": "ada_dev"}})
        await mock_db.candidates.insert_one({"candidate_id": "c2", "parsed": {"personal_info": {"full_name": "Bo"}},
                                             "coding_profiles": {"codechef": "bo.c"}})
        await mock_db.verification_data.insert_one({"candidateId": "c1", "codingProfilesData": [
            {**FETCHED[0], "issues": ["Resume claims LeetCode Guardian; profile badge is Knight"]},
            {"platform": "codechef", "handle": "../bad", "status": "found"},
        ]})
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        by_id = {c["candidate_id"]: c for c in resp.json()["candidates"]}
        cp = by_id["c1"]["coding_profiles"]
        assert len(cp) == 1  # the invalid stored handle is dropped
        assert cp[0]["profile_url"] == "https://leetcode.com/u/ada_dev/" and cp[0]["rating"] == 1900
        assert cp[0]["issues"] == ["Resume claims LeetCode Guardian; profile badge is Knight"]
        # Not verified yet: the listed handle shows as pending
        assert by_id["c2"]["coding_profiles"] == [{**{k: None for k in cp[0] if k not in ("platform", "handle", "status", "issues", "profile_url")},
                                                  "platform": "codechef", "handle": "bo.c", "status": "pending",
                                                  "issues": [], "profile_url": "https://www.codechef.com/users/bo.c"}]

    async def test_no_profiles_is_empty_list(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "c3", "job_id": owned_job_id})
        await mock_db.candidates.insert_one({"candidate_id": "c3", "parsed": {}})
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        assert resp.json()["candidates"][0]["coding_profiles"] == []


# ── Regression: live preview resume (sentence splitting, URLs not read as claims) ──

PREVIEW_RESUME = """Asha Verma
LeetCode: https://leetcode.com/u/lee215/ | Codeforces: https://codeforces.com/profile/tourist | CodeChef: https://www.codechef.com/users/gennady.korotkevich | HackerEarth: https://www.hackerearth.com/@vivek

SUMMARY
Backend engineer. LeetCode Knight with a contest rating of 2500. Codeforces Expert. Solved 3000+ problems across platforms.
"""


class TestPreviewRegression:
    def test_claims_from_preview_resume(self):
        got = {(c["platform"], c["kind"], c["value"]) for c in detect_claims(PREVIEW_RESUME)}
        assert got == {("leetcode", "title", "knight"), ("leetcode", "rating", 2500),
                       ("codeforces", "title", "expert"), (None, "problems", 3000)}

    def test_urls_and_bare_links_give_no_claims(self):
        assert detect_claims("Codeforces: https://codeforces.com/profile/tourist") == []
        assert detect_claims("Codeforces: codeforces.com/profile/tourist") == []
        assert detect_claims("LeetCode: leetcode.com/u/expert_1900") == []

    def test_decimals_and_abbreviations_stay_whole(self):
        got = {(c["platform"], c["kind"], c["value"]) for c in detect_claims("B.Tech grad, LeetCode rating 1850.5 peak")}
        assert ("leetcode", "rating", 1850) in got

    def test_preview_checks_against_live_like_profiles(self):
        profiles = [
            _found("leetcode", name="lee", rating=2204, title="Guardian", problems_solved=704),
            _found("codeforces", name="Gennady Korotkevich", rating=3408, max_rating=4009,
                   title="legendary grandmaster", max_title="tourist"),
        ]
        status, disc = check_profiles(profiles, detect_claims(PREVIEW_RESUME), "Asha Verma")
        lc_issues = profiles[0]["issues"]
        assert any("rating 2500" in i for i in lc_issues)             # 2500 vs 2204 is overstated
        assert not any("Knight" in i for i in lc_issues)              # Guardian is above Knight
        assert not any("Codeforces expert" in i for i in profiles[1]["issues"])
        assert profiles[1]["name_conflict"] is True                   # Gennady Korotkevich vs Asha Verma
        assert status == "unverified"
