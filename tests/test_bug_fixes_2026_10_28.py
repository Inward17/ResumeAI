"""
Regression tests for the critical/high bugs in docs/BUGS_FOUND_2026-10-28.md.
Each test is named after its bug ID.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from tests.conftest import create_owned_job


def _service():
    from app.services.unified_verification import UnifiedVerificationService, VerificationCache
    svc = UnifiedVerificationService.__new__(UnifiedVerificationService)
    svc.cache = VerificationCache()
    svc.db = None
    svc._persist_to_db = AsyncMock()
    return svc


def _linkedin_profile(**overrides):
    profile = {
        "profileId": "li-1", "firstName": "Jane", "lastName": "Doe",
        "positions": [{"title": "Software Engineer", "companyName": "Google"}],
        "educations": [{"schoolName": "IIT Delhi"}],
    }
    profile.update(overrides)
    return profile


class TestBE01WebSearchCounts:
    async def test_verified_web_results_raise_credibility(self, sample_verification_result):
        svc = _service()
        svc.cache.set("c", "github", None)
        svc.cache.set("c", "linkedin", None)
        svc.cache.set("c", "webSearch", sample_verification_result)  # edu 85, exp 90
        result = await svc._build_and_persist("c")
        assert result.matchScore.experienceMatch == 90
        assert result.matchScore.overallCredibility == pytest.approx(87.5)
        web = result.webSearchData.results[0]
        assert web.education.details[0].college == "IIT Delhi"
        assert web.experience.details[0].company == "Google"

    async def test_web_check_with_no_entities_does_not_drag_score(self):
        svc = _service()
        gh = MagicMock(spec=["to_mongo_dict", "success", "username", "score100", "score40",
                             "confidenceLevel", "redFlags"])
        gh.success, gh.username, gh.score100, gh.score40 = True, "jane", 80.0, 32
        gh.confidenceLevel, gh.redFlags = "HIGH", []
        gh.to_mongo_dict.return_value = {}
        svc.cache.set("c", "github", gh)
        svc.cache.set("c", "linkedin", None)
        svc.cache.set("c", "webSearch", {
            "profile_url": "c",
            "education": {"details": [], "average_score": 0, "overall_tag": "Not Found"},
            "experience": {"details": [], "average_score": 0, "overall_tag": "Not Found"},
        })
        result = await svc._build_and_persist("c")
        assert result.matchScore.overallCredibility == 80.0


class TestBE02WebSearchEntities:
    def test_searches_institutions_and_companies_not_whole_lines(self):
        from app.routes.resume import _verification_entities
        universities, companies = _verification_entities({
            "education": ["B.Tech in Computer Science, IIT Delhi, 2021",
                          "M.Sc Cognitive Science, Pune University (2023)"],
            "experience": ["Software Engineer at Google (2021-2024) - Built scalable microservices"],
        })
        assert universities == ["IIT Delhi", "Pune University"]
        assert companies == ["Google"]

    def test_prefers_parser_entity_lists(self):
        from app.routes.resume import _verification_entities
        assert _verification_entities({"university": ["MIT"], "company": ["Acme", "Acme"],
                                       "education": ["ignored"]}) == (["MIT"], ["Acme"])

    async def test_verification_receives_clean_names(self, mock_db, sample_parsed_resume):
        from app.routes import resume
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": sample_parsed_resume})
        await mock_db.tasks.insert_one({"task_id": "c1", "status": "parsed"})
        run = AsyncMock(return_value=None)
        with patch.object(resume.unified_verification_service, "run_unified_verification", run), \
             patch.object(resume, "_create_application", AsyncMock()):
            await resume._run_unified_verification("c1", "job-1")
        profile = run.call_args.kwargs["profile_data"]
        assert profile["educations"] == [{"schoolName": "IIT Delhi"}]
        assert profile["experiences"] == [{"companyName": "Google"}]


class TestBE03AgentModeFallsBack:
    async def test_agent_flag_uses_standard_verification(self, mock_db, sample_parsed_resume, monkeypatch):
        from app.routes import resume
        monkeypatch.setenv("USE_AGENT_SYSTEM", "true")
        monkeypatch.setattr(resume, "_agent_loop_unavailable", False)
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": sample_parsed_resume,
                                             "github_username": "janedoe"})
        await mock_db.tasks.insert_one({"task_id": "c1", "status": "parsed"})
        verification = MagicMock()
        verification.matchScore.overallCredibility = 70
        verification.to_mongo_dict.return_value = {"matchScore": {"overallCredibility": 70}}
        run = AsyncMock(return_value=verification)
        with patch.object(resume.unified_verification_service, "run_unified_verification", run), \
             patch.object(resume, "_create_application", AsyncMock()):
            await resume._run_unified_verification("c1", "job-1")
        run.assert_awaited_once()
        assert (await mock_db.tasks.find_one({"task_id": "c1"}))["status"] == "done"


class TestBE04RepoSizeInKilobytes:
    def test_commit_depth_uses_kb(self):
        from app.services.github_services_v2.github_service import _compute_repo_stats
        repos = [{"name": "service", "fork": False, "size": 500, "pushed_at": None}]  # 500 KB
        stats = _compute_repo_stats(repos, "jane")
        assert stats.avgCommitsPerRepo == 50.0  # ~10 KB per commit, was 0.05


class TestBE05OssContributions:
    async def test_contribution_via_own_fork_is_detected(self):
        from app.services.github_services_v2.analysis.behavioral_analysis import _detect_oss_contributions
        client = MagicMock()
        client.get_repo_info = AsyncMock(return_value={"parent": {"name": "django", "owner": {"login": "django"}}})
        client.get_repo_commits = AsyncMock(return_value=[{"sha": "abc"}])
        repos = [{"name": "django", "fork": True, "owner": {"login": "jane"}}]
        result = await _detect_oss_contributions("jane", repos, client)
        assert result["external_contributions"] == 1
        assert result["external_org_list"] == ["django"]
        client.get_repo_commits.assert_awaited_once_with("django", "django", "jane", max_commits=5)

    async def test_number_of_checks_is_capped(self):
        from app.services.github_services_v2.analysis import behavioral_analysis as ba
        client = MagicMock()
        client.get_repo_info = AsyncMock(return_value={})
        client.get_repo_commits = AsyncMock(return_value=[])
        repos = [{"name": f"r{i}", "fork": False, "owner": {"login": "org"}} for i in range(50)]
        await ba._detect_oss_contributions("jane", repos, client)
        assert client.get_repo_commits.await_count == ba.MAX_OSS_REPO_CHECKS


class TestBE06RoleMatchIsJdMatch:
    async def test_candidate_list_returns_real_jd_match_and_profile(self, client, mock_db, owned_job_id,
                                                                    sample_parsed_resume):
        await mock_db.candidates.insert_one({
            "candidate_id": "c1", "parsed": sample_parsed_resume,
            "github_username": "janedoe", "linkedin_url": "https://linkedin.com/in/janedoe",
        })
        await mock_db.applications.insert_one({
            "candidate_id": "c1", "job_id": owned_job_id, "status": "reviewing",
            "application_date": datetime.utcnow(),
            "score_details": {"jd_match_score": 7.25, "skills_match_score": 40, "overall_score": 66},
        })
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        c = resp.json()["candidates"][0]
        assert c["jd_match_score"] == 72.5          # was 40 (the GitHub score)
        assert c["github_score"] == 40
        assert c["verification_score"] == 66
        assert c["skills"] == ["Python", "FastAPI", "React", "Docker"]
        assert c["education"] == ["B.Tech in CS, IIT Delhi, 2021"]
        assert c["github_url"] == "https://github.com/janedoe"
        assert c["linkedin_url"] == "https://linkedin.com/in/janedoe"
        assert c["status"] == "Under Review"        # legacy value normalised

    async def test_status_must_be_canonical(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "c1", "job_id": owned_job_id})
        bad = await client.put(f"/api/v1/jobs/{owned_job_id}/candidates/c1/status", json={"status": "Maybe"})
        assert bad.status_code == 400
        ok = await client.put(f"/api/v1/jobs/{owned_job_id}/candidates/c1/status", json={"status": "shortlisted"})
        assert ok.json()["new_status"] == "Shortlisted"


class TestBE07LinkedInComparedWithResume:
    async def _run(self, linkedin, parsed):
        svc = _service()
        svc.cache.set("c", "resume", parsed)
        svc.cache.set("c", "github", None)
        svc.cache.set("c", "webSearch", None)
        svc.cache.set("c", "linkedin", linkedin)
        return await svc._build_and_persist("c")

    async def test_matching_profile_is_verified(self, sample_parsed_resume):
        result = await self._run(_linkedin_profile(), sample_parsed_resume)
        assert result.matchScore.linkedinMatch == 100
        assert result.verificationStatus.linkedin == "verified"
        assert result.verificationStatus.discrepancies == []

    async def test_mismatches_are_reported_and_lower_the_score(self, sample_parsed_resume):
        result = await self._run(
            _linkedin_profile(firstName="John", lastName="Smith",
                              positions=[{"companyName": "Initech"}]),
            sample_parsed_resume,
        )
        assert result.matchScore.linkedinMatch == pytest.approx(33.33, abs=0.01)  # only the university agrees
        assert result.verificationStatus.linkedin == "unverified"
        fields = sorted(d.field for d in result.verificationStatus.discrepancies)
        assert fields == ["experience", "name"]
        assert result.matchScore.overallCredibility == pytest.approx(33.33, abs=0.01)


class TestFE02JobStatusAndDetails:
    async def test_draft_job_is_not_published(self, client, mock_db, sample_job_data):
        payload = {**sample_job_data, "status": "Draft", "department": "Platform",
                   "salary_min": 100000, "salary_max": 150000}
        with patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 384):
            resp = await client.post("/api/jobs", json=payload)
        job = resp.json()
        assert (job["status"], job["is_active"]) == ("Draft", False)
        assert (job["department"], job["salary_min"], job["salary_max"]) == ("Platform", 100000, 150000)

        resp = await client.put(f"/api/jobs/{job['id']}", json={"status": "Active"})
        assert (resp.json()["status"], resp.json()["is_active"]) == ("Active", True)

    async def test_legacy_job_status_derived_from_is_active(self, client, mock_db):
        job_id = await create_owned_job(mock_db, is_active=False)
        resp = await client.get(f"/api/jobs/{job_id}")
        assert resp.json()["status"] == "Closed"
