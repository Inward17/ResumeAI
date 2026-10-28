import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables before app modules read them
load_dotenv()

from app.auth import AUTH_DISABLED, get_current_user
from app.database import client, ensure_indexes, ping_database
from app.services.task_queue import RESUME_WORKERS, task_queue
from app.routes import resume, linkedin, verification, github_routes, unified_verification_routes, search_routes, job_routes, interview_questions_routes, evaluation_routes, fact_checker_routes, auth_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app = FastAPI(title="ResumeAI Backend", lifespan=lifespan)

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
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


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "resumeai-backend",
        "time": datetime.utcnow().isoformat()
    }
