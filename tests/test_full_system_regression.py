"""
Full System Regression Tests
=============================
End-to-end and cross-component tests that exercise the complete ResumeAI
pipeline.  Designed to catch regressions when any part of the system changes.

Test categories:
  1. Full Flow (Happy Path)      — Job → Upload → Parse → Verify → Score → Retrieve
  2. Skill Matching Pipeline     — Normalizer → Embedder → Scorer → Pipeline
  3. Resume Route Integration    — Upload, parse, score, application creation
  4. Verification Orchestration  — Concurrent execution, caching, persistence
  5. GitHub Pipeline             — Step isolation, signal fusion, red flags
  6. Data Integrity              — Schema correctness, cross-collection consistency
  7. Edge Cases / Failure Modes  — Empty data, missing fields, service failures

All external APIs are mocked — no real calls to GitHub, Gemini, Apify, etc.
Uses the shared conftest.py fixtures (mock_db, client, sample_*).
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from bson import ObjectId


# ═══════════════════════════════════════════════════════════════════
# 1. FULL PIPELINE FLOW (End-to-End Happy Path)
# ═══════════════════════════════════════════════════════════════════

class TestFullPipelineFlow:
    """
    Tests the golden path: create job → upload resume → parse → verify →
    create application → retrieve candidates with scores.

    This is the MOST IMPORTANT regression test — if this breaks, the
    core product is broken.
    """

    async def test_complete_flow_job_to_candidate_ranking(
        self, client, mock_db, sample_parsed_resume, sample_job_data
    ):
        """
        End-to-end: create job, upload resume, verify background task
        created the right DB records, then retrieve candidates.
        """
        # ── Step 1: Create job ──────────────────────────────────────
        with patch(
            "app.routes.job_routes.db", mock_db
        ), patch(
            "app.services.embedding_service.generate_embedding",
            return_value=[0.1] * 384,
        ):
            resp = await client.post("/api/jobs", json=sample_job_data)
            assert resp.status_code == 200, f"Job creation failed: {resp.text}"
            job = resp.json()
            job_id = job["id"]
            assert job["job_title"] == "Software Engineer"
            assert "Python" in job["required_skills"]

        # ── Step 2: Upload resume ───────────────────────────────────
        with patch(
            "app.routes.resume._parse_and_verify", new_callable=AsyncMock
        ) as mock_pipeline:
            files = [
                ("files", ("resume.pdf", b"fake-pdf", "application/pdf"))
            ]
            resp = await client.post(
                f"/api/v1/jobs/{job_id}/upload", files=files
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "accepted"
            assert len(data["saved"]) == 1
            candidate_id = data["saved"][0]["candidate_id"]
            assert candidate_id  # UUID was generated

            # Verify background task was scheduled
            mock_pipeline.assert_called_once()
            call_args = mock_pipeline.call_args
            assert call_args[0][1] == candidate_id  # candidate_id passed
            assert call_args[0][2] == job_id  # job_id passed

        # ── Step 3: Simulate what the background task does ──────────
        # Insert candidate record (as _parse_and_store would)
        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "filename": f"{candidate_id}_resume.pdf",
            "uploaded_at": datetime.utcnow(),
            "parsed": sample_parsed_resume,
            "status": "verified",
            "github_username": "janedoe",
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "skills_embedding": [0.1] * 384,
        })

        # Insert verification data (as unified_verification would)
        await mock_db.verification_data.insert_one({
            "candidateId": candidate_id,
            "verificationStatus": {
                "github": "verified",
                "linkedin": "verified",
                "webCheck": "verified",
            },
            "matchScore": {
                "overallCredibility": 82.5,
                "skillsMatch": 70,
                "experienceMatch": 85,
            },
            "githubData": {
                "score": 70,
                "github_v2_data": {
                    "repositoryStats": {"total": 15, "original": 12},
                },
            },
        })

        # Insert application (as _create_application would)
        await mock_db.applications.insert_one({
            "candidate_id": candidate_id,
            "job_id": job_id,
            "application_date": datetime.utcnow(),
            "status": "Under Review",
            "score_details": {
                "overall_score": 82.5,
                "skills_match_score": 70,
                "experience_match_score": 85,
                "verification_bonus": 15,
                "score_source": "verified",
                "jd_match_score": 7.4,
                "skill_matches": [
                    {"skill": "Python", "score": 9.2, "found": True,
                     "evidence": {"github": 0.9, "skills": 0.8}},
                    {"skill": "FastAPI", "score": 6.5, "found": True,
                     "evidence": {"experience": 0.7}},
                    {"skill": "MongoDB", "score": 3.1, "found": True,
                     "evidence": {"projects": 0.4}},
                ],
            },
        })

        # ── Step 4: Retrieve candidates ─────────────────────────────
        resp = await client.get(f"/api/v1/jobs/{job_id}/candidates")
        assert resp.status_code == 200
        result = resp.json()
        assert result["job_id"] == job_id
        candidates = result["candidates"]
        assert len(candidates) == 1

        c = candidates[0]
        assert c["candidate_id"] == candidate_id
        assert c["name"] == "Jane Doe"
        assert c["email"] == "jane@example.com"
        assert c["status"] == "Under Review"
        assert c["score_details"]["overall_score"] == 82.5
        assert c["score_details"]["jd_match_score"] == 7.4
        assert len(c["skill_matches"]) == 3
        assert c["verification_status"]["github"] == "verified"

    async def test_multiple_candidates_ranked_correctly(
        self, client, mock_db
    ):
        """Multiple candidates for the same job should all be returned."""
        job_id = "multi-job-123"

        # Insert 3 candidates with different scores
        for i, (name, score) in enumerate([
            ("Alice", 90), ("Bob", 60), ("Charlie", 75)
        ]):
            cid = f"cand-multi-{i}"
            await mock_db.candidates.insert_one({
                "candidate_id": cid,
                "parsed": {
                    "personal_info": {"full_name": name, "email": f"{name.lower()}@test.com"},
                    "skills": "Python",
                },
                "filename": f"{cid}.pdf",
            })
            await mock_db.applications.insert_one({
                "candidate_id": cid,
                "job_id": job_id,
                "application_date": datetime.utcnow(),
                "status": "Under Review",
                "score_details": {
                    "overall_score": score,
                    "skills_match_score": score,
                    "experience_match_score": 0,
                    "verification_bonus": 0,
                    "skill_matches": [],
                },
            })

        resp = await client.get(f"/api/v1/jobs/{job_id}/candidates")
        assert resp.status_code == 200
        candidates = resp.json()["candidates"]
        assert len(candidates) == 3
        names = {c["name"] for c in candidates}
        assert names == {"Alice", "Bob", "Charlie"}


# ═══════════════════════════════════════════════════════════════════
# 2. SKILL MATCHING PIPELINE REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestSkillMatchingPipeline:
    """
    Tests the unified skill scoring pipeline components.
    Catches regressions in: normalizer, section_embedder, evidence_scorer, pipeline.
    """

    def test_normalizer_common_aliases(self):
        """Skill alias normalization must be stable across changes."""
        from app.services.skill_matching.normalizer import normalize_skill

        # Critical aliases that must never change
        assert normalize_skill("GCP") == "google cloud platform"
        assert normalize_skill("AWS") == "amazon web services"
        assert normalize_skill("K8s") == "kubernetes"
        assert normalize_skill("JS") == "javascript"
        assert normalize_skill("TS") == "typescript"
        assert normalize_skill("ReactJS") == "react"
        assert normalize_skill("Node.js") == "node"
        assert normalize_skill("postgres") == "postgresql"
        assert normalize_skill("ML") == "machine learning"
        assert normalize_skill("CI/CD") == "continuous integration continuous deployment"
        assert normalize_skill("py") == "python"
        assert normalize_skill("golang") == "go"

    def test_normalizer_passthrough(self):
        """Unknown skills should pass through as lowercase."""
        from app.services.skill_matching.normalizer import normalize_skill

        assert normalize_skill("FastAPI") == "fastapi"
        assert normalize_skill("Django") == "django"
        assert normalize_skill("Some New Framework") == "some new framework"

    def test_normalizer_case_insensitive(self):
        """Normalization must be case-insensitive."""
        from app.services.skill_matching.normalizer import normalize_skill

        assert normalize_skill("gcp") == normalize_skill("GCP")
        assert normalize_skill("Aws") == normalize_skill("aws")
        assert normalize_skill("K8S") == normalize_skill("k8s")

    def test_section_embedder_extract_skills(self):
        """Skills section extraction must handle both string and list formats."""
        from app.services.skill_matching.section_embedder import extract_section_texts

        # String format
        parsed_str = {"skills": "Python, React, Docker", "experience": [], "projects": []}
        texts = extract_section_texts(parsed_str)
        assert "Python" in texts["skills"]

        # List format
        parsed_list = {"skills": ["Python", "React", "Docker"], "experience": [], "projects": []}
        texts = extract_section_texts(parsed_list)
        assert "Python" in texts["skills"]

    def test_section_embedder_extract_experience(self):
        """Experience extraction must handle both string and dict formats."""
        from app.services.skill_matching.section_embedder import extract_section_texts

        # String entries
        parsed = {
            "skills": "",
            "experience": ["Software Engineer at Google (2021-2024)"],
            "projects": [],
        }
        texts = extract_section_texts(parsed)
        assert "Google" in texts["experience"]

        # Dict entries
        parsed_dict = {
            "skills": "",
            "experience": [{"title": "SWE", "company": "Google", "description": "Built APIs"}],
            "projects": [],
        }
        texts = extract_section_texts(parsed_dict)
        assert "Google" in texts["experience"]
        assert "Built APIs" in texts["experience"]

    def test_section_embedder_extract_projects(self):
        """Project extraction must handle technologies list."""
        from app.services.skill_matching.section_embedder import extract_section_texts

        parsed = {
            "skills": "",
            "experience": [],
            "projects": [{
                "name": "E-commerce Platform",
                "description": "Full-stack web app",
                "technologies": ["Python", "React", "MongoDB"],
            }],
        }
        texts = extract_section_texts(parsed)
        assert "E-commerce" in texts["projects"]
        assert "Python" in texts["projects"]
        assert "MongoDB" in texts["projects"]

    def test_section_embedder_github_data(self):
        """GitHub data extraction from verification results."""
        from app.services.skill_matching.section_embedder import extract_section_texts

        github_v2_data = {
            "resumeVerification": {
                "matches": [
                    {"repoName": "ecommerce-platform", "projectName": "E-Commerce"},
                ],
            },
            "repositoryStats": {"total": 10, "original": 8},
        }
        texts = extract_section_texts({"skills": "", "experience": [], "projects": []}, github_v2_data)
        assert "ecommerce" in texts["github"].lower()
        assert "8 original" in texts["github"]

    def test_section_embedder_missing_fields(self):
        """Pipeline must not crash when fields are None or missing."""
        from app.services.skill_matching.section_embedder import extract_section_texts

        texts = extract_section_texts({})
        assert texts["skills"] == ""
        assert texts["experience"] == ""
        assert texts["projects"] == ""
        assert texts["github"] == ""

    def test_evidence_scorer_weights_sum_to_one(self):
        """Section weights must sum to 1.0 for correct scoring."""
        from app.services.skill_matching.evidence_scorer import SECTION_WEIGHTS

        assert abs(sum(SECTION_WEIGHTS.values()) - 1.0) < 0.001

    def test_evidence_scorer_required_sections(self):
        """All four evidence sections must exist."""
        from app.services.skill_matching.evidence_scorer import SECTION_WEIGHTS

        required = {"github", "experience", "projects", "skills"}
        assert set(SECTION_WEIGHTS.keys()) == required

    def test_evidence_scorer_github_highest_weight(self):
        """GitHub must be the highest-weight section (hardest to fake)."""
        from app.services.skill_matching.evidence_scorer import SECTION_WEIGHTS

        max_section = max(SECTION_WEIGHTS, key=SECTION_WEIGHTS.get)
        assert max_section == "github"

    async def test_score_skill_with_mock_embeddings(self):
        """score_skill must produce valid 0-10 output."""
        from app.services.skill_matching.evidence_scorer import score_skill

        fake_emb = [0.5] * 384

        with patch(
            "app.services.embedding_service.generate_embedding",
            return_value=fake_emb,
        ), patch(
            "app.services.embedding_service.cosine_similarity",
            return_value=0.85,
        ):
            result = await score_skill("Python", {
                "skills": fake_emb,
                "experience": fake_emb,
                "projects": fake_emb,
                "github": fake_emb,
            })
            assert 0 <= result["score"] <= 10
            assert result["skill"] == "Python"
            assert result["canonical"] == "python"
            assert "evidence" in result
            assert isinstance(result["found"], bool)

    async def test_score_all_skills_returns_all(self):
        """score_all_skills must return one result per input skill."""
        from app.services.skill_matching.evidence_scorer import score_all_skills

        fake_emb = [0.5] * 384
        skills = ["Python", "React", "Docker"]

        with patch(
            "app.services.embedding_service.generate_embedding",
            return_value=fake_emb,
        ), patch(
            "app.services.embedding_service.cosine_similarity",
            return_value=0.7,
        ):
            results = await score_all_skills(skills, {"skills": fake_emb})
            assert len(results) == 3
            skill_names = [r["skill"] for r in results]
            assert skill_names == ["Python", "React", "Docker"]

    async def test_unified_pipeline_end_to_end(self):
        """run_unified_skill_scoring must return valid structure."""
        from app.services.skill_matching.pipeline import run_unified_skill_scoring

        fake_emb = [0.5] * 384
        parsed = {
            "skills": "Python, React, Docker",
            "experience": ["SWE at Company"],
            "projects": [{"name": "Project", "description": "A project", "technologies": ["Python"]}],
        }

        with patch(
            "app.services.embedding_service.generate_embedding",
            return_value=fake_emb,
        ), patch(
            "app.services.embedding_service.cosine_similarity",
            return_value=0.75,
        ):
            result = await run_unified_skill_scoring(
                required_skills=["Python", "AWS"],
                parsed=parsed,
            )
            assert "skill_scores" in result
            assert "jd_match_score" in result
            assert len(result["skill_scores"]) == 2
            assert 0 <= result["jd_match_score"] <= 10

    async def test_pipeline_empty_skills_returns_empty(self):
        """Pipeline must handle empty required_skills gracefully."""
        from app.services.skill_matching.pipeline import run_unified_skill_scoring

        result = await run_unified_skill_scoring(
            required_skills=[],
            parsed={"skills": "Python"},
        )
        assert result == {"skill_scores": [], "jd_match_score": 0.0}

    async def test_pipeline_accepts_preferred_skills_kwarg(self):
        """Older callers may pass preferred_skills; pipeline must accept it."""
        from app.services.skill_matching.pipeline import run_unified_skill_scoring

        fake_emb = [0.5] * 384
        parsed = {
            "skills": "Python, Docker",
            "experience": ["Built services in Python"],
            "projects": [{"name": "Infra", "description": "Docker project"}],
        }

        with patch(
            "app.services.embedding_service.generate_embedding",
            return_value=fake_emb,
        ), patch(
            "app.services.embedding_service.cosine_similarity",
            return_value=0.7,
        ):
            result = await run_unified_skill_scoring(
                required_skills=["Python"],
                preferred_skills=["Docker"],
                parsed=parsed,
            )

        assert len(result["skill_scores"]) == 2
        assert [item["skill"] for item in result["skill_scores"]] == ["Python", "Docker"]
        assert 0 <= result["jd_match_score"] <= 10

    async def test_pipeline_failure_returns_zeroed(self):
        """Pipeline must return zeroed results on internal failure (never crash)."""
        from app.services.skill_matching.pipeline import run_unified_skill_scoring

        with patch(
            "app.services.skill_matching.pipeline.extract_section_texts",
            side_effect=Exception("Simulated failure"),
        ):
            result = await run_unified_skill_scoring(
                required_skills=["Python"],
                parsed={"skills": "Python"},
            )
            assert result["skill_scores"] == []
            assert result["jd_match_score"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# 3. RESUME ROUTES REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestResumeRoutesRegression:
    """Tests for resume route invariants that must never break."""

    def test_compute_skill_matches_exact_skills(self):
        """Legacy compute_skill_matches: exact match in skills → score 10."""
        from app.routes.resume import compute_skill_matches

        parsed = {"skills": "Python, React, Docker", "experience": [], "projects": []}
        results = compute_skill_matches(["Python"], parsed)
        assert len(results) == 1
        assert results[0]["skill"] == "Python"
        assert results[0]["score"] == 10
        assert results[0]["found"] is True
        assert results[0]["match_location"] == "skills_section"

    def test_compute_skill_matches_experience(self):
        """Exact match in experience → score 7."""
        from app.routes.resume import compute_skill_matches

        parsed = {
            "skills": "",
            "experience": ["Worked with Kubernetes at Google"],
            "projects": [],
        }
        results = compute_skill_matches(["Kubernetes"], parsed)
        assert results[0]["score"] == 7
        assert results[0]["match_location"] == "experience"

    def test_compute_skill_matches_projects(self):
        """Exact match in projects → score 6."""
        from app.routes.resume import compute_skill_matches

        parsed = {
            "skills": "",
            "experience": [],
            "projects": [{"name": "My App", "description": "Built with Flask", "technologies": ["Flask"]}],
        }
        results = compute_skill_matches(["Flask"], parsed)
        assert results[0]["score"] == 6
        assert results[0]["match_location"] == "projects"

    def test_compute_skill_matches_not_found(self):
        """Skills not in resume → score 0."""
        from app.routes.resume import compute_skill_matches

        parsed = {"skills": "Python", "experience": [], "projects": []}
        results = compute_skill_matches(["Rust"], parsed)
        assert results[0]["score"] == 0
        assert results[0]["found"] is False

    def test_compute_skill_matches_skills_list_format(self):
        """Skills as list (not string) must work."""
        from app.routes.resume import compute_skill_matches

        parsed = {"skills": ["Python", "React"], "experience": [], "projects": []}
        results = compute_skill_matches(["Python"], parsed)
        assert results[0]["score"] == 10

    def test_compute_skill_matches_none_fields(self):
        """None values in parsed data must not crash."""
        from app.routes.resume import compute_skill_matches

        parsed = {"skills": None, "experience": None, "projects": None}
        results = compute_skill_matches(["Python"], parsed)
        assert results[0]["score"] == 0  # Not found, but no crash

    async def test_upload_creates_task_record(self, client, mock_db):
        """Upload must create a task record in the DB."""
        with patch("app.routes.resume._parse_and_verify", new_callable=AsyncMock):
            files = [("files", ("test.pdf", b"content", "application/pdf"))]
            resp = await client.post("/api/v1/jobs/job-task-test/upload", files=files)
            assert resp.status_code == 200
            candidate_id = resp.json()["saved"][0]["candidate_id"]

        task = await mock_db.tasks.find_one({"task_id": candidate_id})
        assert task is not None
        assert task["job_id"] == "job-task-test"
        assert task["status"] == "queued"
        assert task["type"] == "parse_and_verify"

    async def test_candidate_status_update(self, client, mock_db):
        """Status update must modify the application record."""
        job_id = "status-test-job"
        cand_id = "status-test-cand"

        await mock_db.applications.insert_one({
            "candidate_id": cand_id,
            "job_id": job_id,
            "status": "Under Review",
        })

        resp = await client.put(
            f"/api/v1/jobs/{job_id}/candidates/{cand_id}/status",
            json={"status": "Shortlisted"},
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "Shortlisted"

        # Verify DB was updated
        app = await mock_db.applications.find_one({"candidate_id": cand_id})
        assert app["status"] == "Shortlisted"

    async def test_candidate_status_update_not_found(self, client, mock_db):
        """Status update for non-existent application → 404."""
        resp = await client.put(
            "/api/v1/jobs/fake/candidates/fake/status",
            json={"status": "Rejected"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 4. VERIFICATION ORCHESTRATION REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestVerificationOrchestrationRegression:
    """
    Tests UnifiedVerificationService invariants:
    - Concurrent execution of all 3 branches
    - Cache lifecycle (set → merge → clear)
    - Score calculation correctness
    - Failure isolation between branches
    """

    def _make_service(self, mock_db):
        from app.services.unified_verification import (
            UnifiedVerificationService, VerificationCache,
        )
        with patch.object(
            UnifiedVerificationService, "__init__", lambda self, **kw: None
        ):
            svc = UnifiedVerificationService.__new__(UnifiedVerificationService)
            svc.db = mock_db
            svc.github_token = "fake"
            svc.cache = VerificationCache()
            return svc

    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_all_three_sources_concurrent(
        self, mock_web, mock_li, mock_gh, mock_db
    ):
        """All 3 verification sources must be called concurrently."""
        svc = self._make_service(mock_db)

        # Mock GitHub result
        gh_result = MagicMock()
        gh_result.success = True
        gh_result.username = "testuser"
        gh_result.score100 = 80.0
        gh_result.score40 = 32.0
        gh_result.confidenceLevel = "HIGH"
        gh_result.redFlags = []
        gh_result.to_mongo_dict.return_value = {"score100": 80.0}
        mock_gh.return_value = gh_result

        # Mock LinkedIn result
        mock_li.return_value = {
            "status": "success",
            "data": [{
                "profileId": "li-1", "publicIdentifier": "jane",
                "firstName": "Jane", "lastName": "Doe",
                "positions": [], "educations": [], "skills": [],
                "certifications": [],
            }],
        }

        # Mock web search result
        mock_web.return_value = {
            "profile_url": "test",
            "education": {"details": [], "average_score": 85, "overall_tag": "Verified"},
            "experience": {"details": [], "average_score": 90, "overall_tag": "Verified"},
        }

        result = await svc.run_unified_verification(
            candidate_id="cand-all-3",
            github_username="testuser",
            linkedin_url="https://linkedin.com/in/jane",
            profile_data={"publicIdentifier": "jane", "educations": [], "experiences": []},
        )

        # All 3 should have been called
        mock_gh.assert_called_once()
        mock_li.assert_called_once()
        mock_web.assert_called_once()

        # Result should have data from all sources
        assert result.candidateId == "cand-all-3"
        assert result.githubData is not None
        assert result.linkedinData is not None
        assert result.webSearchData is not None
        assert result.matchScore.overallCredibility > 0

    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_github_failure_doesnt_block_others(
        self, mock_web, mock_li, mock_gh, mock_db
    ):
        """If GitHub fails, LinkedIn and web search should still complete."""
        svc = self._make_service(mock_db)

        mock_gh.side_effect = Exception("GitHub API rate limited")
        mock_li.return_value = {"status": "success", "data": []}
        mock_web.return_value = {
            "profile_url": "test",
            "education": {"details": [], "average_score": 70, "overall_tag": "Likely"},
            "experience": {"details": [], "average_score": 80, "overall_tag": "Verified"},
        }

        result = await svc.run_unified_verification(
            candidate_id="cand-gh-fail",
            github_username="testuser",
            linkedin_url="https://linkedin.com/in/test",
            profile_data={"publicIdentifier": "test", "educations": [], "experiences": []},
        )

        # Should NOT crash
        assert result.candidateId == "cand-gh-fail"
        # Web search should still have succeeded
        assert result.verificationStatus.webCheck in ("verified", "pending")

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_cache_cleared_after_persist(self, mock_web, mock_li, mock_db):
        """Cache must be cleared after verification data is persisted."""
        svc = self._make_service(mock_db)

        await svc.run_unified_verification(candidate_id="cand-cache-test")

        # Cache should be empty after completion
        assert svc.cache.get("cand-cache-test") is None

    async def test_verification_data_persisted_to_db(self, mock_db):
        """Verification results must be written to verification_data collection."""
        from app.services.unified_verification import (
            UnifiedVerificationService, VerificationCache,
        )
        with patch.object(
            UnifiedVerificationService, "__init__", lambda self, **kw: None
        ):
            svc = UnifiedVerificationService.__new__(UnifiedVerificationService)
            svc.db = mock_db
            svc.github_token = "fake"
            svc.cache = VerificationCache()

        with patch(
            "app.services.unified_verification.scrape_linkedin_profiles",
            new_callable=AsyncMock,
        ), patch(
            "app.services.unified_verification.verify_profile",
            new_callable=AsyncMock,
        ):
            await svc.run_unified_verification(
                candidate_id="cand-persist",
                profile_data={"publicIdentifier": "test", "educations": [], "experiences": []},
            )

        doc = await mock_db.verification_data.find_one({"candidateId": "cand-persist"})
        assert doc is not None
        assert "verificationStatus" in doc
        assert "matchScore" in doc


# ═══════════════════════════════════════════════════════════════════
# 5. GITHUB PIPELINE REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestGitHubPipelineRegression:
    """Tests the GitHub verification sub-components."""

    def test_repo_stats_computation(self, sample_github_repos):
        """_compute_repo_stats must handle mixed repos correctly."""
        from app.services.github_services_v2.github_service import _compute_repo_stats

        stats = _compute_repo_stats(sample_github_repos, "testuser")
        assert stats.total == 3
        assert stats.forked == 1
        assert stats.original == 2
        assert 0 <= stats.repositoryAuthenticity <= 1.0
        assert 0 <= stats.originalRatio <= 1.0

    def test_repo_stats_empty(self):
        """Empty repo list must return zeroed stats."""
        from app.services.github_services_v2.github_service import _compute_repo_stats

        stats = _compute_repo_stats([], "testuser")
        assert stats.total == 0
        assert stats.repositoryAuthenticity == 0.0

    def test_extract_username_from_url(self):
        """Username extraction must work across different URL formats."""
        from app.services.github_services_v2.github_service import _extract_username

        # Direct key
        assert _extract_username({"github_username": "janedoe"}) == "janedoe"

        # URL in github_username
        assert _extract_username({"github_username": "https://github.com/janedoe"}) == "janedoe"

        # Links array
        assert _extract_username({
            "links": ["https://github.com/janedoe"]
        }) == "janedoe"

        # Social profiles dict
        assert _extract_username({
            "socialProfiles": {"github": "janedoe"}
        }) == "janedoe"

        # Empty / no GitHub
        assert _extract_username({}) is None
        assert _extract_username({"github_username": ""}) is None

    def test_extract_projects(self):
        """Project extraction must filter invalid entries."""
        from app.services.github_services_v2.github_service import _extract_projects

        assert _extract_projects({"projects": [
            {"name": "Valid Project"},
            {"description": "No name"},  # Should be filtered
            "string entry",  # Should be filtered
        ]}) == [{"name": "Valid Project"}]

        assert _extract_projects({}) == []
        assert _extract_projects({"projects": "not a list"}) == []

    def test_select_deep_repos_prioritizes_matched(self, sample_github_repos):
        """Matched repos should be selected first for deep analysis."""
        from app.services.github_services_v2.github_service import _select_deep_repos
        from app.services.github_services_v2.models import ResumeVerificationResult

        mock_rv = MagicMock(spec=ResumeVerificationResult)
        match = MagicMock()
        match.repoName = "my-project"
        mock_rv.matches = [match]
        mock_rv.resumeConsistency = 0.8

        selected = _select_deep_repos(sample_github_repos, mock_rv, "testuser")
        assert len(selected) > 0
        assert selected[0]["name"] == "my-project"

    def test_recency_scoring(self):
        """Recency function must obey the 90/365 day boundaries."""
        from app.services.github_services_v2.github_service import _compute_recency
        from datetime import timezone, timedelta

        now = datetime.now(timezone.utc)

        # Recent push → 1.0
        recent = (now - timedelta(days=30)).isoformat()
        assert _compute_recency(recent) == 1.0

        # Old push → 0.0
        old = (now - timedelta(days=400)).isoformat()
        assert _compute_recency(old) == 0.0

        # No push date → 0.0
        assert _compute_recency(None) == 0.0
        assert _compute_recency("") == 0.0


# ═══════════════════════════════════════════════════════════════════
# 6. JOB ROUTES REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestJobRoutesRegression:
    """Tests job CRUD operations for data consistency."""

    async def test_create_and_retrieve_job(self, client, mock_db):
        """Created job must be retrievable with all fields intact."""
        job_data = {
            "job_title": "Backend Developer",
            "job_description": "Build APIs",
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "experience_level": "Senior",
            "employment_type": "Full-time",
            "location": "Remote",
            "is_active": True,
        }

        with patch(
            "app.routes.job_routes.db", mock_db
        ), patch(
            "app.services.embedding_service.generate_embedding",
            return_value=[0.1] * 384,
        ):
            # Create
            resp = await client.post("/api/jobs", json=job_data)
            assert resp.status_code == 200
            created = resp.json()
            job_id = created["id"]
            assert created["job_title"] == "Backend Developer"
            assert created["required_skills"] == ["Python", "FastAPI"]

            # Retrieve
            resp = await client.get(f"/api/jobs/{job_id}")
            assert resp.status_code == 200
            fetched = resp.json()
            assert fetched["job_title"] == "Backend Developer"
            assert fetched["required_skills"] == ["Python", "FastAPI"]

    async def test_update_job(self, client, mock_db):
        """Job update must only modify specified fields."""
        with patch(
            "app.routes.job_routes.db", mock_db
        ), patch(
            "app.services.embedding_service.generate_embedding",
            return_value=[0.1] * 384,
        ):
            # Create
            resp = await client.post("/api/jobs", json={
                "job_title": "Original Title",
                "job_description": "Original Desc",
                "required_skills": ["Python"],
            })
            job_id = resp.json()["id"]

            # Update title only
            resp = await client.put(f"/api/jobs/{job_id}", json={
                "job_title": "Updated Title",
            })
            assert resp.status_code == 200
            updated = resp.json()
            assert updated["job_title"] == "Updated Title"
            assert updated["job_description"] == "Original Desc"  # Unchanged
            assert updated["required_skills"] == ["Python"]  # Unchanged

    async def test_delete_job(self, client, mock_db):
        """Deleted job must not be retrievable."""
        with patch(
            "app.routes.job_routes.db", mock_db
        ), patch(
            "app.services.embedding_service.generate_embedding",
            return_value=[0.1] * 384,
        ):
            resp = await client.post("/api/jobs", json={
                "job_title": "To Delete",
                "job_description": "Temp",
                "required_skills": [],
            })
            job_id = resp.json()["id"]

            resp = await client.delete(f"/api/jobs/{job_id}")
            assert resp.status_code == 200

            resp = await client.get(f"/api/jobs/{job_id}")
            assert resp.status_code == 404

    async def test_list_jobs_returns_all(self, client, mock_db):
        """GET /api/jobs must return all created jobs."""
        with patch(
            "app.routes.job_routes.db", mock_db
        ), patch(
            "app.services.embedding_service.generate_embedding",
            return_value=[0.1] * 384,
        ):
            for title in ["Job A", "Job B", "Job C"]:
                await client.post("/api/jobs", json={
                    "job_title": title,
                    "job_description": f"Desc for {title}",
                    "required_skills": ["Python"],
                })

            resp = await client.get("/api/jobs")
            assert resp.status_code == 200
            jobs = resp.json()
            assert len(jobs) >= 3

    async def test_invalid_job_id_returns_400(self, client, mock_db):
        """Invalid ObjectId format must return 400."""
        with patch("app.routes.job_routes.db", mock_db):
            resp = await client.get("/api/jobs/not-a-valid-id")
            assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 7. DATA INTEGRITY & CROSS-COMPONENT CONSISTENCY
# ═══════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    """Tests that data flows correctly between components."""

    async def test_create_application_with_full_verification(self, mock_db):
        """_create_application must compute all score fields correctly."""
        from app.routes.resume import _create_application

        candidate_id = "integrity-cand"
        job_id = "a" * 24

        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "parsed": {
                "skills": "Python, React",
                "experience": ["SWE at Google"],
                "projects": [{"name": "App", "description": "Desc", "technologies": ["Python"]}],
            },
        })
        await mock_db.jobs.insert_one({
            "_id": ObjectId(job_id),
            "required_skills": ["Python", "React"],
        })
        await mock_db.verification_data.insert_one({
            "candidateId": candidate_id,
            "verificationStatus": {
                "github": "verified",
                "linkedin": "unverified",
                "webCheck": "verified",
            },
            "matchScore": {"overallCredibility": 75, "skillsMatch": 60, "experienceMatch": 70},
            "githubData": {"score": 60, "github_v2_data": {}},
        })

        mock_scoring = {
            "skill_scores": [
                {"skill": "Python", "score": 8.5, "found": True, "evidence": {}},
                {"skill": "React", "score": 6.0, "found": True, "evidence": {}},
            ],
            "jd_match_score": 7.25,
        }

        with patch("app.routes.resume.db", mock_db), \
             patch("app.routes.resume.run_unified_skill_scoring",
                   new_callable=AsyncMock, return_value=mock_scoring):
            await _create_application(candidate_id, job_id)

        app = await mock_db.applications.find_one({"candidate_id": candidate_id})
        assert app is not None
        sd = app["score_details"]

        # Verification bonus: github(+5) + webCheck(+5) = 10
        assert sd["verification_bonus"] == 10
        assert sd["overall_score"] == 75  # From matchScore.overallCredibility
        assert sd["jd_match_score"] == 7.25
        assert len(sd["skill_matches"]) == 2
        assert sd["score_source"] == "verified"

    async def test_application_stores_skill_matches(self, mock_db):
        """Skill matches computed by unified pipeline must be stored in application."""
        from app.routes.resume import _create_application

        candidate_id = "skill-store-cand"
        job_id = "b" * 24

        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "parsed": {"skills": "Python", "experience": [], "projects": []},
        })
        await mock_db.jobs.insert_one({
            "_id": ObjectId(job_id),
            "required_skills": ["Python"],
        })

        mock_scoring = {
            "skill_scores": [
                {"skill": "Python", "score": 9.0, "found": True,
                 "canonical": "python",
                 "evidence": {"skills": 0.9, "github": 0.8}},
            ],
            "jd_match_score": 9.0,
        }

        with patch("app.routes.resume.db", mock_db), \
             patch("app.routes.resume.run_unified_skill_scoring",
                   new_callable=AsyncMock, return_value=mock_scoring):
            await _create_application(candidate_id, job_id)

        app = await mock_db.applications.find_one({"candidate_id": candidate_id})
        skill_matches = app["score_details"]["skill_matches"]
        assert len(skill_matches) == 1
        assert skill_matches[0]["skill"] == "Python"
        assert skill_matches[0]["score"] == 9.0
        assert "evidence" in skill_matches[0]

    def test_match_score_model_fields(self):
        """MatchScoreModel must have the required fields for score calculation."""
        from app.models.verification_data_model import MatchScoreModel

        score = MatchScoreModel(
            experienceMatch=80,
            skillsMatch=70,
            overallCredibility=75.5,
        )
        assert score.experienceMatch == 80
        assert score.skillsMatch == 70
        assert score.overallCredibility == 75.5

    def test_verification_data_model_to_mongo(self):
        """VerificationDataModel.to_mongo_dict() must produce valid MongoDB document."""
        from app.models.verification_data_model import (
            VerificationDataModel,
            VerificationStatusModel,
            MatchScoreModel,
        )

        model = VerificationDataModel(
            candidateId="test-cand",
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            verificationStatus=VerificationStatusModel(
                linkedin="verified",
                github="unverified",
                webCheck="pending",
            ),
            matchScore=MatchScoreModel(
                experienceMatch=80,
                skillsMatch=70,
                overallCredibility=75,
            ),
        )

        doc = model.to_mongo_dict()
        assert doc["candidateId"] == "test-cand"
        assert "verificationStatus" in doc
        assert "matchScore" in doc


# ═══════════════════════════════════════════════════════════════════
# 8. EDGE CASES & FAILURE MODES
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCasesAndFailures:
    """Tests that the system handles edge cases gracefully."""

    async def test_upload_unsupported_format_rejected(self, client):
        """Unsupported file formats must be rejected with 400."""
        files = [("files", ("resume.xlsx", b"content", "application/excel"))]
        resp = await client.post("/api/v1/jobs/job-1/upload", files=files)
        assert resp.status_code == 400

    async def test_empty_candidates_list(self, client):
        """GET candidates for job with no applications must return empty list."""
        resp = await client.get("/api/v1/jobs/nonexistent-job/candidates")
        assert resp.status_code == 200
        assert resp.json()["candidates"] == []

    async def test_health_check_always_works(self, client):
        """Root endpoint must always return 200 regardless of DB state."""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "resumeai-backend"
        assert "time" in data

    def test_extract_github_username_edge_cases(self):
        """GitHub username extraction must handle all edge cases."""
        from app.routes.resume import extract_github_username

        assert extract_github_username(None) is None
        assert extract_github_username("") is None
        assert extract_github_username("  ") == ""  # Whitespace-only
        assert extract_github_username("https://github.com/user/") == "user"
        assert extract_github_username("user") == "user"

    def test_extract_linkedin_url_edge_cases(self):
        """LinkedIn URL extraction must handle all formats."""
        from app.routes.resume import extract_linkedin_url

        assert extract_linkedin_url(None) is None
        assert extract_linkedin_url("") is None
        assert extract_linkedin_url("https://www.linkedin.com/in/user") == "https://www.linkedin.com/in/user"
        assert "linkedin.com" in extract_linkedin_url("user")

    async def test_verification_with_no_sources(self, client):
        """Verification request with no sources must return 400."""
        resp = await client.post(
            "/api/v1/verification/verify-candidate",
            json={"candidate_id": "test"},
        )
        assert resp.status_code == 400

    async def test_verification_status_nonexistent(self, client):
        """Checking status of non-existent verification must return not_found."""
        resp = await client.get("/api/v1/verification/verification-status/does-not-exist")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    def test_compute_skill_matches_empty_resume(self):
        """Skill matching against completely empty resume must not crash."""
        from app.routes.resume import compute_skill_matches

        parsed = {}
        results = compute_skill_matches(["Python", "React"], parsed)
        assert len(results) == 2
        assert all(r["score"] == 0 for r in results)

    def test_compute_skill_matches_empty_skills_list(self):
        """Empty required skills list must return empty results."""
        from app.routes.resume import compute_skill_matches

        results = compute_skill_matches([], {"skills": "Python"})
        assert results == []

    async def test_pipeline_handles_none_github_data(self):
        """Skill scoring pipeline must work without GitHub data."""
        from app.services.skill_matching.pipeline import run_unified_skill_scoring

        fake_emb = [0.5] * 384

        with patch(
            "app.services.embedding_service.generate_embedding",
            return_value=fake_emb,
        ), patch(
            "app.services.embedding_service.cosine_similarity",
            return_value=0.6,
        ):
            result = await run_unified_skill_scoring(
                required_skills=["Python"],
                parsed={"skills": "Python", "experience": [], "projects": []},
                github_v2_data=None,  # Explicitly None
            )
            assert len(result["skill_scores"]) == 1
            assert 0 <= result["jd_match_score"] <= 10

    async def test_job_delete_nonexistent_returns_404(self, client, mock_db):
        """Deleting non-existent job must return 404."""
        valid_oid = "a" * 24
        with patch("app.routes.job_routes.db", mock_db):
            resp = await client.delete(f"/api/jobs/{valid_oid}")
            assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 9. MATCH SCORE CALCULATION REGRESSION
# ═══════════════════════════════════════════════════════════════════

class TestMatchScoreCalculation:
    """Tests the overallCredibility formula must remain stable."""

    def _make_service(self):
        from app.services.unified_verification import (
            UnifiedVerificationService, VerificationCache,
        )
        with patch.object(
            UnifiedVerificationService, "__init__", lambda self, **kw: None
        ):
            svc = UnifiedVerificationService.__new__(UnifiedVerificationService)
            svc.cache = VerificationCache()
            return svc

    def test_all_sources_weighted_average(self):
        """GitHub(50%) + LinkedIn(20%) + Web(30%) must produce correct average."""
        from app.models.verification_data_model import (
            GitHubDataModel, LinkedInDataModel, WebSearchDataModel,
            WebSearchResult, ExperienceVerification,
        )

        svc = self._make_service()
        gh = GitHubDataModel(success=True, score=80.0)
        li = LinkedInDataModel(profileId="li-1")
        web = WebSearchDataModel(
            status="success",
            results=[WebSearchResult(
                experience=ExperienceVerification(average_score=90),
            )],
        )

        result = svc._calculate_match_scores(gh, li, web)
        # 80*0.5 + 100*0.2 + 90*0.3 = 40 + 20 + 27 = 87
        assert abs(result.overallCredibility - 87.0) < 1.0

    def test_partial_sources_weight_redistribution(self):
        """Missing sources should be excluded from denominator."""
        from app.models.verification_data_model import GitHubDataModel

        svc = self._make_service()
        gh = GitHubDataModel(success=True, score=80.0)

        result = svc._calculate_match_scores(gh, None, None)
        # Only GitHub: 80*0.5 / 0.5 = 80
        assert abs(result.overallCredibility - 80.0) < 1.0

    def test_zero_score_with_no_sources(self):
        """No sources → overallCredibility must be 0."""
        svc = self._make_service()
        result = svc._calculate_match_scores(None, None, None)
        assert result.overallCredibility == 0
