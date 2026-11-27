# Running ResumeAI with Docker

`docker-compose.yml` at the repository root runs the backend and the frontend in containers. The backend image is the same one the Hugging Face Space uses (`backend/Dockerfile`); the frontend is built with Vite and served by nginx (`frontend/Dockerfile`).

## Quick start

1. Create `backend/.env` from `backend/.env.example` (MongoDB URL, Firebase project, AI keys).
2. Create `frontend/.env` from `frontend/.env.example` (Firebase web config).
3. Run:

   ```bash
   docker compose --env-file frontend/.env up --build
   ```

4. Open http://localhost:3000. The API is on http://localhost:8000.

`--env-file frontend/.env` gives compose the `VITE_*` values. They are baked into the frontend bundle at build time, so rebuild (`--build`) after changing them.

## What compose sets for you

| Setting | Value | Why |
|---|---|---|
| `PORT` (backend) | `8000` | The image defaults to 7860 for Hugging Face. |
| `CORS_ORIGINS`, `APP_URL` | `http://localhost:3000` | Where the browser loads the app. Override them in your shell or the `--env-file` when you serve on another address. |
| `VITE_API_URL` | `http://localhost:8000` | Unless your env file sets it. |

Everything else comes from `backend/.env` (loaded with `env_file`, never copied into an image: `.env` files are in both `.dockerignore` files).

## Local MongoDB (optional)

```bash
docker compose --env-file frontend/.env --profile local-db up --build
```

and set `MONGO_URL=mongodb://mongo:27017` in `backend/.env`. Data stays in the `mongo-data` volume.

## Data

- Uploaded resumes: `resumes` volume.
- Downloaded embedding models: `hf-cache` volume, so restarts don't download them again.

`docker compose down` keeps the volumes; `docker compose down -v` deletes them.

## Notes

- `AUTH_DISABLED=true` refuses to start on port 7860 or on Hugging Face (`SPACE_ID`). Use it only for local testing, together with `VITE_AUTH_DISABLED=true` in the frontend env file.
- Google sign-in needs `localhost` (or your host) in Firebase → Authentication → Authorized domains.
- Calendar, mail and Slack integrations need `OAUTH_REDIRECT_BASE_URL` pointing at the backend address the browser can reach.
