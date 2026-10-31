# MongoDB → PostgreSQL: how big is the change?

*Analysis of branch `ui-redesign-teams`, 29 Oct 2026. No code was changed.*

## Verdict

| | |
|---|---|
| **Size** | **Large (L)**: about **13–19 person-days** for one developer who knows the code, or 3–4 calendar weeks part-time |
| **Frontend impact** | None if the API keeps returning ids as strings |
| **Data to move** | Tiny: 11 collections, ~150 documents, ~240 KB |
| **Worth it now?** | **No, unless you have a concrete reason** (see [When it is worth it](#when-it-is-worth-it)). The data is document-shaped LLM output, Atlas works, and most of the cost is rewriting code and tests, not moving data. |

The work is spread thin, not concentrated: database calls are scattered directly through routes and services instead of going through one data-access layer. That spreading, not SQL itself, is what makes it Large.

## 1. What touches MongoDB today

**~170 database calls in 19 files** (of 11.6k lines of backend Python), plus 2 scripts and the test fixtures.

| File | DB call lines | Notes |
|---|---|---|
| `app/routes/resume.py` | 30 | Upload, parse → verify → score pipeline, candidate list (3 batched queries), status changes, task progress aggregation |
| `app/routes/org_routes.py` | 29 | Workspace, members, invites, API keys, usage counts |
| `app/org.py` | 12 | Workspace resolution, API key lookup |
| `app/routes/job_routes.py` | 9 | Job CRUD, candidate-count aggregation |
| `app/agent/decision/context_builder.py` | 9 | Optional agent path (`USE_AGENT_SYSTEM`) |
| `app/services/task_queue.py` | 7 | Durable queue: atomic claim, heartbeats, stale recovery |
| `app/services/jd_matching_service.py` | 7 | Legacy, flagged unused in BACKEND_ANALYSIS |
| `app/routes/interview_questions_routes.py` | 5 | Question cache on applications |
| `app/auth.py` | 5 | Job/candidate access checks, user upsert |
| `app/routes/ai_analysis_routes.py` | 4 | Never mounted (legacy) |
| `app/agent/core/agent_loop.py` | 4 | Agent verification writes |
| 8 more files | 1–2 each | Fact checker, evaluations, verification, GitHub writer |
| `scripts/seed_demo.py`, `assign_job_owner.py` | 21 | Demo data and migration helper |

**Operations used:** `find_one` ×61, `update_one` ×37, `insert_one` ×12, `find` ×12, `update_many` ×7, `delete_many` ×7, `count_documents` ×5, `distinct` ×2, `aggregate` ×2, `find_one_and_update` ×1.
**Operators:** `$set` ×41, `$or` ×16, `$in` ×15, `$setOnInsert`/upserts ×4, `$exists`, `$unset`, `$inc`, `$group`/`$cond`/`$sum` (2 pipelines).
**Ids:** `bson.ObjectId` in 9 files. Jobs, orgs, invites and API keys use ObjectId `_id`; candidates (`candidate_id`) and tasks (`task_id`) use UUID strings.

Nothing exotic is used: no GridFS, change streams, transactions, `$lookup`, text indexes or geo queries. Every operation has a direct SQL equivalent; the work is volume, not difficulty.

## 2. Data shapes

| Collection | Docs | Avg size | Shape | In Postgres |
|---|---|---|---|---|
| `orgs`, `org_members`, `users`, `invites`, `api_keys` | 8 | <0.3 KB | Flat | **Plain tables** with foreign keys and unique constraints (e.g. `(org_id, uid)`) |
| `jobs` | 8 | 5.5 KB | Flat + `required_skills[]` + 384-float `jd_embedding` | Table; skills as `text[]`; embedding as `real[]` or `vector(384)` |
| `applications` | 36 | 0.9 KB | Flat + nested `score_details` (incl. `skill_matches[]`) + cached `interview_questions[]` | Table; `score_details` and `interview_questions` as **JSONB** |
| `tasks` | 15 | 0.5 KB | Flat | Table (the queue) |
| `evaluations` | 6 | 0.4 KB | Per-question list | Table + JSONB |
| `candidates` | 35 | 2.8 KB | Deeply nested `parsed` resume from Gemini + `skills_embedding` | Table; `parsed` as **JSONB**; name/phone as generated columns for the de-duplication index |
| `verification_data` (+ `_agent`) | 35 | 1.5 KB | 20 nested Pydantic models (GitHub, LinkedIn, web, discrepancies) | Table; status columns + details as **JSONB** |

Normalising the parsed resume or verification results into dozens of tables would multiply the work for no benefit; nothing queries inside them except name/phone de-duplication.

## 3. Proposed schema (hybrid)

```sql
orgs(id uuid pk, name text, created_by text, created_at timestamptz)
users(uid text pk, email text, name text, picture text, org_id uuid fk → orgs, ...)
org_members(org_id uuid fk, uid text fk, email text, role text check (role in ('owner','admin','member')),
            joined_at timestamptz, primary key (org_id, uid))
invites(id uuid pk, org_id uuid fk, email text, role text, token text unique, status text, expires_at timestamptz, ...)
api_keys(id uuid pk, org_id uuid fk, key_hash text unique, prefix text, created_by text, revoked_at timestamptz, ...)
jobs(id text pk, org_id uuid fk, owner_uid text, title text, description text, status text,
     required_skills text[], preferred_skills text[], jd_embedding real[], posted_at timestamptz, ...)
candidates(candidate_id text pk, owner_uid text, parsed jsonb, filename text, github_username text, linkedin_url text,
           skills_embedding real[],
           full_name text generated always as (parsed->'personal_info'->>'full_name') stored,
           phone text generated always as (parsed->'personal_info'->>'phone_number') stored)
applications(job_id text fk, candidate_id text fk, status text, application_date timestamptz,
             score_details jsonb, interview_questions jsonb, primary key (job_id, candidate_id))
verification_data(candidate_id text pk fk, verification_status jsonb, match_score jsonb, details jsonb, ...)
tasks(task_id text pk, job_id text fk, owner_uid text, filename text, status text, attempts int,
      worker_id text, heartbeat_at timestamptz, created_at timestamptz, error text)
evaluations(job_id text, candidate_id text, questions jsonb, total_score int, ..., primary key (job_id, candidate_id))
```

- **Keep string ids.** `jobs.id` stays `text` holding the existing 24-hex ids, so URLs and the frontend don't change; new rows can use UUIDs. Drop `bson` from the code.
- **Task queue:** the atomic claim becomes

  ```sql
  UPDATE tasks SET status='processing', worker_id=$1, started_at=now(), heartbeat_at=now(), attempts=attempts+1
  WHERE task_id = (SELECT task_id FROM tasks WHERE status='queued' ORDER BY created_at
                   FOR UPDATE SKIP LOCKED LIMIT 1)
  RETURNING *;
  ```

  This is the standard Postgres queue pattern and is as safe across processes as `find_one_and_update`.
- **Aggregations** (candidate counts per job, task progress) become one `GROUP BY` each, which is simpler than today's pipelines.
- **Foreign keys** add integrity Mongo doesn't enforce today, e.g. deleting a job cleans up applications.
- **pgvector** is optional: embeddings are only compared in Python today. Switching to `vector(384)` later would let the database rank candidates.

## 4. Approach options

| Option | Effort | Pros | Cons |
|---|---|---|---|
| **A. SQLAlchemy 2.0 async + asyncpg + Alembic** (recommended) | L | Typed models, migrations, works with FastAPI/Pydantic, easy to test | Most code to write; learning curve if unfamiliar |
| B. Raw `asyncpg` + SQL files | M–L | Fastest at runtime, no ORM | Hand-written SQL in ~170 places, no migration tooling |
| C. "Document tables" (`id`, `data jsonb` per collection) | M | Quickest port: queries become JSONB lookups | Keeps every downside of schemaless data, so most of the reason to switch is lost |

Whatever the option, **first move every DB call behind a small data-access layer** (`app/repositories/…`) while still on MongoDB. That step is useful even if you never migrate: tests stop depending on Mongo internals. It also turns the switch into replacing one module per collection.

## 5. Effort breakdown

| Phase | Work | Estimate |
|---|---|---|
| 0. Data-access layer (still MongoDB) | Move ~170 calls in 19 files behind repository functions; no behaviour change | 3–4 days |
| 1. Schema & tooling | SQLAlchemy models, Alembic baseline, connection pool replacing `database.py`, indexes | 1–2 days |
| 2. Postgres repositories | Implement every repository; task queue with `SKIP LOCKED`; upserts via `ON CONFLICT`; aggregations as `GROUP BY` | 4–6 days |
| 3. Tests | Replace `mongomock-motor` with a real Postgres (CI service container / `testcontainers`); 77 direct `mock_db` uses in 8 of 15 test files (4.8k lines) | 3–4 days |
| 4. Data migration | One script: read Atlas, write Postgres, verify counts. ~240 KB, so it runs in seconds | 0.5–1 day |
| 5. Deploy & docs | Hosted Postgres (Neon or Supabase free tier), `DATABASE_URL` env, Hugging Face secret, CI service, docs | 0.5–1 day |
| Buffer | Agent path (`app/agent`), legacy files, surprises | 1 day |
| **Total** | | **13–19 person-days** |

Dropping the unused legacy files first (`jd_matching_service.py`, `ai_analysis_routes.py`, `models/github_writer.py`, already flagged in BACKEND_ANALYSIS) removes ~13 call sites before you start.

## 6. Risks

- **Regression surface:** the resume pipeline in `routes/resume.py` (941 lines) mixes DB writes with parsing, verification and scoring, so a mistake there silently loses candidates. Phase 0 plus the existing 335 tests mitigate this.
- **Task queue semantics:** heartbeats, stale recovery and attempt limits must behave identically; `tests/test_task_queue.py` covers them.
- **Agent / dual-run path** (`verification_data_agent`) is optional and rarely exercised; decide whether to port it or remove it.
- **Hosting:** Neon/Supabase free tiers sleep or have connection limits. The backend's pool (`RESUME_WORKERS=8` + API) must fit, or use their pooler (PgBouncer) endpoint.
- **Two databases during cut-over:** keep Atlas read-only as a fallback until the Postgres version has run cleanly.

## When it is worth it

Migrate if one of these is a real need:

- Reporting or analytics in SQL across jobs, candidates and teams (funnels, time-to-hire).
- Database-enforced integrity for workspaces, members and applications as teams grow.
- Ranking candidates by vector similarity inside the database (pgvector).
- A hosting or compliance requirement for Postgres.

Otherwise, stay on MongoDB. Do **Phase 0** anyway when touching these files: it's the cheapest step and makes a later migration about half the size.
