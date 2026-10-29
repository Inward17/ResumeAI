# Scalability, database, authentication and teams: setup guide

This guide covers the infrastructure behind ResumeAI: bulk resume processing, a hosted MongoDB, authenticated APIs, team workspaces with invitations and API keys, and the external services used for verification.

---

## 1. Bulk resume processing (50–100+ resumes at once)

### Why batches were getting lost

| Cause | Effect |
|---|---|
| Starlette `BackgroundTasks` run **one after another**, after the response | Resume #100 waited for 99 full parse + GitHub + LinkedIn + web verifications |
| `parsing_semaphore = asyncio.Semaphore(1)` | Only one Gemini parse at a time across the whole server |
| Background tasks live in the API process's memory | Every restart or `--reload` dropped everything still queued; tasks stayed `queued` forever |
| Apify LinkedIn scrape (`actor.call`) ran **synchronously** inside `async` code | The whole server froze for each scrape (often 30 s or more), stalling every other request and task |
| Embeddings generated synchronously on the event loop | Same problem on a smaller scale |
| langextract's default 1,000-character chunks | 4–6 Gemini calls per resume, so the quota ran out quickly and calls hit 429 errors with no retry |
| `GET /jobs/{id}/candidates` used `to_list(length=100)` plus 2–3 queries per candidate | No more than 100 candidates were ever shown, and the list was slow |
| Frontend showed "processed by AI" 1.5 s after upload | Users could not tell queued, failed and finished resumes apart |

### What changed

- **Durable queue in MongoDB** (`backend/app/services/task_queue.py`). Upload now just saves the file and inserts `tasks` documents. A dispatcher atomically claims queued tasks and runs `RESUME_WORKERS` of them in parallel.
  - Running tasks send a heartbeat. If a worker dies, its tasks are re-queued after `TASK_STALE_SECONDS`, up to `TASK_MAX_ATTEMPTS` times.
  - Claims are atomic (`find_one_and_update`), so several API processes or dedicated workers can share one database without processing a task twice.
- **Gemini parsing** (`backend/app/services/parser.py`):
  - Bounded concurrency (`PARSE_CONCURRENCY`).
  - Exponential backoff with jitter on 429/5xx/timeouts.
  - One chunk per resume (`PARSER_MAX_CHAR_BUFFER=8000`), which cuts Gemini calls roughly 4–6×.
- **No more event-loop blocking.** LinkedIn lookups are async HTTP calls (the Apify fallback runs in a thread), embeddings run in threads, and the embedding model load is thread-safe.
- **Candidate list** has no 100 cap. It uses batched queries (3 total, regardless of candidate count) and supports `skip`/`limit` paging.
- **Progress endpoint** `GET /api/v1/jobs/{job_id}/tasks` returns queued, processing, done and failed counts. The pipeline page polls it, shows real progress, and refreshes candidates as they finish.
- **Frontend upload** sends files in batches of 10, so large selections stay under proxy and host request-size limits.
- **MongoDB indexes** for every hot query are created at startup.

### Tuning

| Variable | Default | Meaning |
|---|---|---|
| `RESUME_WORKERS` | 8 | Resumes processed concurrently per process (0 = API only) |
| `PARSE_CONCURRENCY` | 4 | Concurrent Gemini calls per process |
| `PARSE_TIMEOUT_SECONDS` | 120 | Per-attempt Gemini timeout |
| `PARSE_MAX_RETRIES` | 4 | Retries for rate-limit and transient errors |
| `TASK_STALE_SECONDS` | 300 | Seconds without a heartbeat before a task is re-queued |
| `MAX_UPLOAD_MB` | 10 | Per-file upload limit |

> **The real ceiling is your Gemini quota.** The free tier allows only a handful of requests per minute. With a paid key, raise `PARSE_CONCURRENCY` (for example to 10–20) and `RESUME_WORKERS`. On the free tier, 100 resumes will still finish, just slowly. Calls back off and retry instead of failing.

### Scaling out

Run the API without workers, and run one or more worker processes against the same database:

```bash
# API
RESUME_WORKERS=0 uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
# Workers (as many as your quotas allow)
RESUME_WORKERS=8 python -m app.worker
```

Uploaded files are still written to the local `RESUMES_DIR`. If the API and the workers run on **different machines**, give them a shared volume. Moving files to object storage (S3, GCS or GridFS) is the next step for fully stateless deploys.

---

## 2. Hosted database (MongoDB Atlas)

`backend/app/database.py` reads `MONGO_URL`, adds a CA bundle for TLS (`certifi`), sets pool sizes and timeouts, and pings the cluster at startup. A bad connection string is logged immediately, with the password redacted.

### Create the cluster

1. Create a cluster at <https://cloud.mongodb.com>. The free M0 tier is fine for development; use M10 or higher for production.
2. **Database Access**: add a database user with a strong password.
3. **Network Access**: add your server's outbound IP. Only use `0.0.0.0/0` temporarily, while testing.
4. **Connect → Drivers → Python**: copy the `mongodb+srv://…` string.

### Configure the backend

In `backend/.env` (see `backend/.env.example`):

```
MONGO_URL=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority&appName=resumeai
DB_NAME=resume_validator
```

URL-encode special characters in the password (`@` → `%40`, and so on).

### Move existing local data

```bash
mongodump --uri "mongodb://localhost:27017" --db resume_validator --out ./dump
mongorestore --uri "mongodb+srv://<user>:<password>@<cluster>.mongodb.net" --nsInclude "resume_validator.*" ./dump
```

Indexes are created automatically the next time the backend starts.

---

## 3. Authentication (OAuth 2.0)

The frontend already signed users in with **Firebase Authentication**, using Google sign-in (OAuth 2.0 / OpenID Connect) or email and password. However, the backend accepted **every request without checking anything**, and all recruiters shared all jobs and candidates.

### What changed

- **Backend** (`backend/app/auth.py`): every `/api` route requires `Authorization: Bearer <ID token>`.
  - Tokens are verified against Google's published signing keys (cached per `Cache-Control`), plus issuer, audience and expiry.
  - Firebase ID tokens are accepted. Plain Google OAuth 2.0 ID tokens are also accepted when `GOOGLE_OAUTH_CLIENT_IDS` is set.
  - `GET /` (the health check) stays public.
- **Per-workspace data** (see section 4):
  - Jobs belong to a workspace (`org_id`), and every `/jobs/{job_id}/…` route checks the caller is a member. Other workspaces' jobs return 404.
  - Candidate de-duplication happens within one uploader's data only.
  - Candidate-level routes (fact checker, verification status) check that the candidate applied to one of the workspace's jobs.
- **`GET /api/auth/me`** records the user in a `users` collection. The frontend calls it on sign-in.
- **Frontend** (`frontend/src/services/api.js`): all API calls send the Firebase ID token, which the SDK refreshes automatically. A 401 signs the user out.

### Configuration

1. In the Firebase console, go to **Authentication → Sign-in method** and enable **Google** (plus Email/Password if you want it). Add your production domain under **Authorized domains**.
2. `frontend/.env`: the `VITE_FIREBASE_*` values from Project settings, plus `VITE_API_URL` (see `frontend/.env.example`). These were called `REACT_APP_*` before the move to Vite.
3. `backend/.env`: `FIREBASE_PROJECT_ID=<same project id>`.
4. `CORS_ORIGINS` must list your frontend's URL.

For quick local hacking without Firebase, set `AUTH_DISABLED=true` in `backend/.env`. Every request then acts as a single `dev-user`. **Never enable this in production.** If neither `FIREBASE_PROJECT_ID` nor `GOOGLE_OAUTH_CLIENT_IDS` is set, the API fails closed with a 500 error.

### Existing jobs after upgrading

Jobs created before workspaces existed move into their owner's workspace automatically the first time that person signs in. Jobs from before authentication have no owner at all, so they are hidden until you assign them:

```bash
cd backend
python -m scripts.assign_job_owner --email you@company.com --dry-run   # sign in to the app once first
python -m scripts.assign_job_owner --email you@company.com
```

---

## 4. Teams: workspaces, invitations and API keys

Code: `backend/app/org.py`, `backend/app/routes/org_routes.py`; UI under **Settings → Team / API keys**.

### Workspaces

- Everyone works inside one **workspace** (an organization). The first time a user is seen, a personal workspace is created and they become its **owner**.
- Jobs and their candidates are shared by every member of the workspace.
- Roles: **owner** (one per workspace), **admin** (can invite, remove members and manage API keys) and **member** (works on every job).
- A user belongs to one active workspace at a time. Accepting an invitation switches them to the inviting workspace; leaving or being removed sends them back to their own.

### Invitations

1. An owner or admin enters an email and role in **Settings → Team**.
2. The backend creates an invitation valid for 14 days and returns a join link (`APP_URL/join/<token>`). The link can always be copied from the pending list.
3. If `COMPOSIO_API_KEY` is set, the invitation is also emailed through **Composio's Gmail tool** from the connected Gmail account.
4. The invitee opens the link, signs in (or signs up) **with the invited email address**, and accepts. A link opened by anyone else is refused.

| Variable | Meaning |
|---|---|
| `APP_URL` | Frontend base URL used in invitation links (defaults to the first `CORS_ORIGINS` entry) |
| `COMPOSIO_API_KEY` | Enables invitation emails |
| `COMPOSIO_USER_ID` | Composio user whose Gmail account is connected (default `default`) |
| `COMPOSIO_GMAIL_ACCOUNT_ID` | Optional: pin a specific connected Gmail account |

To connect Gmail: create a Composio project, add the Gmail toolkit, and connect a Gmail account for the user id you put in `COMPOSIO_USER_ID`. **Settings → Plan & usage** shows whether an active Gmail connection was found.

### Workspace API keys

Owners and admins can create keys in **Settings → API keys**. A key is shown once, stored only as a SHA-256 hash, and acts as the person who created it inside that workspace:

```bash
curl http://localhost:8000/api/jobs -H "Authorization: Bearer rai_…"
```

Revoking a key stops it immediately. `last_used_at` is updated on every call.

---

## 5. External services and their limits

**Settings → Plan & usage** checks every key the backend runs on and shows live limits where the provider exposes them (cached for one minute; **Refresh** re-checks).

| Service | Used for | Variable | What the page shows |
|---|---|---|---|
| Google Gemini | Resume parsing | `GEMINI_API_KEY` | Key validity and `PARSE_CONCURRENCY` (Google has no quota API) |
| GitHub | Repository verification | `GITHUB_TOKEN` | Core and search rate limits, with reset times |
| Firecrawl | LinkedIn lookups | `FIRECRAWL_API_KEY` | Credits used this billing period |
| Apify | LinkedIn fallback | `APIFY_TOKEN` | Monthly spend against your limit |
| Groq | Fact checker, interview questions | `GROQ_API_KEY` | Key validity (Groq reports limits per request) |
| Composio | Invitation emails | `COMPOSIO_API_KEY` | Active Gmail connections |

### LinkedIn verification

`backend/app/services/linkedinScraper.py` looks profiles up through Firecrawl's `fullenrich/people/match` (exact profile URL → headline, employment history, education, skills). It costs **5 Firecrawl credits per profile found** and nothing when no profile matches. Profiles Firecrawl can't resolve, or every profile when `FIRECRAWL_API_KEY` is unset, fall back to the Apify actor. Both return the same shape, so the rest of the verification pipeline is unchanged.

