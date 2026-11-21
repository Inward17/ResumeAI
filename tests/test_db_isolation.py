"""Tests must never reach a real MongoDB (security review finding 11)."""
from types import SimpleNamespace


async def test_verification_singleton_writes_to_mock_db(mock_db):
    # The module-level service is built at import time, before any patch;
    # it must still resolve the patched app.database.db when it writes.
    from app.services.unified_verification import unified_verification_service

    data = SimpleNamespace(candidateId="isolation-cand", to_mongo_dict=lambda: {"candidateId": "isolation-cand"})
    await unified_verification_service._persist_to_db(data)

    assert await mock_db.verification_data.find_one({"candidateId": "isolation-cand"})


def test_real_client_points_at_unreachable_address():
    from app import database

    assert database.MONGO_URL == "mongodb://127.0.0.1:1"
