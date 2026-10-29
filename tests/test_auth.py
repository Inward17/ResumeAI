"""
Tests for OAuth 2.0 bearer-token auth (app/auth.py) and per-user job scoping.
Tokens are signed with a locally generated key; Google's cert endpoint is never called.
"""
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt as google_jwt

from tests.conftest import create_owned_job

PROJECT_ID = "resumeai-test"
KEY_ID = "test-key"


@pytest.fixture(scope="module")
def signing_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(days=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    signer = crypt.RSASigner.from_string(private_pem, key_id=KEY_ID)
    certs = {KEY_ID: cert.public_bytes(serialization.Encoding.PEM).decode()}
    return signer, certs


def make_token(signer, **overrides):
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT_ID}",
        "aud": PROJECT_ID,
        "sub": "uid-123",
        "user_id": "uid-123",
        "email": "recruiter@example.com",
        "name": "Recruiter",
        "iat": now,
        "exp": now + 3600,
        "firebase": {"sign_in_provider": "google.com"},
    }
    claims.update(overrides)
    return google_jwt.encode(signer, claims).decode()


@pytest.fixture()
def firebase_auth(signing_material):
    _, certs = signing_material
    with patch("app.auth.FIREBASE_PROJECT_ID", PROJECT_ID), \
         patch("app.auth.AUTH_DISABLED", False), \
         patch("app.auth._cert_cache.get", new=AsyncMock(return_value=certs)):
        yield


class TestVerifyIdToken:
    async def test_valid_firebase_token(self, firebase_auth, signing_material):
        from app.auth import verify_id_token
        user = await verify_id_token(make_token(signing_material[0]))
        assert user.uid == "uid-123"
        assert user.email == "recruiter@example.com"
        assert user.provider == "google.com"

    async def test_expired_token_rejected(self, firebase_auth, signing_material):
        from fastapi import HTTPException
        from app.auth import verify_id_token
        now = int(time.time())
        token = make_token(signing_material[0], iat=now - 7200, exp=now - 3600)
        with pytest.raises(HTTPException) as exc:
            await verify_id_token(token)
        assert exc.value.status_code == 401

    async def test_wrong_audience_rejected(self, firebase_auth, signing_material):
        from fastapi import HTTPException
        from app.auth import verify_id_token
        token = make_token(signing_material[0], aud="another-project",
                           iss=f"https://securetoken.google.com/{PROJECT_ID}")
        with pytest.raises(HTTPException) as exc:
            await verify_id_token(token)
        assert exc.value.status_code == 401

    async def test_unknown_issuer_rejected(self, firebase_auth, signing_material):
        from fastapi import HTTPException
        from app.auth import verify_id_token
        token = make_token(signing_material[0], iss="https://evil.example.com")
        with pytest.raises(HTTPException) as exc:
            await verify_id_token(token)
        assert exc.value.status_code == 401

    async def test_token_signed_by_other_key_rejected(self, firebase_auth):
        from fastapi import HTTPException
        from app.auth import verify_id_token
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = other_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        forged = make_token(crypt.RSASigner.from_string(pem, key_id=KEY_ID))
        with pytest.raises(HTTPException) as exc:
            await verify_id_token(forged)
        assert exc.value.status_code == 401

    async def test_garbage_token_rejected(self, firebase_auth):
        from fastapi import HTTPException
        from app.auth import verify_id_token
        with pytest.raises(HTTPException) as exc:
            await verify_id_token("not-a-jwt")
        assert exc.value.status_code == 401


class TestProtectedRoutes:
    async def test_missing_token_is_401(self, anon_client, firebase_auth):
        resp = await anon_client.get("/api/jobs")
        assert resp.status_code == 401
        assert resp.headers["www-authenticate"] == "Bearer"

    async def test_candidate_routes_require_token(self, anon_client, firebase_auth):
        resp = await anon_client.post("/api/v1/jobs/abc/upload", files=[("files", ("a.pdf", b"x"))])
        assert resp.status_code == 401

    async def test_valid_token_reaches_route(self, anon_client, firebase_auth, signing_material, mock_db):
        token = make_token(signing_material[0])
        resp = await anon_client.get("/api/jobs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    async def test_me_records_user(self, anon_client, firebase_auth, signing_material, mock_db):
        token = make_token(signing_material[0])
        resp = await anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["uid"] == "uid-123"
        assert await mock_db.users.count_documents({"uid": "uid-123"}) == 1

    async def test_health_check_is_public(self, anon_client):
        resp = await anon_client.get("/")
        assert resp.status_code == 200

    async def test_unconfigured_server_fails_closed(self, anon_client):
        with patch("app.auth.FIREBASE_PROJECT_ID", ""), patch("app.auth.GOOGLE_OAUTH_CLIENT_IDS", []), \
             patch("app.auth.AUTH_DISABLED", False):
            resp = await anon_client.get("/api/jobs", headers={"Authorization": "Bearer x"})
        assert resp.status_code == 500


class TestJobScoping:
    async def test_jobs_list_only_shows_own_jobs(self, client, mock_db):
        mine = await create_owned_job(mock_db, job_title="Mine")
        await create_owned_job(mock_db, owner_uid="someone-else", job_title="Theirs")
        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        assert [j["id"] for j in resp.json()] == [mine]

    async def test_jobs_list_includes_candidate_counts(self, client, mock_db, owned_job_id):
        for status in ["Under Review", "Shortlisted", "Interview", "New"]:
            await mock_db.applications.insert_one({"job_id": owned_job_id, "candidate_id": status, "status": status})
        resp = await client.get("/api/jobs")
        job = resp.json()[0]
        assert (job["total_candidates"], job["screened"], job["shortlisted"]) == (4, 3, 2)

    async def test_cannot_read_update_or_delete_other_users_job(self, client, mock_db):
        theirs = await create_owned_job(mock_db, owner_uid="someone-else")
        assert (await client.get(f"/api/jobs/{theirs}")).status_code == 404
        assert (await client.put(f"/api/jobs/{theirs}", json={"job_title": "x"})).status_code == 404
        assert (await client.delete(f"/api/jobs/{theirs}")).status_code == 404
        assert await mock_db.jobs.count_documents({"owner_uid": "someone-else"}) == 1

    async def test_created_job_is_owned_by_caller(self, client, mock_db, sample_job_data):
        with patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 384):
            resp = await client.post("/api/jobs", json=sample_job_data)
        assert resp.status_code == 200
        from bson import ObjectId
        job = await mock_db.jobs.find_one({"_id": ObjectId(resp.json()["id"])})
        assert job["owner_uid"] == "test-user"

    async def test_fact_checker_requires_candidate_access(self, client, mock_db):
        theirs = await create_owned_job(mock_db, owner_uid="someone-else")
        await mock_db.applications.insert_one({"candidate_id": "c-theirs", "job_id": theirs})
        resp = await client.post("/api/fact-checker/c-theirs", json={"message": "hi"})
        assert resp.status_code == 404
