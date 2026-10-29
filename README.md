# ResumeAI

AI resume screening: parses resumes with Gemini, verifies candidates against GitHub / LinkedIn / the web, and ranks them against job descriptions.

## Run locally

```bash
# Backend (copy backend/.env.example to backend/.env first)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (copy frontend/.env.example to frontend/.env first)
cd frontend
yarn install && yarn start
```

Tests: `pytest` from the repository root.

## Docs

- [Bugs found — 28 Oct 2026 (tracking checklist)](docs/BUGS_FOUND_2026-10-28.md)
- [Scalability, hosted database and OAuth 2.0 setup](docs/SCALING_DATABASE_AUTH.md)
- [UI audit: what's real and what's only in the UI](docs/UI_AUDIT.md)
- [Backend analysis: bugs, scoring correctness, limits](docs/BACKEND_ANALYSIS.md)
- [UI upgrade & compatibility review](docs/UI_UPGRADE_COMPATIBILITY.md)
