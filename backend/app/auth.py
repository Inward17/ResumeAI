"""
OAuth 2.0 bearer-token authentication.

The frontend signs users in with Firebase Authentication (Google OAuth 2.0 /
OpenID Connect, or email + password) and sends the resulting ID token as
``Authorization: Bearer <token>``. Every API route verifies that token here:
signature against Google's published keys, issuer, audience and expiry.

Plain Google OAuth 2.0 ID tokens (e.g. from Google Identity Services or a
mobile app) are accepted too when GOOGLE_OAUTH_CLIENT_IDS is set.

Configuration (backend .env):
  FIREBASE_PROJECT_ID     Firebase project id (same as REACT_APP_FIREBASE_PROJECT_ID)
  GOOGLE_OAUTH_CLIENT_IDS optional, comma-separated OAuth client ids
  AUTH_DISABLED=true      local development only: skip verification
"""
import os
import re
import time
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

import httpx
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import exceptions as google_auth_exceptions
from google.auth import jwt as google_jwt

from app.database import db
from app.org import API_KEY_PREFIX, ensure_org, user_for_api_key

logger = logging.getLogger(__name__)

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_IDS = [c.strip() for c in os.getenv("GOOGLE_OAUTH_CLIENT_IDS", "").split(",") if c.strip()]
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() == "true"

FIREBASE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

bearer_scheme = HTTPBearer(auto_error=False, description="Firebase / Google OAuth 2.0 ID token")


@dataclass
class AuthUser:
    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: Optional[str] = None
    # Set for workspace API keys, which always act inside their own organization
    org_id: Optional[str] = None


class _CertCache:
    """Caches Google's public signing certificates for as long as Cache-Control allows."""

    def __init__(self):
        self._certs: Dict[str, Tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, url: str) -> dict:
        certs, expires_at = self._certs.get(url, ({}, 0.0))
        if certs and time.time() < expires_at:
            return certs
        async with self._lock:
            certs, expires_at = self._certs.get(url, ({}, 0.0))
            if certs and time.time() < expires_at:
                return certs
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
            match = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
            max_age = int(match.group(1)) if match else 3600
            certs = response.json()
            self._certs[url] = (certs, time.time() + max_age)
            return certs


_cert_cache = _CertCache()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_id_token(token: str) -> AuthUser:
    """Verify a Firebase or Google OAuth 2.0 ID token and return the user it identifies."""
    try:
        # Signature is NOT checked here — only used to pick the issuer's keys below
        unverified = google_jwt.decode(token, verify=False)
    except (ValueError, google_auth_exceptions.GoogleAuthError):
        raise _unauthorized("Malformed token")

    issuer = unverified.get("iss", "")
    if FIREBASE_PROJECT_ID and issuer == f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}":
        certs_url, audience = FIREBASE_CERTS_URL, FIREBASE_PROJECT_ID
    elif GOOGLE_OAUTH_CLIENT_IDS and issuer in GOOGLE_ISSUERS:
        certs_url, audience = GOOGLE_CERTS_URL, GOOGLE_OAUTH_CLIENT_IDS
    else:
        raise _unauthorized("Token issuer is not accepted")

    try:
        certs = await _cert_cache.get(certs_url)
    except httpx.HTTPError as exc:
        logger.error("Could not fetch Google signing certificates: %s", exc)
        raise HTTPException(status_code=503, detail="Authentication service unavailable")

    try:
        # Checks signature, exp/iat (with small clock skew) and audience
        claims = google_jwt.decode(token, certs=certs, audience=audience, clock_skew_in_seconds=10)
    except (ValueError, google_auth_exceptions.GoogleAuthError) as exc:
        raise _unauthorized(f"Invalid token: {exc}")
    if claims.get("iss") != issuer:
        raise _unauthorized("Token issuer is not accepted")

    uid =claims.get("user_id") or claims.get("sub")
    if not uid:
        raise _unauthorized("Token has no subject")

    firebase_info = claims.get("firebase") or {}
    return AuthUser(
        uid=uid,
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
        provider=firebase_info.get("sign_in_provider") or "google",
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    """FastAPI dependency: the authenticated user, or 401."""
    if AUTH_DISABLED:
        return AuthUser(uid="dev-user", email="dev@localhost", name="Local Developer", provider="disabled")
    # Workspace API keys don't depend on the identity provider being configured
    if credentials is not None and credentials.credentials.startswith(API_KEY_PREFIX):
        user = await user_for_api_key(credentials.credentials)
        if not user:
            raise _unauthorized("Invalid or revoked API key")
        return user
    if not FIREBASE_PROJECT_ID and not GOOGLE_OAUTH_CLIENT_IDS:
        logger.error("Auth is enabled but neither FIREBASE_PROJECT_ID nor GOOGLE_OAUTH_CLIENT_IDS is set")
        raise HTTPException(status_code=500, detail="Authentication is not configured on the server")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")
    return await verify_id_token(credentials.credentials)


async def require_job_owner(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    """Dependency for /jobs/{job_id}/... routes: the job must belong to the caller."""
    try:
        obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    job = await db.jobs.find_one({"_id": obj_id, "org_id": await ensure_org(user)})
    if not job:
        # 404 rather than 403 so job ids of other organizations aren't revealed
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def require_candidate_access(candidate_id: str, user: AuthUser = Depends(get_current_user)) -> None:
    """Dependency for candidate routes: the candidate must have applied to one of the organization's jobs."""
    job_ids = await db.applications.distinct("job_id", {"candidate_id": candidate_id})
    owned = []
    for job_id in job_ids:
        try:
            owned.append(ObjectId(job_id))
        except Exception:
            continue
    if not owned or not await db.jobs.find_one({"_id": {"$in": owned}, "org_id": await ensure_org(user)}):
        raise HTTPException(status_code=404, detail="Candidate not found")


async def upsert_user(user: AuthUser) -> dict:
    """Record the user on login so the app has a users collection to build on."""
    now = datetime.utcnow()
    await db.users.update_one(
        {"uid": user.uid},
        {
            "$set": {"email": user.email, "name": user.name, "picture": user.picture,
                     "provider": user.provider, "last_login_at": now},
            "$setOnInsert": {"uid": user.uid, "created_at": now},
        },
        upsert=True,
    )
    return await db.users.find_one({"uid": user.uid}, {"_id": 0})
