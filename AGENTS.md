# AGENTS.md

Instructions for coding and review agents working on ResumeAI: an AI resume-screening app with a React frontend and a FastAPI + MongoDB backend. See [README.md](README.md) for the product and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for CI/CD.

## Layout

| Path | What |
|---|---|
| `backend/app/routes/` | HTTP endpoints |
| `backend/app/services/` | Parsing, task queue, verification, GitHub pipeline, skill matching, usage checks |
| `backend/app/auth.py`, `backend/app/org.py` | Sign-in, workspace API keys, workspaces, roles and invites |
| `frontend/src/components/` | Pages and shared UI (`common.jsx`) |
| `frontend/src/services/` | API calls; snake_case to camelCase conversion happens here |
| `tests/` | Backend tests (run from the repository root) |

## Commands

```bash
pytest                          # from the repository root; external services are mocked
cd frontend && yarn build       # the frontend has no test suite or linter, so the build is the check
```

Both run in CI on every pull request. Pushes to `main` deploy the frontend to GitHub Pages and the backend to Hugging Face.

## Conventions

- Keep diffs small and match the surrounding code. Don't add a dependency for what a few lines can do.
- Colours come from the theme tokens in `frontend/src/index.css`, so light and dark both work. Reuse the components in `common.jsx`.
- Candidate statuses are defined in `frontend/src/lib/statuses.js` and must match the backend's list in `backend/app/routes/resume.py`.
- Scores reach the UI as 0–100, and `null` means "not available", never 0. Skill and role-match scores are 0–10 in the database.
- When the AI service fails, tell the user that it is down and which feature can't work. Never substitute made-up or generic results.
- Any module that does `from app.database import db` must be listed in `_patch_db` in `tests/conftest.py`. Otherwise its tests write to the real database.
- Bug fixes come with a regression test when the logic is on the backend.
- Commits and pull requests carry no AI co-author or "generated with" lines.

## Review guidelines

Report defects that would break behaviour or lose data. Skip style preferences and anything CI already catches. Security rules are in [SECURITY.md](SECURITY.md); treat a violation of them as P1 or higher.

**P0: must not merge**
- A route or query that exposes one workspace's jobs, candidates, members or keys to another.
- A secret, real `.env` value or real candidate data in the diff.
- `AUTH_DISABLED` or `VITE_AUTH_DISABLED` able to take effect in a production build or deployment.
- A change that can silently lose candidates or evaluations, such as a pipeline write that fails without marking the task failed.

**P1: fix before merge**
- Task queue changes that break atomic claims, heartbeats, stale recovery or attempt limits.
- A write that ignores the existing per-candidate, per-job upsert and creates duplicates.
- Scores on the wrong scale, or a missing value displayed as 0.
- A failure in an external service (Gemini, Groq, GitHub, Firecrawl, Apify, Composio) that crashes a request, stops the batch, or is reported as success.
- A new route with no test for its access check.
- A navigation change that loses unsaved work or sends the user to the wrong page.
- Blocking calls (file I/O, embeddings) on the event loop in async routes. Use `asyncio.to_thread`.

**Don't flag**
- `datetime.utcnow()` deprecation warnings; they are a known, repo-wide item.
- Legacy files already marked unused in `docs/`, unless the diff changes them.
- Missing frontend tests, unless the pull request claims to add them.
