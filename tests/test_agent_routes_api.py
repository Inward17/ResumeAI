"""
test_routes_api.py (agent endpoints) — Section 15

End-to-end HTTP tests for agent routes using mongomock-motor.
All external API calls are mocked.

NOTE: The project already has a tests/test_routes_api.py for legacy routes.
      This file covers ONLY the agent routes added in agent_routes.py.
      It is named with _agent suffix to avoid collision.
"""

import pytest
import os
from unittest.mock import AsyncMock, patch


# ===========================================================================
# Tests
# ===========================================================================
class TestAgentRoutes:

    @pytest.mark.asyncio
    async def test_verify_disabled_when_flag_off(self, client):
        """POST /api/v1/agent/verify returns disabled when USE_AGENT_SYSTEM=false."""
        with patch.dict(os.environ, {"USE_AGENT_SYSTEM": "false"}):
            resp = await client.post("/api/v1/agent/verify", json={
                "candidate_id": "cand-1",
                "job_id": "job-1",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_verify_calls_agent_loop_when_enabled(self, client):
        """POST /api/v1/agent/verify calls agent_loop.run when enabled."""
        mock_summary = {
            "candidate_id": "cand-1",
            "actions_taken": ["github"],
            "signals_skipped": ["linkedin"],
            "plan_source": "rule",
            "run_id": "test-run-id",
            "run_duration_ms": 500,
            "status": "complete",
            "results": {},
        }

        with patch.dict(os.environ, {"USE_AGENT_SYSTEM": "true", "DUAL_RUN": "false"}), \
             patch("app.routes.agent_routes.agent_loop.run",
                   new_callable=AsyncMock, return_value=mock_summary):
            resp = await client.post("/api/v1/agent/verify", json={
                "candidate_id": "cand-1",
                "job_id": "job-1",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["run_id"] == "test-run-id"

    @pytest.mark.asyncio
    async def test_verify_dual_run_serves_legacy(self, client, mock_db):
        """DUAL_RUN=true runs both but serves legacy result."""
        legacy_result = {"githubData": {"confidence_score": 0.85}, "matchScore": {"tier": "A"}}
        agent_summary = {"run_id": "agent-123", "actions_taken": ["github"]}

        with patch.dict(os.environ, {"USE_AGENT_SYSTEM": "true", "DUAL_RUN": "true"}), \
             patch("app.routes.agent_routes._run_legacy",
                   new_callable=AsyncMock, return_value=legacy_result), \
             patch("app.routes.agent_routes.agent_loop.run",
                   new_callable=AsyncMock, return_value=agent_summary):
            resp = await client.post("/api/v1/agent/verify", json={
                "candidate_id": "cand-1",
                "job_id": "job-1",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "dual_run"
        assert data["data"]["matchScore"]["tier"] == "A"  # legacy result served

    @pytest.mark.asyncio
    async def test_plan_endpoint_404_when_no_runs(self, client):
        """GET /api/v1/agent/plan/{cid} returns 404 when no agent runs exist."""
        resp = await client.get("/api/v1/agent/plan/nonexistent-cand")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_plan_endpoint_returns_latest_run(self, client, mock_db):
        """GET /api/v1/agent/plan/{cid} returns the most recent agent run."""
        from datetime import datetime

        await mock_db.agent_runs.insert_one({
            "candidate_id": "cand-1",
            "run_id": "run-latest",
            "job_id": "job-1",
            "timestamp": datetime.utcnow(),
            "plan_source": "rule",
            "actions_taken": ["github"],
            "signals_skipped": ["linkedin"],
            "run_duration_ms": 300,
        })

        # Patch agent_runs_col to use mock_db
        with patch("app.routes.agent_routes.agent_runs_col", mock_db.agent_runs):
            resp = await client.get("/api/v1/agent/plan/cand-1")

        assert resp.status_code == 200
        assert resp.json()["data"]["run_id"] == "run-latest"

    @pytest.mark.asyncio
    async def test_status_endpoint_404(self, client):
        """GET /api/v1/agent/status/{cid} returns 404 when no runs."""
        resp = await client.get("/api/v1/agent/status/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_structured_data(self, client, mock_db):
        """GET /api/v1/agent/status/{cid} returns structured run data."""
        from datetime import datetime

        await mock_db.agent_runs.insert_one({
            "candidate_id": "cand-2",
            "run_id": "run-status",
            "job_id": "job-2",
            "timestamp": datetime.utcnow(),
            "plan_source": "llm",
            "actions_taken": ["github", "web_search"],
            "signals_skipped": [],
            "run_duration_ms": 1200,
        })

        with patch("app.routes.agent_routes.agent_runs_col", mock_db.agent_runs):
            resp = await client.get("/api/v1/agent/status/cand-2")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["run_id"] == "run-status"
        assert data["plan_source"] == "llm"
        assert "github" in data["actions_taken"]
