# ResumeAI Automation Platform (Complete Architecture & Development Guide)

## 📌 Project Overview
**ResumeAI** is an advanced full-stack recruitment automation framework. It accelerates and scales the technical screening process using semantic JD-to-resume matching, multi-source background verification (GitHub, LinkedIn, DuckDuckGo), and deep AI insights.

### Platform Topology
- **Frontend**: React 19 SPA, Tailwind CSS, shadcn/ui, Firebase Authentication.
- **Backend Framework**: High-performance asynchronous FastAPI & Uvicorn.
- **Database**: MongoDB (via async Motor driver).
- **Core AI**: Google Gemini 2.5 Flash via `langextract` for unstructured parsing.
- **Embeddings**: Local dense vectors (`all-MiniLM-L6-v2`) via FastEmbed for Cosine Similarity.
- **Verification Nodes**: GitHub API (Code & Repos), Apify Actors (LinkedIn headless scraper), DuckDuckGo (Fuzzy Web queries via RapidFuzz).

---

## 🏗 System Architecture & Workflow

### 1. Legacy Verification Pipeline (Parallel Sync)
The initial baseline design works entirely synchronously over isolated background tasks to fulfill jobs efficiently:
1. **Job Request**: Recruiter initiates an opening on the UI.
2. **Resume Drop**: Resumes undergo deep extraction (`parser.py`).
3. **Parallel Verifier** (`unified_verification.py`):
   - Immediately dispatches independent, non-blocking asynchronous scrape commands to GitHub, LinkedIn, and DuckDuckGo using `asyncio.gather`.
4. **Scoring Engine**: Evaluates JD match. (5 points: 2 for parsed textual experience, 3 for deep GitHub repository stack similarities).
5. **UI Relay**: React fetches and displays parsed matrices.

*This mode is highly efficient but lacks error resilience against throttling and cannot gracefully skip verifications dynamically.*

### 2. Version 2 -> Agentic Verification Pipeline (Intelligent Node)
We overhauled the architecture to introduce an intelligent, deterministic **Agent Layer**. This bridges the gap between raw parsing and brute-force parallel execution, bringing memory and logical deduplication.

#### Agent Layer Philosophy
The core principle was **Decoupling Logic from Execution**. 
- The existing backend API logic *(unchanged)*.
- The new agent decides *if*, *when*, and *what* to execute.

#### Sub-Systems
1. **Context Builder**: Pulls Candidate/App metadata and establishes **Signal Freshness**. (e.g. GitHub caches for 7 days, LinkedIn for 14 days).
2. **Rule Engine**: Deterministic boundary controller. Automatically overrides to `SKIP` if the URL is missing (e.g., no GitHub URL in PDF) or if the signal is marked natively fresh.
3. **Scoring Engine**: Handles priority threshold logic based on feature matrices.
4. **Gemini Planner**: Only triggered as an absolute last resort if ambiguous verification overlaps exist.
5. **Executor Wrappers**: Executes only the explicitly approved tools inside `asyncio.gather` while preventing mass 503 throttling cascades.

---

## 🚀 Environment Configuration & Agent Toggles

The project is natively flexible. By modifying parameters inside the backend `.env`, you can toggle execution modes dynamically.

| Environment Variable | Description |
|----------------------|-------------|
| `USE_AGENT_SYSTEM` | boolean (`true`/`false`). Activates wrapping requests through `agent_loop.py` instead of the legacy `unified_verification.py`. |
| `DUAL_RUN` | boolean (`true`/`false`). If `true`, the agent explicitly forces `target_collection` to push to `verification_data_agent` in MongoDB to maintain DB parity tests entirely isolated from the standard frontend app. |
| `AGENT_TOOL_TIMEOUT_SEC` | Integer (default: `150`). Hard ceiling constraint applied to individual scraping wrappers to cleanly kill hanging Apify headless actors or large GitHub parsing trees. |
| `AGENT_TOTAL_TIMEOUT_SEC`| Integer (default: `300`). Total master `asyncio.wait` ceiling for the core agent to loop, execute, merge db records, and close. |

---

## 📅 Timeline: Agent Stabilization Upgrades & Fixes

Our upgrade from Legacy to Agentic introduced friction points natively caused by API throttling ceilings, DB schema translations, and parsing anomalies. Here is exactly what we modified to reach a **100% Stable Release Pipeline**:

1. **DB Orphan Persistence (Fix 1)**: Early agent results were orphaned within MongoDB because the payload execution wasn't explicitly injecting and associating the `candidateId` keys back down to the target field on upsert. We manually patched `update_fields["candidateId"]` inside the Executor flush.
2. **Signal Merging & Preservation Cache (The Score Drop Fix)**: The Rule Engine is smart—it skips recently verified signals. But initially, when the Agent bypassed GitHub, the final `matchScore` recalculation computed 0 because GitHub was "missing" from the active loop payload. We patched `agent_loop.py` to **Read the DB first**, then map missing skipped data natively into the final arithmetic to sustain existing verifications (e.g., merging `overallCredibility: 39.27`).
3. **PDF Hyperlink Embedding Escapes**: The Gemini Flash pipeline occasionally failed to OCR or extract standard Github/LinkedIn URLs as they were stored as *Hyperlink Annotations* behind generic blue text. We integrated `pdfminer` directly inside `resume.py`. If Gemini string extraction fails (`not github_url`), the code natively reads document `A.URI` objects and forces the extraction explicitly.
4. **Gemini "String Capture" Bug**: Gemini systematically pulled the string `"GitHub"` instead of the profile URL when OCR'ing resumes. We introduced explicit domain substring validations checking for `.com` in the text blob, forcing it into our PDF Hyperlink fallback engine when false extraction triggered.
5. **Legacy Score Migration (`score100` Sync)**: Our Agent code stored results differently than the native legacy loop. (Legacy logic had no `success` boolean parameter, and cached raw integers inside a `score100` field). We added deterministic `OR` fallback clauses across `agent_loop.py` to correctly map `score100 > 0` directly against `success: True`.
6. **API Throttling Silence Logs**: Apify limits and Gemini `503 Service Unavailable` disconnects were quietly dying within the loop catchers resulting in frontend hangs with empty dashboards. We exposed standard UI logging to explicitly bubble `[PARSE] ❌ FAILED for {task_id}` timeouts into the main Uvicorn terminal feed.

---

## 🛠️ Frequently Faced Problems & Solutions

**1. "Zero-Vector Fastembed Initializations / ONNXRuntime Errors"**
*   **Cause**: You will occasionally see `[WinError 1114] DLL initialization routine failed` when hitting `fastembed` locally because of Windows PyTorch package mismatches or background hardware cache threading. 
*   **Fix**: These are non-fatal. The backend falls back to standard keyword overlap when JD Matching embeddings fail to natively allocate vector trees. To permanently silence, you must natively re-compile PyTorch or ensure dependencies explicitly match Python 3.10 environments without overriding `c10.dll` paths in windows. 

**2. "Apify Actor Hard Limits"**
*   **Cause**: Error logs such as `❌ You hit hard limit for the total number of runs` populate instantly natively inside the Agent Executor.
*   **Fix**: The `linkedin_scraper` is limited to free-tier bounds on Apify. Wait for month reset, transition to standard plans, or rely inherently on Github and WebSearch verification arrays for overall Credibility Matrix scores.

**3. "Gemini 503 Disconnected without sending response"**
*   **Cause**: Rapid concurrent resume uploads aggressively throttles Gemini's free tier RPS thresholds, triggering connection closing mid-parse.
*   **Fix**: This is inherently standard for multi-parse batch scenarios. Simply retry the specific candidate document sequentially roughly ~60 seconds afterward. The agent loop naturally handles the failed state correctly.

---

## 🧠 The Math Behind the Math (Scoring Architecture)

If you are debugging candidate scoring, here is exactly how numbers are calculated natively inside the application:

1. **Job Description (JD) Match Score (out of 10)**
   - Stored in the `evaluations` collection.
   - Designed to measure *fitness for the role* via semantic embeddings (`all-MiniLM-L6-v2`).
   - `resume_match_score` (Base 0–4 Points): Tests raw OCR extracted text against the Job required skills. Falls back to RapidFuzz string overlap if local vectors fail.
   - `github_repository_match` (Base 0–6 Points): Tests the repository names, commit tags, and languages fetched during GitHub verification against the JD skills.

2. **Overall Credibility / Verification Score (%)**
   - Stored inside `verification_data` as `matchScore.overallCredibility`. 
   - Designed to measure *whether the person is real or lying*.
   - Evaluated as a weighted aggregate of three sources:
     - **GitHub (50% Weight)**: Is the GitHub account active? Does code depth imply seniority?
     - **LinkedIn (20% Weight)**: Did Apify successfully resolve a valid profile structure?
     - **Web Search (30% Weight)**: Did DuckDuckGo successfully link the parsed companies and universities to canonical real-world entities?

---

## 🧭 Project Directory & Key File Mapping
If you need to edit logic, jump straight to these files natively:

- **Agent Framework**: `backend/app/agent/`
  - *Heart of Agent*: `core/agent_loop.py`
  - *Conditionals*: `decision/rule_engine.py` (Edit here to add new skips).
  - *Data Combiner*: `decision/context_builder.py` (Edit here for MongoDB hydration).
- **Core Scraping Services (Unchanged)**: `backend/app/services/`
  - *Gemini Extraction*: `parser.py`
  - *DuckDuckGo Engine*: `search.py`
  - *Apify Hooks*: `linkedinScraper.py`
  - *Fastembed Semantic Math*: `jd_matching_service.py` 
- **Legacy Verification Trigger**: `backend/app/services/unified_verification.py`
- **Frontend Dashboard Components**: `frontend/src/components/`
  - *Main Table View*: `JobPostings.jsx`
  - *Deep Analytics Modal*: `CandidateModal.jsx`

---

## 🌿 Git Branching Strategy
This project relies on explicit branch protections to preserve stable states:
- `verification4`: The golden **Legacy Pipeline Branch**. This branch contains absolutely *0* Agentic/AI Node logic. If the Agent loops ever fundamentally break in production, `checkout verification4` for a completely functional, dumb, parallel hardcoded pipeline.
- `agentic-mode`: The intelligent overlay branch containing the `agent/` directories, intelligent merging logic, semantic rulesets, and PDF URI parsers. 

---

## 📂 Pending Work & Future Expansion
- Replace or mock the Apify Actor locally running a Puppeteer node headless instance to completely eliminate rate boundaries.
- Introduce `gunicorn` threading configs to handle asynchronous parallelization explicitly across CPU cores to offset the native Fastembed local execution burden.

---

## 🏃 Setup & How to Run Locally

### Backend
1. **Activate Environment**: `cd backend` -> `.\venv\Scripts\activate` (Windows)
2. **Setup Envs**: Ensure your `.env` contains `MONGO_URL`, `GEMINI_API_KEY`, and `APIFY_API_TOKEN`. Set Agent toggles as described above.
3. **Start Server**: `uvicorn app.main:app` (Runs on `http://127.0.0.1:8000`)

### Frontend
1. **Navigate**: `cd frontend`
2. **Start App**: `npm start` (Runs on `http://localhost:3000`)

