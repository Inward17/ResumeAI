"""
Regression tests for the workflow bugs fixed on 2026-10-30:
job edits, job deletion, unverified credibility and interview evaluations.
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

EMBEDDING = "app.services.embedding_service.generate_embedding"


@pytest.fixture
async def job_id(client, sample_job_data):
    with patch(EMBEDDING, return_value=[0.0] * 384):
        resp = await client.post("/api/jobs", json={**sample_job_data, "department": "Engineering", "salary_min": 100})
    return resp.json()["id"]


async def _apply(mock_db, job_id, candidate_id="c1", status="Under Review", source="verified", overall=80):
    await mock_db.candidates.insert_one({"candidate_id": candidate_id, "parsed": {"personal_info": {"full_name": "Jane"}}})
    await mock_db.applications.insert_one({
        "job_id": job_id, "candidate_id": candidate_id, "status": status, "application_date": datetime.utcnow(),
        "score_details": {"overall_score": overall, "score_source": source, "jd_match_score": 7},
    })


class TestJobEdit:
    async def test_optional_fields_can_be_cleared(self, client, job_id):
        with patch(EMBEDDING, return_value=[0.0] * 384):
            resp = await client.put(f"/api/jobs/{job_id}", json={"department": None, "salary_min": None})
        assert resp.status_code == 200
        assert resp.json()["department"] is None
        assert resp.json()["salary_min"] is None
        assert resp.json()["job_title"] == "Software Engineer"

    async def test_text_change_refreshes_embedding(self, client, job_id, mock_db):
        with patch(EMBEDDING, return_value=[1.0] * 384) as embed:
            await client.put(f"/api/jobs/{job_id}", json={"required_skills": ["Go"]})
        assert "Go" in embed.call_args.args[0]
        job = await mock_db.jobs.find_one({})
        assert job["jd_embedding"] == [1.0] * 384

    async def test_status_only_change_skips_embedding(self, client, job_id, sample_job_data):
        # The frontend resends unchanged text fields along with the new status
        with patch(EMBEDDING) as embed:
            await client.put(f"/api/jobs/{job_id}", json={**sample_job_data, "status": "Closed"})
        embed.assert_not_called()


class TestJobDelete:
    async def test_pipeline_and_queued_tasks_removed(self, client, job_id, mock_db):
        await _apply(mock_db, job_id)
        await mock_db.evaluations.insert_one({"job_id": job_id, "candidate_id": "c1"})
        await mock_db.tasks.insert_many([{"job_id": job_id, "status": "queued"}, {"job_id": job_id, "status": "done"}])

        assert (await client.delete(f"/api/jobs/{job_id}")).status_code == 200
        assert await mock_db.applications.count_documents({"job_id": job_id}) == 0
        assert await mock_db.evaluations.count_documents({"job_id": job_id}) == 0
        assert await mock_db.tasks.count_documents({"job_id": job_id, "status": "queued"}) == 0
        assert await mock_db.candidates.count_documents({"candidate_id": "c1"}) == 1


class TestCandidateScores:
    async def test_unverified_credibility_is_null(self, client, job_id, mock_db):
        await _apply(mock_db, job_id, source="unverified", overall=0)
        cand = (await client.get(f"/api/v1/jobs/{job_id}/candidates")).json()["candidates"][0]
        assert cand["verification_score"] is None
        assert cand["interview_score"] is None

    async def test_hired_counts_as_shortlisted(self, client, job_id, mock_db):
        await _apply(mock_db, job_id, status="Hired")
        assert (await client.get(f"/api/jobs/{job_id}")).json()["shortlisted"] == 1


class TestEvaluation:
    BODY = {"questions": [{"question_id": 1, "question": "Q", "total_tags": 2, "selected_tags": ["a"], "score": 0.5}],
            "total_score": 50, "total_selected": 1, "total_possible": 2}

    async def test_submit_moves_to_interview_and_shows_score(self, client, job_id, mock_db):
        await _apply(mock_db, job_id, status="Shortlisted")
        resp = await client.post(f"/api/jobs/{job_id}/candidates/c1/evaluation", json=self.BODY)
        assert resp.json()["candidate_status"] == "Interview"
        cand = (await client.get(f"/api/v1/jobs/{job_id}/candidates")).json()["candidates"][0]
        assert cand["status"] == "Interview"
        assert cand["interview_score"] == 50

    async def test_later_stage_is_kept(self, client, job_id, mock_db):
        await _apply(mock_db, job_id, status="Offer")
        resp = await client.post(f"/api/jobs/{job_id}/candidates/c1/evaluation", json=self.BODY)
        assert resp.json()["candidate_status"] is None
        assert (await mock_db.applications.find_one({}))["status"] == "Offer"


class TestAIServiceDown:
    async def test_interview_questions_report_outage(self, client, job_id, mock_db):
        await _apply(mock_db, job_id)
        with patch("app.routes.interview_questions_routes.generate_interview_questions", return_value=None):
            resp = await client.get(f"/api/jobs/{job_id}/candidates/c1/interview-questions")
        assert resp.status_code == 503
        assert "AI service is down" in resp.json()["detail"]

    async def test_fact_checker_reports_outage(self, client, job_id, mock_db):
        from app.services.fact_checker_service import AIServiceUnavailable
        await _apply(mock_db, job_id)
        with patch("app.routes.fact_checker_routes.fact_check", side_effect=AIServiceUnavailable("HTTP 404")):
            resp = await client.post("/api/fact-checker/c1", json={"message": "Is this verified?"})
        assert resp.status_code == 503
        assert "AI service is down" in resp.json()["detail"]

    async def test_groq_failure_raises_instead_of_answering(self):
        from app.services import fact_checker_service as fc
        with patch.object(fc, "GROQ_API_KEY", ""), patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            with pytest.raises(fc.AIServiceUnavailable):
                await fc._call_groq("system", "user")

    async def test_usage_flags_retired_groq_model(self):
        from unittest.mock import MagicMock
        from app.services import usage_service
        resp = MagicMock()
        resp.json.return_value = {"data": [{"id": "some-other-model"}]}
        http = MagicMock()
        http.get = AsyncMock(return_value=resp)
        result = await usage_service._groq(http)
        assert result["status"] == "error"
        assert "no longer available" in result["error"]


class TestSkillScoring:
    """Skills written on the resume must score high, even without GitHub or projects."""

    PARSED = {"skills": ["SQL", "Python"], "experience": ["Data Analyst: built SQL reports in Python."]}

    async def _score(self, skills, sim):
        from app.services.skill_matching.evidence_scorer import score_all_skills
        from app.services.skill_matching.section_embedder import extract_section_texts
        texts = extract_section_texts(self.PARSED)
        embeddings = {k: [0.1] * 384 for k, v in texts.items() if v}
        with patch("app.services.embedding_service.generate_embedding", return_value=[0.1] * 384), \
             patch("app.services.embedding_service.cosine_similarity", return_value=sim):
            return await score_all_skills(skills, embeddings, texts)

    async def test_listed_skill_scores_full_marks(self):
        [sql] = await self._score(["SQL"], sim=0.4)
        assert sql["score"] == 10 and sql["found"]

    async def test_unlisted_skill_with_weak_similarity_is_not_found(self):
        [dbt] = await self._score(["dbt"], sim=0.4)
        assert dbt["score"] < 3 and not dbt["found"]

    async def test_short_names_need_exact_case(self):
        from app.services.skill_matching.evidence_scorer import _mentions
        assert _mentions("Backend services in Go and C++", ["Go"])
        assert _mentions("Backend services in Go and C++", ["C++"])
        assert not _mentions("ready to go live", ["Go"])
        assert not _mentions("MySQL admin", ["SQL"])
