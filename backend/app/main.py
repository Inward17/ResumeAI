import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database import client
from app.routes import resume, linkedin, verification, github_routes

# Load environment variables
load_dotenv()

# Create app
app = FastAPI(title="ResumeAI Backend")

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(resume.router, prefix="/api/v1")
app.include_router(linkedin.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(github_routes.router, prefix="/api/v1")


@app.on_event("shutdown")
async def shutdown():
    """Close MongoDB connection on shutdown"""
    client.close()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "resumeai-backend",
        "time": datetime.utcnow().isoformat()
    }