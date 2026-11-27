# ResumeAI

AI resume screening for hiring teams. ResumeAI parses every resume with Gemini, checks the candidate's claims against GitHub, LinkedIn and the web, scores them against your job description, and ranks the pipeline so recruiters start with the strongest, most credible candidates.

## Features

- **Bulk screening.** Drop 100+ resumes (PDF, DOCX, TXT) on a job. A durable MongoDB-backed queue parses and verifies them in parallel, with live progress.
- **Evidence, not keywords.** Per-skill match scores, a 15-step GitHub authenticity pipeline, LinkedIn employment/education matching and a web check combine into one credibility score.
- **Coding profiles.** LeetCode, HackerRank, HackerEarth, Codeforces and CodeChef profiles linked on the resume are looked up; ratings, titles and problems solved are shown in the dossier, overstated claims ("Codeforces Expert", "500+ problems") and name mismatches are flagged. They are extra evidence and don't change the credibility score.
- **Portfolios & communities.** Behance, Dribbble, a personal portfolio website, Kaggle and Stack Overflow linked on the resume are read (Stack Overflow through its official API, the rest through Firecrawl). The dossier shows projects, tools, tiers, reputation and top tags; overstated claims ("Kaggle Master", "10k reputation"), name mismatches and history that contradicts the resume are flagged, and job skills shown in the portfolio are listed. Evidence only: no effect on credibility or role match.
- **Project reviews.** On demand, the AI visits up to three of the candidate's deployed projects (the ones most relevant to the job) through Firecrawl, looks at the landing page, two internal pages and a screenshot, and rates whether it works, polish, technical depth and originality, checks it against the resume or portfolio claim and for ownership signs, and suggests interview questions about it. Each result keeps where the candidate mentioned the project. Evidence only: no effect on credibility or role match.
- **Ranked pipeline.** Sortable candidate table with role match and credibility, inline status changes, and a dossier for each candidate.
- **Cover letters.** Attach a cover letter (file or pasted text) in a candidate's dossier, or drop letters in with the resumes: each upload is classified as resume or cover letter, and letters are paired with their resume by filename or signed name (a letter-then-resume PDF is split). Letters that match no resume are listed after the upload and never create a candidate. One AI call summarises the letter, checks how well it fits the job, lists differences from the resume by severity, and suggests points to probe; the analysis feeds the interview questions. Letters are evidence only and never change a score.
- **Interview kit.** AI-generated questions tailored to the job and resume, a checklist scorer, and a fact checker you can ask about any claim.
- **Teams.** Shared workspaces with email invitations (via Composio Gmail) or copyable invite links, and five roles: owner, admin, recruiter, hiring manager and interviewer. Hiring managers and interviewers see only the jobs whose hiring team they are on.
- **Workspace API keys** for calling the API from your own tools.
- **AI and Integrations settings.** Today's AI calls and uploads against the daily limits, usage by feature and over 30 days, and live limits of every external key the backend runs on (GitHub, Firecrawl, Apify, Gemini, Groq, Composio). Owners and admins can give a workspace its own key for any of them.
- Light and dark themes, phone layouts, keyboard and screen-reader support.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 6, Tailwind CSS 3, Radix UI, Firebase Authentication |
| Backend | Python 3.11+, FastAPI, Motor (MongoDB), asyncio task queue |
| AI & data | Google Gemini (parsing), Groq (questions, fact checking), MiniLM / CodeBERT / BGE embeddings, Firecrawl + Apify (LinkedIn), GitHub REST API, DuckDuckGo |

## Live demo

The `main` branch deploys automatically: the app to **GitHub Pages** (<https://inward17.github.io/ResumeAI/>) and the API to a Hugging Face Space. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the CI/CD pipeline and one-time setup.

## Run locally

Prerequisites: Python 3.11+, Node 24.12+ with Yarn 1, a MongoDB database (local or Atlas) and a Firebase project with Google sign-in enabled.

```bash
# Backend: copy backend/.env.example to backend/.env and fill it in
cd backend
python -m venv venv && venv/Scripts/activate      # macOS/Linux: source venv/bin/activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt   # runtime + test tools
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
| `FIRECRAWL_API_KEY`, `PORTFOLIO_CHECKS_ENABLED` | Behance, Dribbble, Kaggle and portfolio-website checks (one Firecrawl scrape per source per verification; without a key they show "not checked"; `false` switches them off) |
| `PROJECT_REVIEW_MAX_PROJECTS`, `PROJECT_REVIEW_MAX_PAGES` | Project reviews: projects per review (default 3) and pages per project (default 3). Needs `FIRECRAWL_API_KEY` and `GEMINI_API_KEY`; about 3 Firecrawl credits and 1 Gemini call per project |
| `COMPOSIO_API_KEY`, `APP_URL` | Invitation emails and their links |
| `PROVIDER_KEYS_SECRET` | Workspace keys in Settings → Integrations: a Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) that encrypts them. Without it, every workspace uses the server keys above |

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
- [Deployment](docs/DEPLOYMENT.md): CI/CD, GitHub Pages and Hugging Face setup
- [Scalability, database, authentication and teams](docs/SCALING_DATABASE_AUTH.md): setup guide
- [Project report](docs/PROJECT_REPORT.md): algorithms and implementation in depth
- [Evaluation results](docs/EVALUATION_RESULTS.md)
- Review records: [backend analysis](docs/BACKEND_ANALYSIS.md), [bugs found on 28 Oct 2026](docs/BUGS_FOUND_2026-10-28.md)
- [LangGraph migration plan](docs/LANGGRAPH_MIGRATION_PLAN.md) (proposal, not implemented)

## License

[MIT](LICENSE)
