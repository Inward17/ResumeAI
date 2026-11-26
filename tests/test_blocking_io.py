"""Disk caches and resume reads run in a thread, off the event loop (issue #77)."""
import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np

from app.routes import resume
from app.services.github_services_v2 import github_client
from app.services.github_services_v2.analysis import code_similarity


def _spy():
    """Wrap asyncio.to_thread, recording the functions sent to a thread."""
    calls, real = [], asyncio.to_thread

    async def to_thread(fn, *args, **kwargs):
        calls.append(fn)
        return await real(fn, *args, **kwargs)
    return calls, patch("asyncio.to_thread", to_thread)


async def test_search_cache_round_trip_in_a_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(github_client, "SEARCH_CACHE_DIR", str(tmp_path))
    client = github_client.GitHubClient(token="fake-token")
    try:
        client._save_search_cache("fastapi todo", [{"full_name": "a/b"}])
        calls, spy = _spy()
        with spy:
            assert await client.search_similar_repos("fastapi todo") == [{"full_name": "a/b"}]
        assert [getattr(f, "__name__", "") for f in calls] == ["_load_search_cache"]
    finally:
        await client.close()


async def test_embedding_disk_cache_round_trip_and_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(code_similarity, "EMBEDDING_CACHE_DIR", str(tmp_path))
    emb = np.arange(4, dtype=np.float32)
    calls, spy = _spy()
    with spy:
        await code_similarity._EmbeddingCache().put_many([("chunk a", emb)])
        fresh = code_similarity._EmbeddingCache()  # empty memory: must come from disk
        got = await fresh.get_many(["chunk a", "chunk b"])
    assert np.array_equal(got[0], emb) and got[1] is None
    assert len(calls) == 2

    key = fresh._key("chunk a")
    (tmp_path / f"{key}.meta").write_text((datetime.now() - timedelta(days=365)).isoformat())
    assert code_similarity._disk_load(key) is None
    assert not (tmp_path / f"{key}.npy").exists()


def test_read_bytes(tmp_path):
    path = tmp_path / "r.txt"
    path.write_bytes(b"resume")
    assert resume._read_bytes(os.fspath(path)) == b"resume"
