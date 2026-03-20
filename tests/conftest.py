"""
Shared fixtures and configuration for ResumeAI backend tests.
All external APIs are mocked — no real calls to GitHub, Gemini, Apify, or DuckDuckGo.
"""
import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Ensure backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


# ---------------------------------------------------------------------------
# Event-loop fixture (pytest-asyncio)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock MongoDB  (mongomock-motor)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_db():
    """Provide a fresh mongomock-motor database for each test."""
    from mongomock_motor import AsyncMongoMockClient
    client = AsyncMongoMockClient()
    db = client["test_resume_validator"]
    return db


@pytest.fixture(autouse=True)
def _patch_db(mock_db):
    """Auto-patch app.database.db and every module that imports db directly."""
    import importlib
    from contextlib import ExitStack

    targets = [
        "app.database.db",
        "app.routes.job_routes.db",
        "app.routes.resume.db",
        "app.routes.github_routes.db",
        "app.services.unified_verification.db",
    ]

    # Pre-import every module so patch() can resolve the attribute
    for target in targets:
        module_path = target.rsplit(".", 1)[0]
        try:
            importlib.import_module(module_path)
        except Exception:
            pass  # Module may not be loadable — patch will skip

    with ExitStack() as stack:
        for target in targets:
            try:
                stack.enter_context(patch(target, mock_db))
            except (AttributeError, ModuleNotFoundError):
                pass  # Skip modules that couldn't be imported
        yield


# ---------------------------------------------------------------------------
# FastAPI async test client
# ---------------------------------------------------------------------------
@pytest.fixture()
async def client(mock_db):
    """Async HTTP client for route tests."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_github_repo():
    """Single GitHub repo as returned by the GitHub REST API."""
    return {
        "name": "my-project",
        "full_name": "testuser/my-project",
        "owner": {"login": "testuser"},
        "fork": False,
        "stargazers_count": 10,
        "forks_count": 2,
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-06-01T14:00:00Z",
        "description": "A cool Python project",
    }


@pytest.fixture()
def sample_github_repos(sample_github_repo):
    """List of GitHub repos."""
    forked_repo = {
        **sample_github_repo,
        "name": "forked-repo",
        "full_name": "testuser/forked-repo",
        "fork": True,
        "description": "Fork of popular project",
    }
    trivial_repo = {
        **sample_github_repo,
        "name": "todo-app",
        "full_name": "testuser/todo-app",
        "description": "Simple todo",
    }
    return [sample_github_repo, forked_repo, trivial_repo]


@pytest.fixture()
def sample_commits():
    """GitHub commit objects."""
    return [
        {"commit": {"author": {"date": "2024-01-15T10:30:00Z"}}},
        {"commit": {"author": {"date": "2024-02-10T12:00:00Z"}}},
        {"commit": {"author": {"date": "2024-03-05T09:15:00Z"}}},
        {"commit": {"author": {"date": "2024-04-20T16:45:00Z"}}},
        {"commit": {"author": {"date": "2024-05-10T11:30:00Z"}}},
        {"commit": {"author": {"date": "2024-05-11T14:00:00Z"}}},
    ]


@pytest.fixture()
def sample_parsed_resume():
    """Parsed resume data as returned by parse_resume."""
    return {
        "personal_info": {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone_number": "+1 555-987-6543",
            "github": "github.com/janedoe",
            "linkedin": "linkedin.com/in/janedoe",
        },
        "skills": "Python, FastAPI, React, Docker",
        "education": ["B.Tech in CS, IIT Delhi, 2021"],
        "experience": ["Software Engineer at Google (2021-2024)"],
        "projects": [
            {
                "name": "E-commerce Platform",
                "technologies": ["Python", "React"],
                "description": "Full-stack app",
                "duration": "Jan-Mar 2023",
                "details": "E-commerce Platform (Jan-Mar 2023) - Built full-stack app",
            }
        ],
        "certifications": ["AWS Certified"],
        "achievements": ["Won hackathon"],
        "university": ["IIT Delhi"],
        "company": ["Google"],
    }


@pytest.fixture()
def sample_linkedin_profile():
    """LinkedIn profile data as returned by Apify scraper."""
    return {
        "profileId": "li-123",
        "publicIdentifier": "janedoe",
        "profileUrl": "https://linkedin.com/in/janedoe",
        "firstName": "Jane",
        "lastName": "Doe",
        "headline": "Software Engineer",
        "summary": "Experienced developer",
        "location": "San Francisco",
        "countryCode": "US",
        "pictureUrl": "https://example.com/pic.jpg",
        "positions": [
            {
                "title": "Software Engineer",
                "companyName": "Google",
                "locationName": "Mountain View",
                "description": "Building systems",
                "totalDuration": "3 years",
            }
        ],
        "educations": [
            {
                "title": "IIT Delhi",
                "schoolName": "IIT Delhi",
                "degreeName": "B.Tech",
                "fieldOfStudy": "Computer Science",
            }
        ],
        "skills": [
            {"name": "Python", "endorsements": 50},
            {"name": "React", "endorsements": 30},
        ],
        "certifications": [{"name": "AWS Certified", "authority": "Amazon"}],
    }


@pytest.fixture()
def sample_verification_result():
    """Web search verification result from verify_profile."""
    return {
        "profile_url": "test-candidate",
        "education": {
            "details": [
                {
                    "college": "IIT Delhi",
                    "verified": True,
                    "confidence": 85,
                    "score": 85,
                    "tag": "Verified",
                    "top_result": "https://iitd.ac.in",
                    "title": "IIT Delhi Official",
                    "snippet": "Indian Institute of Technology Delhi",
                }
            ],
            "average_score": 85,
            "overall_tag": "Verified",
        },
        "experience": {
            "details": [
                {
                    "company": "Google",
                    "position": "Software Engineer",
                    "verified": True,
                    "confidence": 90,
                    "score": 90,
                    "tag": "Verified",
                    "top_result": "https://google.com",
                    "title": "Google Official",
                    "snippet": "Google LLC",
                }
            ],
            "average_score": 90,
            "overall_tag": "Verified",
        },
    }


@pytest.fixture()
def sample_search_results():
    """DuckDuckGo search results."""
    return [
        {
            "href": "https://iitd.ac.in",
            "title": "IIT Delhi - Indian Institute of Technology Delhi",
            "body": "Welcome to IIT Delhi, a premier engineering institution.",
        },
        {
            "href": "https://en.wikipedia.org/wiki/IIT_Delhi",
            "title": "IIT Delhi - Wikipedia",
            "body": "Indian Institute of Technology Delhi is a public university.",
        },
    ]


@pytest.fixture()
def sample_job_data():
    """Job posting data."""
    return {
        "job_title": "Software Engineer",
        "job_description": "Build scalable systems",
        "required_skills": ["Python", "FastAPI", "MongoDB"],
        "preferred_skills": ["Docker", "AWS"],
        "experience_level": "Mid-level",
        "employment_type": "Full-time",
        "location": "Remote",
        "is_active": True,
    }
