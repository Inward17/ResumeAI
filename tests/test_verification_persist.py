"""
Re-verifying a candidate replaces the stored result: sources that are gone
from the new run must not keep their old data.
"""
from datetime import datetime

from app.models.verification_data_model import VerificationDataModel
from app.services.unified_verification import UnifiedVerificationService


def _service(db):
    svc = UnifiedVerificationService.__new__(UnifiedVerificationService)
    svc.db = db
    return svc


async def test_sources_missing_from_a_new_run_are_cleared(mock_db):
    first_run = datetime(2026, 1, 1)
    await mock_db.verification_data.insert_one({
        "candidateId": "c1", "createdAt": first_run,
        "githubData": {"username": "old"}, "linkedinData": {"profileUrl": "old"},
        "webSearchData": {"status": "success"}, "matchScore": {"overallCredibility": 80},
    })

    await _service(mock_db)._persist_to_db(VerificationDataModel(candidateId="c1"))

    doc = await mock_db.verification_data.find_one({"candidateId": "c1"})
    for field in ("githubData", "linkedinData", "webSearchData", "matchScore"):
        assert field not in doc, field
    assert doc["createdAt"] == first_run
    assert "verificationStatus" in doc


async def test_first_run_is_inserted_with_created_at(mock_db):
    await _service(mock_db)._persist_to_db(VerificationDataModel(candidateId="c2"))
    doc = await mock_db.verification_data.find_one({"candidateId": "c2"})
    assert doc["createdAt"] and doc["updatedAt"]
