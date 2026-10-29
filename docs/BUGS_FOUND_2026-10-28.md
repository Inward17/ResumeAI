# Bugs Found: 28 October 2026

| | |
|---|---|
| **Date of review** | 28 Oct 2026 |
| **Branch** | `ccr-0d143dc9-on9bjz` |
| **Code reviewed at** | commit `a15157e` (line numbers below refer to this commit) |
| **Scope** | Backend (`backend/app`), frontend (`frontend/src`), tests |
| **Totals** | **34 bugs**: 29 fixed, 5 open (4 medium, 1 low), see the status update below |

**How to use this file:** when an open bug is fixed, tick its box, fill in the *Fixed in* column with the commit, and re-run the *How to verify* check. "Verified" means the bug was reproduced by running code, not just by reading it. Related reports: [BACKEND_ANALYSIS.md](BACKEND_ANALYSIS.md), [UI_AUDIT.md](UI_AUDIT.md), [UI_UPGRADE_COMPATIBILITY.md](UI_UPGRADE_COMPATIBILITY.md).

---

## Status update: 28 Oct 2026 (later the same day)

**All critical and high bugs are fixed**, plus all frontend medium and low bugs. They were fixed by the UI upgrade, which was done in parallel.

| Commit | What |
|---|---|
| `8768212` | Backend fixes BE-01 to BE-07, plus the job status, department and salary API for FE-02 |
| `417aca0` | `github_score` is null (shown as "Not analysed") when GitHub wasn't verified |
| `a2698f0` (merged in `600a26a`) | UI upgrade: Vite, real URLs, real data only, accessible dialogs, design tokens; fixes FE-01 to FE-11 |

**Still open:** BE-08 (GitHub rate-limit handling), BE-09 (phone/email normalisation for duplicates), BE-10 (GitHub URL parsing), BE-11 (cascade delete), BE-12 (mount the AI-summary route).

**How the fixes were checked:**
- `tests/test_bug_fixes_2026_10_28.py`: one regression test per fixed backend bug. Every test fails on the code before the fix and passes after.
- Full suite: 330 tests pass with the embedding model stubbed.
- The **real backend** (in-memory MongoDB, auth disabled) seeded candidates through the real verification and scoring code, and the **real built UI** was clicked through in Chromium at desktop and phone sizes:
  - jobs, Drafts tab, pipeline, refresh on `/jobs/:id`, the dossier at `?candidate=`, Escape to close, and interviews all worked;
  - no HTTP errors and no horizontal overflow.
- Credibility now reflects real checks. A candidate whose LinkedIn matched the resume scored 92.5 ("verified"); one with a mismatched name and company scored 52.5 ("unverified", with discrepancies recorded).

**Action needed after deploying:**
- **Re-run verification for existing candidates.** Scores stored before these fixes still contain the old bugs (web check counted as 0, LinkedIn counted as 100, and so on).
- **Rename the frontend environment variables** from `REACT_APP_*` to `VITE_*` (see `frontend/.env.example`).

---

## Summary

| ID | Severity | Area | Bug | Status |
|---|---|---|---|---|
| FX-01 | Critical | Backend | No uploaded resume ever reached the candidate list (crash in `_create_application`) | ✅ Fixed `a15157e` |
| FX-02 | Critical | Backend | Bulk uploads processed one at a time and lost on restart | ✅ Fixed `2e22574` |
| FX-03 | High | Backend | LinkedIn (Apify) scrape froze the whole server | ✅ Fixed `2e22574` |
| FX-04 | High | Security | API had no authentication; every user saw every job | ✅ Fixed `2e22574` |
| FX-05 | High | Backend | Candidate list capped at 100, with 2–3 DB queries per candidate | ✅ Fixed `2e22574` |
| FX-06 | Medium | Backend | 4–6 Gemini calls per resume, no retry on rate-limit errors | ✅ Fixed `2e22574` |
| FX-07 | Medium | Backend | Embeddings computed on the event loop (blocked other work) | ✅ Fixed `2e22574` |
| FX-08 | Medium | Security | Duplicate-candidate check could overwrite another user's candidate | ✅ Fixed `2e22574` |
| FX-09 | Medium | Frontend | Fake upload progress ("processed by AI" after 1.5 s; Remaining = 5 − n) | ✅ Fixed `2e22574` |
| FX-10 | Low | Backend | Candidate phone number always blank | ✅ Fixed `2e22574` |
| FX-11 | Low | Tests | Test runs wrote uploaded files into the repo's `resumes/` folder | ✅ Fixed `2e22574` |
| BE-01 | Critical | Backend | Web check never counts toward credibility (wrong field names) | ✅ Fixed `8768212` |
| BE-02 | Critical | Backend | Web check searches degree / job description instead of university / company | ✅ Fixed `8768212` |
| BE-03 | High | Backend | Agent mode (`USE_AGENT_SYSTEM=true`) cannot start: modules never committed | ✅ Fixed `8768212` |
| BE-04 | High | Backend | GitHub repo size treated as bytes instead of KB, so commit-depth score ≈ 0 | ✅ Fixed `8768212` |
| BE-05 | High | Backend | Open-source contribution check almost always finds 0 | ✅ Fixed `8768212` |
| BE-06 | High | Backend / UI | "Role Match %" in the UI is really the GitHub score | ✅ Fixed `8768212`, `417aca0` |
| BE-07 | High | Backend | LinkedIn scores 100% just for existing; never compared with the resume | ✅ Fixed `8768212` |
| BE-08 | Medium | Backend | GitHub rate limits not respected (403 treated as final, `Retry-After` ignored) | ⬜ Open |
| BE-09 | Medium | Backend | Duplicate check uses exact name + phone (formatting creates duplicates) | ⬜ Open |
| BE-10 | Medium | Backend | GitHub username taken from URL with query string (`user?tab=…`) | ⬜ Open |
| BE-11 | Medium | Backend | Deleting a job leaves its applications, tasks and resume files | ⬜ Open |
| BE-12 | Low | Backend | `ai_analysis_routes` (AI candidate summary) exists but is never mounted | ⬜ Open |
| FE-01 | High | Frontend | Blank white page when Firebase settings are missing | ✅ Fixed `a2698f0` |
| FE-02 | High | Frontend | Draft jobs are published as Active; department and salary are discarded | ✅ Fixed `8768212` (API), `a2698f0` (UI) |
| FE-03 | Medium | Frontend | Dashboard shows invented numbers (1.2k, 24, 8, 78%) when data is empty | ✅ Fixed `a2698f0` |
| FE-04 | Medium | Frontend | Interview page shows invented candidate details ("Senior Developer", fake email/phone, 94%) | ✅ Fixed `a2698f0` |
| FE-05 | Medium | Frontend | Candidate status dropdown lacks the backend default "Under Review" | ✅ Fixed `a2698f0` |
| FE-06 | Medium | Frontend | Candidate modal: skills/education/experience/links always empty; placeholder bio | ✅ Fixed `a2698f0` |
| FE-07 | Medium | Frontend | Candidate modal can't be closed with Escape; no focus trap | ✅ Fixed `a2698f0` |
| FE-08 | Low | Frontend | Refresh / Back button loses the current page (single URL for all views) | ✅ Fixed `a2698f0` |
| FE-09 | Low | Frontend | Upload picker hides `.txt` although the backend accepts it | ✅ Fixed `a2698f0` |
| FE-10 | Low | Privacy | Third-party PostHog analytics script with someone else's project key | ✅ Fixed `a2698f0` |
| FE-11 | Low | Frontend | Low-contrast grey text (2.56:1) used in 110 places | ✅ Fixed `a2698f0` |

The many UI-only / mock features (Settings page, Profile save, notifications, etc.) are listed separately in [UI_AUDIT.md](UI_AUDIT.md). They are unbuilt features rather than bugs and are not counted here.

---

## ✅ Fixed during the review (before the bug list was written)

- [x] **FX-01: No uploaded resume ever reached the candidate list.** *Critical · verified · fixed in `a15157e`*
  - Since commit `93c23e4` (3 Apr 2026), `_create_application` called `run_unified_skill_scoring(..., preferred_skills=...)`, an argument the function didn't accept.
  - Every resume was parsed and verified, then raised `TypeError`. The error was only printed, so no application record was written and no candidate appeared in the UI.
  - Location: `backend/app/routes/resume.py` (call) and `backend/app/services/skill_matching/pipeline.py` (signature).
  - Verify: `pytest tests/test_routes_resume.py -k real_skill_scoring`.
- [x] **FX-02: Bulk uploads processed one at a time and lost on restart.** *Critical · fixed in `2e22574`*
  - FastAPI `BackgroundTasks` run sequentially, and a global `asyncio.Semaphore(1)` serialised Gemini parsing. Queued work lived in memory and vanished on restart or reload.
  - Replaced by a MongoDB-backed queue (`backend/app/services/task_queue.py`).
  - Verify: `pytest tests/test_task_queue.py` (includes 100-resume end-to-end test).
- [x] **FX-03: LinkedIn scrape froze the whole server.** *High · fixed in `2e22574`*
  - The blocking Apify `actor.call()` ran inside async code (`backend/app/services/linkedinScraper.py`). It now runs in a thread.
- [x] **FX-04: API had no authentication.** *High · fixed in `2e22574`*
  - Any request was accepted, and all users shared all jobs and candidates.
  - Now: every route requires a Firebase/Google OAuth 2.0 ID token, and jobs are owner-scoped (`backend/app/auth.py`).
  - Verify: `pytest tests/test_auth.py`.
- [x] **FX-05: Candidate list capped at 100.** *High · fixed in `2e22574`*
  - `to_list(length=100)` plus per-candidate queries in `get_job_candidates`. Now batched, with no cap.
  - Verify: `pytest tests/test_routes_resume.py -k more_than_100`.
- [x] **FX-06: Excess Gemini calls.** *Medium · fixed in `2e22574`*
  - langextract's default 1,000-char chunks meant 4–6 calls per resume, and there was no retry on 429.
  - Now one chunk per resume, with backoff retries (`backend/app/services/parser.py`).
- [x] **FX-07: Embeddings blocked the event loop.** *Medium · fixed in `2e22574`*
  - `generate_embedding` was called directly in async code (`resume.py`, `job_routes.py`). Now runs via `asyncio.to_thread`, and the model load is thread-safe.
- [x] **FX-08: Cross-user candidate overwrite.** *Medium · fixed in `2e22574`*
  - The duplicate check matched across all users, so one recruiter's upload replaced another's candidate data. Now scoped by `owner_uid`.
- [x] **FX-09: Fake upload progress.** *Medium · fixed in `2e22574`*
  - `CandidatePipeline.jsx` now polls `GET /api/v1/jobs/{id}/tasks` for real queued/processing/done/failed counts.
- [x] **FX-10: Candidate phone always blank.** *Low · fixed in `2e22574`*
  - The route read `phone`, but the parser stores `phone_number`.
- [x] **FX-11: Tests polluted the repo.** *Low · fixed in `2e22574`*
  - Upload tests wrote files to `resumes/`. Now isolated in a temp directory (`tests/conftest.py`).

---

## Backend bugs (☐ open · ☑ fixed)

| ☐ | ID | Severity | Location (at `a15157e`) | Problem and impact | How to verify | Suggested fix | Fixed in |
|---|---|---|---|---|---|---|---|
| ☑ | **BE-01** | Critical | `backend/app/services/unified_verification.py` L366–375 | `verify_profile` returns keys `education`/`experience`, but the model is only built `if ws.get("university")` / `ws.get("company")`, so `experienceMatch` is always 0. The web check keeps its 30% weight, so **every candidate's credibility is pulled down**. *Verified:* an all-"Verified" (90%) web result gave credibility 0. | Run `_build_and_persist` with a web result scored 90 and check `matchScore.experienceMatch` (expected 90) | Read the `education`/`experience` keys | `8768212` |
| ☑ | **BE-02** | Critical | `backend/app/routes/resume.py` L377–378, `services/verifier.py` (`_clean_education_name`) | Whole resume lines are sent for web verification and cut at the first comma: "B.Tech in CS, IIT Delhi, 2021" → searches **"B.Tech in CS"**; "Software Engineer at Google (…) – Built…" → searches the job description. *Verified.* | `extract_entities` + clean functions on a sample line | Use the parser's clean `university`/`company` lists (already stored on the candidate) | `8768212` |
| ☑ | **BE-03** | High | `backend/app/agent/core/agent_loop.py` L26–33 | Imports `agent_runs_col` (missing from `database.py`) and modules never committed (`agent.config`, `agent.memory`, `decision.scoring_engine`, `core.planner`, `core.executor`, `core.verifier`, `models.agent_models`). With `USE_AGENT_SYSTEM=true`, **verification fails for every candidate**. *Verified* (ImportError). | `python -c "import app.agent.core.agent_loop"` | Commit the missing modules or delete the agent package and flag | `8768212` |
| ☑ | **BE-04** | High | `backend/app/services/github_services_v2/github_service.py` L306 | GitHub reports repo `size` in **KB**, but the code divides by 10,000 as if it were bytes ("1 commit ≈ 10 KB"). The commit-depth sub-signal (25% of RepositoryAuthenticity) is ≈ 0 for almost everyone. | Repo of 500 KB → `avg_commits` 0.05 | Divide by ~10 (KB), or use the real commit count from deep analysis | `8768212` |
| ☑ | **BE-05** | High | `backend/app/services/github_services_v2/analysis/behavioral_analysis.py` L294 | OSS detection skips repos owned by the candidate, but forks listed under a user *are* owned by that user, so they are never checked. OSSContribution ≈ 0 for nearly everyone while weighing 10% of the GitHub score. | Candidate with an upstream-merged fork still gets 0 | Check the fork's `parent` repo for commits by the user | `8768212` |
| ☑ | **BE-06** | High | `backend/app/routes/resume.py` L836 | Response field `jd_match_score` is filled from `skills_match_score` (the **GitHub** score). The real JD match is `score_details.jd_match_score` (0–10). The UI shows the GitHub score as "Role Match %". | Compare the two fields in `GET /api/v1/jobs/{id}/candidates` | Return the real JD match (×10 for %), or rename the field | `8768212`, `417aca0` |
| ☑ | **BE-07** | High | `backend/app/services/unified_verification.py` L386, L440 | LinkedIn contributes **100/100 for merely being scraped**, and `discrepancies` is a `TODO`. LinkedIn data is never compared with resume claims. | Any scraped profile → full 20% | Compare positions/education with the resume; score on agreement | `8768212` |
| ☐ | **BE-08** | Medium | `backend/app/services/github_services_v2/github_client.py` L107 | Any 403 is treated as "rate limited" and deep analysis is skipped. 429/5xx retries use fixed 0.5–2 s waits, ignoring `Retry-After` and `X-RateLimit-Reset`. Large batches lose GitHub analysis. | Run >25 candidates with one token | Honour reset headers; queue GitHub work per token | |
| ☐ | **BE-09** | Medium | `backend/app/routes/resume.py` L280 | Duplicate check uses exact `full_name + phone_number`. "+91 98200 11111" vs "9820011111" creates duplicates. | Upload the same resume with a reformatted phone | Normalise phone (E.164) and email before matching | |
| ☐ | **BE-10** | Medium | `backend/app/services/github_services_v2/github_service.py` L364 | `"github.com/user?tab=repositories".split("/")[-1]` gives username `user?tab=repositories`, so the GitHub lookup fails. Usernames are also not validated before being put into API paths. | Resume with a query-string GitHub URL | Parse with `urllib.parse`; validate `^[A-Za-z0-9-]{1,39}$` | |
| ☐ | **BE-11** | Medium | `backend/app/routes/job_routes.py` (`delete_job`) | Deleting a job leaves applications, tasks and uploaded resume files behind (personal data retention). | Delete a job, count `applications` for it | Cascade delete, or soft-delete with a retention job | |
| ☐ | **BE-12** | Low | `backend/app/routes/ai_analysis_routes.py`, `backend/app/main.py` | The Gemini candidate-analysis route is never included in the app, so the UI can never show a real AI summary. | `GET /api/jobs/{id}/candidates/{cid}/analysis` → 404 | Mount the router (it already has the owner check) and call it from the modal | |

## Frontend bugs (☐ open · ☑ fixed)

| ☐ | ID | Severity | Location (at `a15157e`) | Problem and impact | How to verify | Suggested fix | Fixed in |
|---|---|---|---|---|---|---|---|
| ☑ | **FE-01** | High | `frontend/src/firebase.js` L18 | Without `REACT_APP_FIREBASE_*` env vars, `getAuth` throws `auth/invalid-api-key` at import and the **whole app is a blank white page**. *Verified.* | Build without `frontend/.env`, open `/login` | Check config at startup and render an error screen | `a2698f0` |
| ☑ | **FE-02** | High | `frontend/src/services/jobService.js` L41 (`transformJobToAPI`); `components/JobModal.jsx` | `is_active: status !== 'Closed'`, so a job saved as **Draft is published as Active**, and the Drafts tab is always empty. `department`, `salaryMin` and `salaryMax` are collected but never sent, so they are lost. | Create a Draft job and reload | Add `status`, `department` and salary to the API model and transform | `8768212` (API), `a2698f0` (UI) |
| ☑ | **FE-03** | Medium | `frontend/src/components/Dashboard.jsx` L58–65 | Falls back to `'1.2k'`, `24`, `8` when real values are 0; "78% OPTIMAL" and "+12.5%" are hard-coded. New users see fake statistics. | Log in with an empty workspace | Show real values or an empty state | `a2698f0` |
| ☑ | **FE-04** | Medium | `frontend/src/components/QAPage.jsx` L176–185 | Missing fields fall back to "Senior Developer", "candidate@example.com", "+91 98200 45XXX", 94% and a canned AI quote. Real candidates are shown with invented details during interviews. | Open Take Interview for any candidate | Show "—" / hide the field | `a2698f0` |
| ☑ | **FE-05** | Medium | `frontend/src/components/CandidateModal.jsx` L9 | Status options don't include "Under Review" (the backend default), so new candidates display as "New". Statuses differ across screens. | Open a fresh candidate | Shared status enum for frontend and backend | `a2698f0` |
| ☑ | **FE-06** | Medium | `frontend/src/components/CandidateModal.jsx` (L220 "Last sync: 14 min ago"), `services/jobService.js` (`getJobCandidates`) | The API response doesn't include skills, education, experience or GitHub/LinkedIn links, so those sections are always empty. The bio is a generic placeholder; "Top 1% expertise" and "Last sync" are hard-coded. | Open any candidate | Return these fields from the API (or add `GET /candidates/{id}`) | `a2698f0` |
| ☑ | **FE-07** | Medium | `frontend/src/components/CandidateModal.jsx` | Custom overlay: Escape doesn't close it, focus isn't trapped, no `role="dialog"`. *Verified in browser.* | Open modal, press Esc | Use the existing Radix `Dialog` (`components/ui/dialog.jsx`) | `a2698f0` |
| ☑ | **FE-08** | Low | `frontend/src/App.js` | All views live under `/dashboard` and switch via React state, so refresh and Back lose the page and links can't be shared. | Open a pipeline, press F5 | Add real routes (`/jobs/:id`, …) with React Router | `a2698f0` |
| ☑ | **FE-09** | Low | `frontend/src/components/CandidatePipeline.jsx` L276 | `accept=".pdf,.docx,.doc"` hides `.txt`, which the backend supports. | Open file picker | Add `.txt` | `a2698f0` |
| ☑ | **FE-10** | Low | `frontend/public/index.html` L98 | PostHog analytics snippet with a hard-coded third-party project key sends usage data to a project you may not own. | View page source | Remove, or use your own key with consent | `a2698f0` |
| ☑ | **FE-11** | Low | `frontend/src/components/*.jsx` (110× `text-slate-400`, 9× `text-slate-300`) | Contrast 2.56:1 / 1.48:1, below WCAG AA (4.5:1). Hard to read. | Contrast checker | Use `slate-500` (4.76:1) or darker | `a2698f0` |

---

## How these were found

- Reading every backend and frontend module.
- Reproducing suspected bugs with small Python scripts against the real functions (MongoDB mocked).
- Running the full test suite: 313 tests pass when the embedding-model download is stubbed. The 7 job-route tests fail in the review sandbox only because it cannot download the model.
- Clicking through all main screens in headless Chromium at 1440 px, 820 px and 390 px with a mocked API.

Safari and Firefox were not tested.
