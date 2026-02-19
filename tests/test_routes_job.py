"""
Tests for Job routes — full CRUD with mocked MongoDB.
"""
import pytest
from bson import ObjectId


class TestJobRoutes:
    """Tests for /api/jobs endpoints."""

    async def _clean_db(self, mock_db):
        """Clean jobs collection before each test."""
        await mock_db.jobs.delete_many({})

    async def test_create_job(self, client, sample_job_data, mock_db):
        await self._clean_db(mock_db)
        resp = await client.post("/api/jobs", json=sample_job_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_title"] == "Software Engineer"
        assert data["is_active"] is True
        assert "id" in data
        assert "posted_at" in data

    async def test_create_job_minimal(self, client):
        job = {
            "job_title": "Intern",
            "job_description": "Internship position",
            "required_skills": ["Python"],
        }
        resp = await client.post("/api/jobs", json=job)
        assert resp.status_code == 200
        assert resp.json()["job_title"] == "Intern"

    async def test_create_job_missing_fields(self, client):
        resp = await client.post("/api/jobs", json={"job_title": "Test"})
        assert resp.status_code == 422  # Validation error

    async def test_get_jobs_empty(self, client, mock_db):
        await self._clean_db(mock_db)
        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_jobs_after_create(self, client, sample_job_data, mock_db):
        await self._clean_db(mock_db)
        await client.post("/api/jobs", json=sample_job_data)
        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["job_title"] == "Software Engineer"

    async def test_get_single_job(self, client, sample_job_data):
        create_resp = await client.post("/api/jobs", json=sample_job_data)
        job_id = create_resp.json()["id"]

        resp = await client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["job_title"] == "Software Engineer"

    async def test_get_job_not_found(self, client):
        fake_id = str(ObjectId())
        resp = await client.get(f"/api/jobs/{fake_id}")
        assert resp.status_code == 404

    async def test_get_job_invalid_id(self, client):
        resp = await client.get("/api/jobs/not-a-valid-id")
        assert resp.status_code == 400

    async def test_update_job(self, client, sample_job_data):
        create_resp = await client.post("/api/jobs", json=sample_job_data)
        job_id = create_resp.json()["id"]

        update = {"job_title": "Senior Software Engineer", "location": "NYC"}
        resp = await client.put(f"/api/jobs/{job_id}", json=update)
        assert resp.status_code == 200
        assert resp.json()["job_title"] == "Senior Software Engineer"
        assert resp.json()["location"] == "NYC"
        # Unchanged fields preserved
        assert resp.json()["required_skills"] == ["Python", "FastAPI", "MongoDB"]

    async def test_update_job_not_found(self, client):
        fake_id = str(ObjectId())
        resp = await client.put(f"/api/jobs/{fake_id}", json={"job_title": "Test"})
        assert resp.status_code == 404

    async def test_update_job_invalid_id(self, client):
        resp = await client.put("/api/jobs/invalid", json={"job_title": "Test"})
        assert resp.status_code == 400

    async def test_delete_job(self, client, sample_job_data):
        create_resp = await client.post("/api/jobs", json=sample_job_data)
        job_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify it's gone
        get_resp = await client.get(f"/api/jobs/{job_id}")
        assert get_resp.status_code == 404

    async def test_delete_job_not_found(self, client):
        fake_id = str(ObjectId())
        resp = await client.delete(f"/api/jobs/{fake_id}")
        assert resp.status_code == 404

    async def test_delete_job_invalid_id(self, client):
        resp = await client.delete("/api/jobs/bad-id")
        assert resp.status_code == 400

    async def test_multiple_jobs_sorted(self, client, mock_db):
        """Jobs are returned sorted by posted_at descending."""
        await self._clean_db(mock_db)
        await client.post("/api/jobs", json={
            "job_title": "Job A",
            "job_description": "First",
            "required_skills": ["Python"],
        })
        await client.post("/api/jobs", json={
            "job_title": "Job B",
            "job_description": "Second",
            "required_skills": ["Java"],
        })
        resp = await client.get("/api/jobs")
        jobs = resp.json()
        assert len(jobs) == 2
