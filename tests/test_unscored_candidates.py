"""
Issue #7: missing scores reach the API as null, never as 0.
"""
import pytest


async def _application(mock_db, job_id, score_details):
    await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {"personal_info": {"full_name": "Jane"}}})
    await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": "c1", "score_details": score_details})


async def _scores(client, job_id):
    cand = (await client.get(f"/api/v1/jobs/{job_id}/candidates")).json()["candidates"][0]
    return cand["jd_match_score"], cand["verification_score"]


@pytest.mark.parametrize("score_details", [{}, None, {"score_source": "verified"}])
async def test_unscored_candidate_has_null_scores(client, mock_db, owned_job_id, score_details):
    await _application(mock_db, owned_job_id, score_details)
    assert await _scores(client, owned_job_id) == (None, None)


async def test_unverified_candidate_keeps_its_match_score(client, mock_db, owned_job_id):
    await _application(mock_db, owned_job_id, {"jd_match_score": 6.5, "score_source": "unverified", "overall_score": 0})
    assert await _scores(client, owned_job_id) == (65.0, None)


async def test_real_zero_scores_stay_zero(client, mock_db, owned_job_id):
    await _application(mock_db, owned_job_id, {"jd_match_score": 0.0, "score_source": "verified", "overall_score": 0})
    assert await _scores(client, owned_job_id) == (0.0, 0)


async def test_records_without_score_source_keep_their_credibility(client, mock_db, owned_job_id):
    await _application(mock_db, owned_job_id, {"jd_match_score": 7, "overall_score": 80})
    assert await _scores(client, owned_job_id) == (70.0, 80)
