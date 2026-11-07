"""
Issue #9: duplicate resumes are matched within the workspace, not per uploader.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.routes import resume

ORG_A, ORG_B = "org-a", "org-b"


@pytest.fixture(autouse=True)
def _no_ai(sample_parsed_resume):
    with patch.object(resume, "parse_resume", AsyncMock(return_value=sample_parsed_resume)), \
         patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 384):
        yield


async def _upload(mock_db, task_id, owner_uid, org_id):
    with open(os.path.join(resume.RESUMES_DIR, f"{task_id}.txt"), "w") as f:
        f.write("Jane Doe resume")
    await mock_db.tasks.insert_one({"task_id": task_id, "status": "processing"})
    return await resume._parse_and_store(f"{task_id}.txt", task_id, owner_uid, org_id)


async def test_teammates_share_one_candidate(mock_db):
    first = await _upload(mock_db, "t1", "alice", ORG_A)
    second = await _upload(mock_db, "t2", "bob", ORG_A)
    assert second == first
    assert await mock_db.candidates.count_documents({}) == 1
    assert (await mock_db.candidates.find_one({}))["org_id"] == ORG_A


async def test_other_workspaces_never_share_a_candidate(mock_db):
    first = await _upload(mock_db, "t1", "alice", ORG_A)
    second = await _upload(mock_db, "t2", "carol", ORG_B)
    assert second != first
    assert await mock_db.candidates.count_documents({}) == 2


async def test_same_user_in_another_workspace_gets_a_new_candidate(mock_db):
    first = await _upload(mock_db, "t1", "alice", ORG_A)
    second = await _upload(mock_db, "t2", "alice", ORG_B)
    assert second != first


async def test_legacy_candidate_without_org_matches_its_uploader_and_is_tagged(mock_db, sample_parsed_resume):
    await mock_db.candidates.insert_one({"candidate_id": "legacy", "owner_uid": "alice", "parsed": sample_parsed_resume})
    assert await _upload(mock_db, "t1", "alice", ORG_A) == "legacy"
    assert (await mock_db.candidates.find_one({"candidate_id": "legacy"}))["org_id"] == ORG_A


async def test_legacy_candidate_is_not_reused_by_another_user(mock_db, sample_parsed_resume):
    await mock_db.candidates.insert_one({"candidate_id": "legacy", "owner_uid": "alice", "parsed": sample_parsed_resume})
    assert await _upload(mock_db, "t1", "mallory", ORG_A) != "legacy"


async def test_unknown_workspace_never_deduplicates(mock_db):
    first = await _upload(mock_db, "t1", "alice", None)
    second = await _upload(mock_db, "t2", "alice", None)
    assert second != first


async def test_queue_passes_the_jobs_workspace(mock_db):
    job_id = str((await mock_db.jobs.insert_one({"org_id": ORG_A})).inserted_id)
    with patch.object(resume, "_parse_and_store", AsyncMock(return_value="c1")) as store, \
         patch.object(resume, "_run_unified_verification", AsyncMock()):
        await resume._parse_and_verify("f.txt", "t1", job_id, "alice")
        await resume._parse_and_verify("f.txt", "t2", str(ObjectId()), "alice")
    assert store.await_args_list[0].args == ("f.txt", "t1", "alice", ORG_A)
    assert store.await_args_list[1].args == ("f.txt", "t2", "alice", None)
