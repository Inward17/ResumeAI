# ResumeAI

AI resume screening for hiring teams. ResumeAI parses every resume with Gemini, checks the candidate's claims against GitHub, LinkedIn and the web, scores them against your job description, and ranks the pipeline so recruiters start with the strongest, most credible candidates.

## Features

- **Bulk screening.** Drop 100+ resumes (PDF, DOCX, TXT) on a job. A durable MongoDB-backed queue parses and verifies them in parallel, with live progress.
- **Evidence, not keywords.** Per-skill match scores, a 15-step GitHub authenticity pipeline, LinkedIn employment/education matching and a web check combine into one credibility score.
- **Ranked pipeline.** Sortable candidate table with role match and credibility, inline status changes, and a dossier for each candidate.
- **Interview kit.** AI-generated questions tailored to the job and resume, a checklist scorer, and a fact checker you can ask about any claim.
- **Teams.** Shared workspaces with owner, admin and member roles, email invitations (via Composio Gmail) or copyable invite links.
- **Workspace API keys** for calling the API from your own tools.
- **Plan & usage.** Live limits of every external key the backend runs on (GitHub, Firecrawl, Apify, Gemini, Groq, Composio).
- Light and dark themes, phone layouts, keyboard and screen-reader support.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 6, Tailwind CSS 3, Radix UI, Firebase Authentication |
| Backend | Python 3.11+, FastAPI, Motor (MongoDB), asyncio task queue |
| AI & data | Google Gemini (parsing), Groq (questions, fact checking), MiniLM / CodeBERT / BGE embeddings, Firecrawl + Apify (LinkedIn), GitHub REST API, DuckDuckGo |

## Run locally

Prerequisites: Python 3.11+, Node 20+ with Yarn 1, a MongoDB database (local or Atlas) and a Firebase project with Google sign-in enabled.

```bash
# Backend: copy backend/.env.example to backend/.env and fill it in
cd backend
python -m venv venv && venv/Scripts/activate      # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend: copy frontend/.env.example to frontend/.env and fill it in
cd frontend
yarn install
yarn dev                                          # http://localhost:3000
```

Sign in once, then load demo data into your workspace if you want something to click through:

```bash
cd backend
python -m scripts.seed_demo --email you@company.com            # 5 jobs, 28 candidates, 2 teammates, 2 invites
python -m scripts.seed_demo --email you@company.com --remove   # delete everything it created
```

## Configuration

All backend settings live in `backend/.env`; [`backend/.env.example`](backend/.env.example) documents every variable. The essentials:

| Variable | Needed for |
|---|---|
| `MONGO_URL`, `DB_NAME` | Database |
| `FIREBASE_PROJECT_ID`, `CORS_ORIGINS` | Sign-in and browser access |
| `GEMINI_API_KEY` | Resume parsing |
| `GITHUB_TOKEN` | GitHub verification (5,000 requests/hour instead of 60) |
| `GROQ_API_KEY` | Interview questions and the fact checker |
| `FIRECRAWL_API_KEY` / `APIFY_TOKEN` | LinkedIn verification (Firecrawl first, Apify fallback) |
| `COMPOSIO_API_KEY`, `APP_URL` | Invitation emails and their links |

The frontend needs `VITE_API_URL` and the `VITE_FIREBASE_*` values ([`frontend/.env.example`](frontend/.env.example)).

## Tests

```bash
pytest            # from the repository root; all external services are mocked
```

## Project structure

```
backend/
  app/
    main.py              FastAPI app, CORS, routers
    auth.py              Firebase / Google ID tokens and workspace API keys
    org.py               Workspaces, roles, invitations, API key helpers
    database.py          MongoDB client and indexes
    routes/              HTTP endpoints (jobs, resumes, verification, interviews, organization…)
    services/            Parsing, task queue, verification, GitHub pipeline, skill matching, usage checks
    agent/               Optional agent-based verification (USE_AGENT_SYSTEM)
  scripts/               seed_demo.py, assign_job_owner.py
frontend/src/
  components/            Pages, shared UI kit (common.jsx), settings sections
  services/              API clients
  lib/                   Theme, statuses, preferences
tests/                   Backend test suite
docs/                    Architecture, setup guides, reports
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): components, request flow, data model
- [Scalability, database, authentication and teams](docs/SCALING_DATABASE_AUTH.md): setup guide
- [Project report](docs/PROJECT_REPORT.md): algorithms and implementation in depth
- [Evaluation results](docs/EVALUATION_RESULTS.md)
- Review records: [backend analysis](docs/BACKEND_ANALYSIS.md), [bugs found on 28 Oct 2026](docs/BUGS_FOUND_2026-10-28.md)
- [LangGraph migration plan](docs/LANGGRAPH_MIGRATION_PLAN.md) (proposal, not implemented)
