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

- [Scalability, hosted database and OAuth 2.0 setup](docs/SCALING_DATABASE_AUTH.md)
- [UI audit: what's real and what's only in the UI](docs/UI_AUDIT.md)
