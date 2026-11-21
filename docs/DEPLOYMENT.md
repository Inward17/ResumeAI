# Deployment (CI/CD)

`.github/workflows/ci-cd.yml` runs on every pull request and every push to `main`:

| Job | When | What |
|---|---|---|
| Backend tests | Always | `pytest` with CPU-only PyTorch; every external service is mocked |
| Frontend build | Always | `yarn build` for GitHub Pages (base path `/<repo>/`, `404.html` fallback for deep links) |
| Deploy frontend | Push to `main`, tests and build green | Publishes `frontend/dist` to **GitHub Pages** |
| Deploy backend | Push to `main`, tests green, `HF_SPACE` set | Uploads `backend/` to a **Hugging Face Docker Space** and syncs its settings |

Live URLs once set up:

- App: `https://<github-user>.github.io/<repo>/` (here: <https://inward17.github.io/ResumeAI/>)
- API: `https://<hf-user>-<space-name>.hf.space`

GitHub Pages can only serve static files, so the FastAPI backend runs on Hugging Face Spaces: the free CPU tier has 16 GB of RAM, enough for the embedding models (MiniLM, CodeBERT, BGE-large).

## One-time setup

### 1. GitHub Pages

Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 2. Repository variables (Settings → Secrets and variables → Actions → Variables)

| Variable | Value |
|---|---|
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_MEASUREMENT_ID` | Same values as `frontend/.env`. Firebase web config is public by design; it ends up in the browser bundle. |
| `HF_SPACE` | `<hf-user>/<space-name>`, e.g. `jane/resumeai-api`. Created automatically on first deploy. |
| `API_URL` | Optional. Overrides the API URL derived from `HF_SPACE`. |

### 3. Hugging Face

1. Create a free account at <https://huggingface.co>.
2. **Settings → Access Tokens → Create new token** with **Write** access.
3. Add it to GitHub as the repository **secret** `HF_TOKEN`.

### 4. Backend secrets (Settings → Secrets and variables → Actions → Secrets)

Each deploy copies these to the Space's secrets. You can also set them directly in the Space (**Settings → Variables and secrets**) and skip them here.

| Secret | Needed for |
|---|---|
| `MONGO_URL`, `DB_NAME` | Database (required) |
| `GEMINI_API_KEY` | Resume parsing (required) |
| `GROQ_API_KEY` | Interview questions, fact checker |
| `GH_VERIFICATION_TOKEN` | GitHub verification. Becomes `GITHUB_TOKEN` in the Space; GitHub reserves the `GITHUB_` prefix for its own secrets. |
| `FIRECRAWL_API_KEY`, `APIFY_TOKEN` | LinkedIn verification |
| `COMPOSIO_API_KEY` | Invitation emails (also set `COMPOSIO_USER_ID` in the Space if it isn't `default`) |

The deploy also sets these Space variables: `CORS_ORIGINS` (your Pages origin), `APP_URL` (Pages URL, used in invitation links) and `FIREBASE_PROJECT_ID`.

### 5. Firebase and MongoDB

- Firebase console → **Authentication → Settings → Authorized domains** → add `<github-user>.github.io`. Without it, Google sign-in fails on the live site.
- MongoDB Atlas → **Network Access**: Hugging Face doesn't publish fixed outbound IPs, so allow `0.0.0.0/0` and rely on a strong database password. Use a separate database user for production.

### 6. Deploy

Merge to `main` (or **Actions → CI/CD → Run workflow** on `main`). The first backend build takes 10–15 minutes while PyTorch installs; the first request after that downloads the models.

## Notes

- **Cold starts:** free Spaces sleep after about 48 hours without traffic. The first request afterwards takes a minute or two.
- **Uploaded resumes** are stored on the Space's disk, which is reset on every redeploy or restart. Finished candidates live in MongoDB and are unaffected; only files still queued at that moment are lost. Persistent storage (or object storage such as S3) removes this limit.
- **Pull requests** run tests and the build but never deploy.
- The backend image (`backend/Dockerfile`) runs on any container host: set `PORT` and the variables in `backend/.env.example`.
