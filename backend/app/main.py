import os
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables before app modules read them
load_dotenv()

# Windows consoles default to cp1252, and logging an emoji there raises inside
# request handlers; never let a log line break a request
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.auth import AUTH_DISABLED, get_current_user
from app.database import client, ensure_indexes, ping_database
from app.services.task_queue import RESUME_WORKERS, task_queue
from app.routes import resume, linkedin, verification, github_routes, unified_verification_routes, search_routes, job_routes, interview_questions_routes, evaluation_routes, fact_checker_routes, auth_routes, org_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def check_auth_disabled_allowed():
    """Refuse to start with AUTH_DISABLED on a deployment.

    Hugging Face Spaces set SPACE_ID, and the Docker image serves on port 7860;
    either means this isn't a local development server.
    """
    if AUTH_DISABLED and (os.getenv("SPACE_ID") or os.getenv("PORT") == "7860"):
        raise RuntimeError("AUTH_DISABLED=true is for local development only; refusing to start on a deployment")


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_auth_disabled_allowed()
    if AUTH_DISABLED:
        logger.warning("AUTH_DISABLED=true — API is open to anyone. Never use this in production.")
    if await ping_database():
        await ensure_indexes()
    # RESUME_WORKERS=0 runs an API-only process (pair it with `python -m app.worker`)
    task_queue.start(resume.process_resume_task, RESUME_WORKERS)
    yield
    await task_queue.stop()
    # Close MongoDB connection on shutdown
    client.close()


# Create app
# API docs are off unless ENABLE_API_DOCS=true, so a deployment doesn't publish its schema
_docs = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"
app = FastAPI(
    title="ResumeAI Backend",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every API route requires a valid OAuth 2.0 bearer token
authenticated = [Depends(get_current_user)]

# Include routers
app.include_router(auth_routes.router, prefix="/api", dependencies=authenticated)
app.include_router(resume.router, prefix="/api/v1", dependencies=authenticated)
app.include_router(linkedin.router, prefix="/api/v1", dependencies=authenticated)
app.include_router(verification.router, prefix="/api/v1", dependencies=authenticated)
app.include_router(github_routes.router, prefix="/api/v1", dependencies=authenticated)
app.include_router(unified_verification_routes.router, prefix="/api/v1", dependencies=authenticated)
app.include_router(search_routes.router, dependencies=authenticated)
app.include_router(job_routes.router, prefix="/api", dependencies=authenticated)
app.include_router(interview_questions_routes.router, prefix="/api", dependencies=authenticated)
app.include_router(evaluation_routes.router, prefix="/api", dependencies=authenticated)
app.include_router(fact_checker_routes.router, prefix="/api", dependencies=authenticated)
app.include_router(org_routes.router, prefix="/api", dependencies=authenticated)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "resumeai-backend",
        "time": datetime.utcnow().isoformat()
    }
