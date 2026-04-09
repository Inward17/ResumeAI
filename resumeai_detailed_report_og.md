# ResumeAI: Comprehensive Project Developer & Architecture Report
> **v5.0 Algorithms & Implementation Edition**: An exhaustive blueprint covering macro architecture, every algorithm used across the system, their mathematical formulas, and the exact files where each is implemented.

---

## 📑 Detailed Table of Contents
1. [Executive Summary & Product Vision](#1-executive-summary--product-vision)
2. [Macro System Architecture & Orchestration Strategy](#2-macro-system-architecture--orchestration-strategy)
3. [Deep-Dive File Hierarchy & Component Breakdown](#3-deep-dive-file-hierarchy--component-breakdown)
4. [Implementation Deep-Dive: FastApi & AsyncIO Orchestration](#4-implementation-deep-dive-fastapi--asyncio-orchestration)
5. [Algorithms Used & Their Implementation Areas](#5-algorithms-used--their-implementation-areas)
    - 5.1 [Algorithm: Levenshtein Distance (Fuzzy String Matching)](#51-algorithm-levenshtein-distance-fuzzy-string-matching)
    - 5.2 [Algorithm: CLS Pooling & L2-Normalized Cosine Similarity](#52-algorithm-cls-pooling--l2-normalized-cosine-similarity)
    - 5.3 [Algorithm: Jaccard Index (Structural Pre-Filter)](#53-algorithm-jaccard-index-structural-pre-filter)
    - 5.4 [Algorithm: Top-K% Mean Aggregation (Code Similarity Scoring)](#54-algorithm-top-k-mean-aggregation-code-similarity-scoring)
    - 5.5 [Algorithm: Weighted Arithmetic Mean with Max-Bonus (Skill Scoring)](#55-algorithm-weighted-arithmetic-mean-with-max-bonus-skill-scoring)
    - 5.6 [Algorithm: Dynamic Weight Redistribution (Signal Fusion)](#56-algorithm-dynamic-weight-redistribution-signal-fusion)
    - 5.7 [Algorithm: Linear Decay Function (Recency Scoring)](#57-algorithm-linear-decay-function-recency-scoring)
    - 5.8 [Algorithm: Behavioral Authenticity Composite](#58-algorithm-behavioral-authenticity-composite)
    - 5.9 [Algorithm: Population Standard Deviation (Confidence Level)](#59-algorithm-population-standard-deviation-confidence-level)
    - 5.10 [Algorithm: LRU Eviction with SHA-256 Keying (Embedding Cache)](#510-algorithm-lru-eviction-with-sha-256-keying-embedding-cache)
    - 5.11 [Algorithm: Hash-Map Alias Resolution (Skill Normalizer)](#511-algorithm-hash-map-alias-resolution-skill-normalizer)
    - 5.12 [Algorithm: Deterministic Rule Engine (Red Flag Generation)](#512-algorithm-deterministic-rule-engine-red-flag-generation)
    - 5.13 [Algorithm: LLM Chain-of-Fallback Arbitration](#513-algorithm-llm-chain-of-fallback-arbitration)
6. [Master Algorithm-to-File Cross-Reference Table](#6-master-algorithm-to-file-cross-reference-table)
7. [Implementation Deep-Dive: The 15-Step GitHub Pipeline](#7-implementation-deep-dive-the-15-step-github-pipeline)
8. [Implementation Deep-Dive: Unified Skill Scoring Pipeline](#8-implementation-deep-dive-unified-skill-scoring-pipeline)
9. [Implementation Deep-Dive: System Regression Testing](#9-implementation-deep-dive-system-regression-testing)
10. [Implementation Deep-Dive: The Frontend Service Tier & UX State](#10-implementation-deep-dive-the-frontend-service-tier--ux-state)
11. [Data Persistence & Pydantic Schema Guards](#11-data-persistence--pydantic-schema-guards)
12. [Defensive Engineering & Lock Mechanics](#12-defensive-engineering--lock-mechanics)

---

## 1. Executive Summary & Product Vision

**ResumeAI** evaluates a candidate's digital footprint instead of just keyword-matching a resume. Utilizing three separate intelligence layers—**Google Gemini (Zero-shot NLP)**, **BGE-Large (Semantic Transformers)**, and **CodeBERT (Syntax Clone Checkers)**—the software assigns an "Authenticity Score". This evaluation operates synchronously masking extreme backend complexity inside an elegant React `shadcn/ui` Dashboard.

### 1.1 Core Design Philosophy
The system avoids monolithic AI frameworks (LangChain, CrewAI) in favour of deterministic `asyncio`-based orchestration. Every pipeline step is explicit, testable, and debuggable. ML models are loaded lazily behind `asyncio.Lock()` double-check patterns, and every scoring formula is defined by mathematical constants in a single centralised configuration (`config.py`).

---

## 2. Macro System Architecture & Orchestration Strategy

### 2.1 The Two-Tiered Separation of Concerns
The system comprises a fully decoupled client-server architecture:
- **Frontend (React 19 / Tailwind / Radix UI):** Pure SPA utilizing HTTP long-polling and specific Service classes manipulating state logic. The color palette follows an "Indigo Neural" theme binding strict gradient layers programmatically.
- **Backend (Python / FastAPI / Motor / Uvicorn):** Operates purely asynchronously using ASGI. It guarantees that an HTTP worker evaluating heavy NLP doesn't permanently block port `8000`.

### 2.2 The Custom Orchestrator Pattern
ResumeAI explicitly bypasses `LangChain` orchestration layers within the active logic. Instead, the backend employs **Deterministic Python Orchestration**, split into:
1. **Parallel Execution (Wide)**: Launching GitHub REST trees, LinkedIn scraping requests, and Google Searches simultaneously using `asyncio.gather()`.
2. **Sequential Pipelines (Deep)**: Inside the GitHub block, a strict 15-step pipeline operates rigidly to circumvent 3rd-party API rate limit blocking.

---

## 3. Deep-Dive File Hierarchy & Component Breakdown

### 3.1 Backend Application Space (`backend/`)
```text
backend/app/
├── main.py                          # Initializer of FastAPI, CORS limits, and Routing Trees.
├── database.py                      # Async MotorClient (MongoDB) Connection Singleton.
├── routes/                          # Translates network routes /api/v1/ to logic endpoints.
├── services/
│   ├── unified_verification.py      # Central Concurrency Hub (asyncio.gather).
│   ├── parser.py                    # Gemini 2.x API Wrapper / JSON extraction.
│   ├── embedding_service.py         # MiniLM-L6-v2 (384-dim) embeddings + cosine similarity.
│   ├── skill_matching/              # Unified, evidence-weighted semantic skill scoring.
│   │   ├── normalizer.py            # Hash-map alias resolution (100+ aliases).
│   │   ├── section_embedder.py      # Text extraction + concurrent section embedding.
│   │   ├── evidence_scorer.py       # Weighted arithmetic mean + max-bonus scoring.
│   │   └── pipeline.py             # Orchestrates the 4-step skill scoring pipeline.
│   ├── github_services_v2/          # The V2 pipeline (15-Step logic).
│   │   ├── config.py                # ALL thresholds, weights, model configs (single source of truth).
│   │   ├── github_client.py         # Thin httpx wrapper for GitHub REST API.
│   │   ├── github_service.py        # 15-step orchestrator + RepositoryAuthenticity formula.
│   │   ├── models.py                # Pydantic models for all pipeline data structures.
│   │   ├── matching/
│   │   │   └── project_matcher.py   # 3-stage waterfall: Exact → Fuzzy → BGE-Large embedding.
│   │   ├── analysis/
│   │   │   ├── code_similarity.py   # CodeBERT clone detection + LRU/disk embedding cache.
│   │   │   ├── readme_similarity.py # BGE-Large README plagiarism detection.
│   │   │   └── behavioral_analysis.py # Commit pattern, burst risk, message quality scoring.
│   │   ├── scoring/
│   │   │   └── signal_fusion.py     # Dynamic weight redistribution + confidence + red flags.
│   │   └── llm/
│   │       └── llm_provider.py      # Gemini → Groq fallback for borderline similarity.
├── models/                          # Pydantic validation schemas blocking NoSQL anomalies.
└── utils/                           # Regex normalizations, logging scripts.
```

### 3.2 Frontend Application Space (`frontend/src/`)
```text
frontend/src/
├── App.js / theme.js             # Route bindings and global CSS variable declarations.
├── components/
│   ├── Dashboard.jsx             # Top level executive view.
│   ├── CandidatePipeline.jsx     # Kanban drag/drop.
│   ├── Settings.jsx              # Extensive Admin control using Lucide-React arrays.
│   ├── ui/                       # Radix UI primitives.
├── services/
│   └── jobService.js             # AXIOS interceptors & Snake → Camel Case transformers.
├── hooks/ / context/             # Custom state lifecycles / React Stores.
```

---

## 4. Implementation Deep-Dive: FastApi & AsyncIO Orchestration

### 4.1 Concurrent Scatter/Gather Logic
At the heart of the system operates `UnifiedVerificationService` inside `unified_verification.py`. Upon receiving an ID, the app runs the following code block:

```python
results = await asyncio.gather(
    self._verify_github(candidate_id, github_username, parsed_resume),
    self._verify_linkedin(candidate_id, linkedin_url),
    self._verify_web_search(candidate_id, profile_data),
    return_exceptions=True
)
```
- **Implementation Detail:** The flag `return_exceptions=True` is vital. Under default python behavior, if the web search throws a `urllib` exception, `asyncio.gather` cancels all peer coroutines immediately. With this flag, Exceptions are yielded as object strings inside `results`, permitting the backend to successfully post the GitHub score onto MongoDB even if the LinkedIn integration crashed entirely.

### 4.2 In-Memory Lock Caching
To prevent identical operations from overlapping on consecutive rapid requests:
```python
class VerificationCache:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def set(self, candidate_id: str, key: str, value: Any):
        if candidate_id not in self._cache:
            self._cache[candidate_id] = {}
        self._cache[candidate_id][key] = value
```
When endpoints initialize, they read the `VerificationCache` dict, ensuring multi-threaded requests targeting the same `CANDIDATE_ID` utilize the locked payload rather than spamming the GitHub API repeatedly. 

---

## 5. Algorithms Used & Their Implementation Areas

This section catalogues every distinct algorithm employed in the ResumeAI system, explaining the mathematical formula, the code that implements it, and exactly where in the pipeline it executes.

---

### 5.1 Algorithm: Levenshtein Distance (Fuzzy String Matching)

| Property | Value |
|---|---|
| **Algorithm** | Levenshtein Edit Distance via Token Set Ratio |
| **Library** | `thefuzz` (Python) |
| **Implementation File** | `github_services_v2/matching/project_matcher.py` |
| **Pipeline Step** | Step 5 — Resume→Repo Matching, Stage 2 |
| **Threshold** | `FUZZY_MATCH_THRESHOLD = 85` (from `config.py`) |

**Mathematical Definition:**
The Levenshtein distance `d(a, b)` is the minimum number of single-character edits (insertions, deletions, substitutions) required to transform string `a` into string `b`. The `token_set_ratio` variant tokenises both strings, computes the intersection and residuals, then returns:

```
ratio = 100 × max(
    fuzz_ratio(sorted_intersection, sorted_intersection + sorted_rest_of_a),
    fuzz_ratio(sorted_intersection, sorted_intersection + sorted_rest_of_b),
    fuzz_ratio(sorted_intersection + sorted_rest_of_a, sorted_intersection + sorted_rest_of_b)
)
```

This makes the match order-insensitive. `"Database Migration Tool V2"` and `"v2-tool-database-migration"` produce a high score because their token intersection is large.

**Code Implementation:**
```python
# project_matcher.py — Stage 2
from thefuzz import fuzz

score = fuzz.token_set_ratio(proj_name.lower(), repo_name.lower())
if score >= FUZZY_MATCH_THRESHOLD:  # 85
    return MatchedProject(..., matchStage="FUZZY", matchScore=score / 100)
```

---

### 5.2 Algorithm: CLS Pooling & L2-Normalized Cosine Similarity

| Property | Value |
|---|---|
| **Algorithm** | Transformer CLS-token pooling + L2-normalised dot product |
| **Models** | `BAAI/bge-large-en-v1.5` (1024-dim), `microsoft/codebert-base` (768-dim), `all-MiniLM-L6-v2` (384-dim) |
| **Implementation Files** | `project_matcher.py`, `code_similarity.py`, `readme_similarity.py`, `embedding_service.py` |
| **Pipeline Steps** | Step 5 (Stage 3), Step 7, Step 8, Skill Scoring |

**Mathematical Definition:**
Given two text inputs, each is fed through a Transformer encoder. The **CLS token** (first token `[0]`) of the `last_hidden_state` output is extracted as the sentence/code embedding:

```
emb = last_hidden_state[:, 0, :]   # Shape: (batch, dim)
```

**L2 Normalization** scales each vector to unit length:
```
emb_normalized = emb / ||emb||₂     where ||emb||₂ = √(Σ emb_i²)
```

**Cosine Similarity** between two L2-normalized vectors simplifies to a dot product:
```
cos(A, B) = A · B = Σ(A_i × B_i)   # range [−1, 1], clamped to [0, 1]
```

**Code Implementation (BGE-Large in `project_matcher.py`):**
```python
def _encode():
    with torch.no_grad():
        outputs = _bge_model(**encoded)
    # CLS pooling — extract first token
    embs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    # L2 normalise
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # guard against division-by-zero
    embs = embs / norms
    return embs

# Similarity is a simple matrix multiply on normalised vectors
sims = repo_embs @ proj_emb  # shape: (num_repos,)
max_idx = int(np.argmax(sims))
max_sim = float(sims[max_idx])
```

**Code Implementation (MiniLM in `embedding_service.py`):**
```python
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sqrt(sum(a ** 2 for a in vec1))
    norm2 = sqrt(sum(b ** 2 for b in vec2))
    similarity = dot_product / (norm1 * norm2)
    return max(0.0, min(1.0, similarity))  # clamp to [0, 1]
```

**Implementation Areas:**

| Use Case | Model | Dimensions | File |
|---|---|---|---|
| Resume project → GitHub repo matching | BGE-Large | 1024 | `project_matcher.py` |
| README plagiarism detection | BGE-Large | 1024 | `readme_similarity.py` |
| Source code clone detection | CodeBERT | 768 | `code_similarity.py` |
| Skill → resume section evidence | MiniLM-L6-v2 | 384 | `evidence_scorer.py` via `embedding_service.py` |
| Job description → resume matching | MiniLM-L6-v2 | 384 | `embedding_service.py` |

---

### 5.3 Algorithm: Jaccard Index (Structural Pre-Filter)

| Property | Value |
|---|---|
| **Algorithm** | Jaccard Similarity Coefficient |
| **Implementation File** | `github_services_v2/analysis/code_similarity.py` |
| **Pipeline Step** | Step 8 — Code Clone Detection (pre-filter) |
| **Threshold** | `STRUCTURE_JACCARD_THRESHOLD = 0.25` |

**Mathematical Definition:**
```
J(A, B) = |A ∩ B| / |A ∪ B|
```
Where `A` and `B` are sets of file paths within a repository. If two repos share fewer than 25% of their file paths, their structure is too different to be clones, so the expensive CodeBERT embedding step is skipped entirely.

**Code Implementation:**
```python
def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)

# Usage: skip if structural overlap is too low
if _jaccard(cand_paths, ref_paths) < STRUCTURE_JACCARD_THRESHOLD:
    continue  # skip this reference repo — too structurally different
```

---

### 5.4 Algorithm: Top-K% Mean Aggregation (Code Similarity Scoring)

| Property | Value |
|---|---|
| **Algorithm** | Per-chunk max similarity → top-30% mean |
| **Implementation File** | `github_services_v2/analysis/code_similarity.py` |
| **Pipeline Step** | Step 8 — Code Clone Detection |
| **Configuration** | `TOP_CHUNK_PERCENT = 0.30` |

**Mathematical Definition:**
For each candidate code chunk `c_i`, compute its maximum similarity against all reference chunks:
```
max_sim_i = max_j(cos(c_i, r_j))
```
Sort all `max_sim` values descending, take the top 30%, and compute their mean:
```
repo_similarity = mean(top_30%_of_max_sims)
```

This prevents a few incidentally-similar utility files (e.g. `utils.py`) from inflating the overall score, while still detecting bulk plagiarism when many chunks match. The `CodeOriginality` signal is then:
```
CodeOriginality = 1.0 − codeSimilarityMax
```

**Verdict thresholds (from `config.py`):**
| Similarity | Verdict |
|---|---|
| ≥ 0.90 | `COPIED` |
| 0.75–0.90 | `SUSPICIOUS` |
| < 0.75 | `ORIGINAL` |

---

### 5.5 Algorithm: Weighted Arithmetic Mean with Max-Bonus (Skill Scoring)

| Property | Value |
|---|---|
| **Algorithm** | Evidence-weighted linear combination + max-evidence bonus |
| **Implementation File** | `skill_matching/evidence_scorer.py` |
| **Pipeline Step** | Skill scoring per required JD skill |

**Mathematical Definition:**
For a single skill, compute cosine similarity against each resume section embedding:
```
weighted_sum = Σ(section_weight_i × similarity_i)
max_bonus    = max(similarity_i) × 0.25
raw          = weighted_sum + max_bonus          # theoretical max = 1.25
score        = clamp(raw / 1.25, 0, 1) × 10     # → 0–10
```

**Evidence weights (by evidential reliability):**

| Section | Weight | Rationale |
|---|---|---|
| `github` | 0.35 | Proved via actual code — hardest to fake |
| `experience` | 0.30 | Professional context, verified by employer |
| `projects` | 0.25 | Personal/academic context |
| `skills` | 0.10 | Self-declared — weakest, most gameable |

The **max-bonus** prevents a strong single signal (e.g. 0.90 GitHub similarity) from being diluted by zero values in weaker sections.

**Code Implementation:**
```python
# evidence_scorer.py
SECTION_WEIGHTS = {"github": 0.35, "experience": 0.30, "projects": 0.25, "skills": 0.10}
MAX_BONUS_WEIGHT = 0.25
_SCORE_MAX = sum(SECTION_WEIGHTS.values()) + MAX_BONUS_WEIGHT  # = 1.25

weighted_sum = sum(SECTION_WEIGHTS.get(sec, 0.0) * sim for sec, sim in section_sims.items())
max_sim = max(section_sims.values())
max_bonus = max_sim * MAX_BONUS_WEIGHT
raw = weighted_sum + max_bonus
score = round(min(raw / _SCORE_MAX, 1.0) * 10, 2)  # 0–10
found = score >= 3.0  # _FOUND_THRESHOLD
```

The aggregate **JD Match Score** is the arithmetic mean of all individual skill scores:
```python
jd_match_score = round(sum(s["score"] for s in skill_scores) / len(skill_scores), 2)
```

---

### 5.6 Algorithm: Dynamic Weight Redistribution (Signal Fusion)

| Property | Value |
|---|---|
| **Algorithm** | Proportional weight redistribution + weighted sum |
| **Implementation File** | `github_services_v2/scoring/signal_fusion.py` |
| **Pipeline Step** | Step 12 — Signal Fusion |

**Mathematical Definition:**
Given `N` available signals (some may be unavailable due to API failures), redistribute their base weights proportionally so they sum to 1.0:
```
adjusted_weight_i = base_weight_i / Σ(base_weight_j for j ∈ available)
score = Σ(adjusted_weight_i × signal_value_i)
score100 = round(score × 100, 2)
score40  = round(score100 × 0.4)     # 40-point scale for legacy compat
```

**Base Signal Weights (from `config.py`, must sum to 1.0):**

| Signal | Weight | Source File |
|---|---|---|
| ResumeConsistency | 0.20 | `project_matcher.py` |
| RepositoryAuthenticity | 0.20 | `github_service.py` |
| CodeOriginality | 0.20 | `code_similarity.py` |
| ReadmeOriginality | 0.15 | `readme_similarity.py` |
| BehavioralAuthenticity | 0.15 | `behavioral_analysis.py` |
| OSSContribution | 0.10 | `behavioral_analysis.py` |

**Code Implementation:**
```python
def _redistribute_weights(available: Dict[str, float]) -> Dict[str, float]:
    present_weights = {k: v for k, v in SIGNAL_WEIGHTS.items() if k in available}
    total_present = sum(present_weights.values())
    return {k: v / total_present for k, v in present_weights.items()}

# Final score computation
weights = _redistribute_weights(available)
score = sum(weights[k] * available[k] for k in available)
score = max(0.0, min(1.0, score))  # clamp
```

---

### 5.7 Algorithm: Linear Decay Function (Recency Scoring)

| Property | Value |
|---|---|
| **Algorithm** | Piecewise linear decay |
| **Implementation File** | `github_services_v2/github_service.py` |
| **Pipeline Step** | Step 4 — RepositoryAuthenticity sub-signal |
| **Configuration** | `RECENCY_FULL_DAYS=90`, `RECENCY_ZERO_DAYS=365` |

**Mathematical Definition:**
```
recency(days) = 
    1.0                                         if days ≤ 90
    (365 − days) / (365 − 90)                   if 90 < days < 365
    0.0                                         if days ≥ 365
```

**Code Implementation:**
```python
def _compute_recency(last_push: Optional[str]) -> float:
    days_ago = (datetime.now(timezone.utc) - dt).days
    if days_ago <= RECENCY_FULL_DAYS:       # 90
        return 1.0
    if days_ago >= RECENCY_ZERO_DAYS:       # 365
        return 0.0
    return (RECENCY_ZERO_DAYS - days_ago) / (RECENCY_ZERO_DAYS - RECENCY_FULL_DAYS)
```

The recency is then used in the **RepositoryAuthenticity** composite:
```python
# github_service.py — _compute_repo_stats()
RepositoryAuthenticity = 
    0.40 × (original / total)                             # original ratio
  + 0.25 × min(1.0, avg_commits / 50)                     # commit depth
  + 0.15 × recency                                        # recency
  + 0.20 × (non_trivial / total)                           # non-trivial ratio
```

---

### 5.8 Algorithm: Behavioral Authenticity Composite

| Property | Value |
|---|---|
| **Algorithm** | Four sub-score arithmetic mean |
| **Implementation File** | `github_services_v2/analysis/behavioral_analysis.py` |
| **Pipeline Step** | Step 9 — Behavioral Analysis |

**Four Sub-Scores:**

| Sub-Score | Formula | Config |
|---|---|---|
| Commit Consistency | `min(1.0, (unique_days / total_commits) × 2)` | — |
| Burst Risk | `commits_in_top_2_days / total_commits` | — |
| Message Quality | `0.5 × (unique_msgs / total) + 0.5 × min(1.0, avg_len / 40)` | `COMMIT_MESSAGE_LENGTH_CAP = 40` |
| File Diversity | Linear interpolation: `0.1→0.0`, `0.5→1.0` | `FILE_DIVERSITY_LOW=0.1, HIGH=0.5` |

**Composite Formula:**
```
BehavioralAuthenticity = (consistency + (1 − burstRisk) + messageQuality + fileDiversity) / 4
```

**Code Implementation:**
```python
def compute_behavioral_authenticity(consistency, burst_risk, message_quality, file_diversity):
    return clamp(
        (consistency + (1.0 - burst_risk) + message_quality + file_diversity) / 4.0
    )
```

**OSS Contribution** (also computed in this file):
```
external_contributions ≥ 3  →  1.0
external_contributions 1–2  →  0.5
external_contributions 0    →  0.0
```

---

### 5.9 Algorithm: Population Standard Deviation (Confidence Level)

| Property | Value |
|---|---|
| **Algorithm** | Population standard deviation with tier thresholds |
| **Implementation File** | `github_services_v2/scoring/signal_fusion.py` |
| **Pipeline Step** | Step 12 — Signal Fusion |

**Mathematical Definition:**
```
σ = √( (1/N) × Σ(v_i − μ)² )

Confidence = 
    "HIGH"     if σ < 0.15 and N ≥ 3
    "MEDIUM"   if σ ≤ 0.30 and N ≥ 3
    "LOW"      if σ > 0.30 or N < 3
```

If signals agree (low variance), confidence is HIGH. If signals contradict each other (e.g., code looks copied but behavior is genuine), confidence drops to LOW.

**Code Implementation:**
```python
def compute_confidence(values: List[float]) -> str:
    if len(values) < MIN_SIGNALS_FOR_CONFIDENCE:  # 3
        return "LOW"
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)
    if std_dev < CONFIDENCE_HIGH_MAX_STD:   # 0.15
        return "HIGH"
    if std_dev <= CONFIDENCE_MEDIUM_MAX_STD: # 0.30
        return "MEDIUM"
    return "LOW"
```

---

### 5.10 Algorithm: LRU Eviction with SHA-256 Keying (Embedding Cache)

| Property | Value |
|---|---|
| **Algorithm** | Least Recently Used cache with content-addressable SHA-256 keys |
| **Implementation File** | `github_services_v2/analysis/code_similarity.py` |
| **Pipeline Step** | Step 8 — Code Clone Detection (performance optimization) |
| **Configuration** | `EMBEDDING_LRU_MAX_SIZE=4096`, `EMBEDDING_CACHE_TTL_HOURS=72` |

**How it works:**
1. Each code chunk is hashed using SHA-256 to produce a deterministic key
2. **Memory lookup**: Python `OrderedDict` checked first (O(1) amortised). On hit, the entry is moved to the end (most recently used)
3. **Disk lookup**: If not in memory, check `EMBEDDING_CACHE_DIR` for `{hash}.npy` + TTL metadata
4. **Eviction**: When memory cache exceeds 4096 entries, the least recently used entry is evicted via `popitem(last=False)`

**Code Implementation:**
```python
class _EmbeddingCache:
    def __init__(self):
        self._mem: OrderedDict[str, np.ndarray] = OrderedDict()

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[np.ndarray]:
        key = self._key(text)
        if key in self._mem:
            self._mem.move_to_end(key)  # mark as recently used
            return self._mem[key]
        # fallback: load from disk if within TTL...

    def _put_mem(self, key: str, emb: np.ndarray) -> None:
        self._mem[key] = emb
        if len(self._mem) > EMBEDDING_LRU_MAX_SIZE:  # 4096
            self._mem.popitem(last=False)  # evict oldest
```

---

### 5.11 Algorithm: Hash-Map Alias Resolution (Skill Normalizer)

| Property | Value |
|---|---|
| **Algorithm** | O(1) hash-map lookup with lowercase normalization |
| **Implementation File** | `skill_matching/normalizer.py` |
| **Pipeline Step** | First step of every skill scoring iteration |
| **Coverage** | 100+ aliases across 15 technology categories |

**How it works:**
Every skill string is lowercased and looked up in a static `dict` of 100+ aliases. If found, return the canonical form; otherwise, return the lowercased input unchanged.

```python
SKILL_ALIASES = {
    "gcp": "google cloud platform",
    "aws": "amazon web services",
    "k8s": "kubernetes",
    "js": "javascript",
    "reactjs": "react",
    "py": "python",
    "golang": "go",
    "ci/cd": "continuous integration continuous deployment",
    # ... 90+ more
}

def normalize_skill(skill: str) -> str:
    normalised = skill.lower().strip()
    return SKILL_ALIASES.get(normalised, normalised)
```

---

### 5.12 Algorithm: Deterministic Rule Engine (Red Flag Generation)

| Property | Value |
|---|---|
| **Algorithm** | Threshold-based rule evaluation |
| **Implementation File** | `github_services_v2/scoring/signal_fusion.py` (evaluator) + `config.py` (rules) |
| **Pipeline Step** | Step 13 — Explainability |

**How it works:**
Six immutable rules are defined in `config.py`. Each rule specifies a signal key, a threshold, a direction (`above`/`below`), and a human-readable message. The evaluator iterates through all rules and fires any that match.

**Rules (from `config.py`):**

| Rule | Signal | Threshold | Direction | Message |
|---|---|---|---|---|
| `low_resume_consistency` | ResumeConsistency | 0.50 | below | "Less than half of claimed projects found on GitHub" |
| `code_similarity_high` | codeSimilarityMax | 0.75 | above | "High code similarity with external repositories detected" |
| `readme_similarity_high` | readmeSimilarityMax | 0.75 | above | "README content highly similar to external repositories" |
| `commit_burst` | burstRisk | 0.60 | above | "Commit burst pattern detected — majority of commits in 1–2 days" |
| `poor_commit_messages` | messageQuality | 0.40 | below | "Low quality commit messages (short / repetitive)" |
| `low_original_ratio` | originalRatio | 0.40 | below | "Majority of repositories are forks, not original work" |

```python
def generate_red_flags(raw_signals: Dict[str, float]) -> List[str]:
    flags = []
    for rule_name, rule in RED_FLAG_RULES.items():
        value = raw_signals.get(rule["signal"])
        if value is None:
            continue
        if rule["direction"] == "below" and value < rule["threshold"]:
            flags.append(rule["message"])
        elif rule["direction"] == "above" and value > rule["threshold"]:
            flags.append(rule["message"])
    return flags
```

---

### 5.13 Algorithm: LLM Chain-of-Fallback Arbitration

| Property | Value |
|---|---|
| **Algorithm** | Primary-fallback LLM chain with structured JSON output |
| **Implementation File** | `github_services_v2/llm/llm_provider.py` |
| **Pipeline Step** | Step 13b — LLM Escalation (conditional) |
| **Trigger Band** | `0.75 ≤ codeSimilarity < 0.90` |
| **Configuration** | `LLM_TEMPERATURE=0.0`, `LLM_TIMEOUT_SECONDS=15`, `LLM_MAX_INPUT_CHARS=4000` |

**How it works:**
When code similarity falls in the ambiguous band (SUSPICIOUS but not COPIED), the system escalates to an LLM for a semantic ruling. The primary LLM is **Gemini 2.0 Flash**; if Gemini fails (rate limit, timeout, API error), it falls back to **Groq (Llama 3.3-70B)**. If both fail, the pipeline continues without LLM input.

```python
async def _call_llm(user_message: str) -> Optional[Dict[str, Any]]:
    # ── Try Gemini ──
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        result = await _call_gemini(gemini_key, user_message)
        if result is not None:
            return result

    # ── Fallback: Groq ──
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        result = await _call_groq(groq_key, user_message)
        if result is not None:
            return result

    return None  # pipeline continues without LLM
```

Output is always structured JSON: `{"verdict": "ORIGINAL"|"SUSPICIOUS"|"COPIED", "reasoning": "...", "confidence": 0.0-1.0}`

---

## 6. Master Algorithm-to-File Cross-Reference Table

| # | Algorithm | File(s) | Pipeline Step | Input | Output |
|---|---|---|---|---|---|
| 1 | Levenshtein Distance (Token Set Ratio) | `project_matcher.py` | Step 5, Stage 2 | Two strings | Similarity 0–100 |
| 2 | CLS Pooling + L2 Cosine Similarity | `project_matcher.py`, `code_similarity.py`, `readme_similarity.py`, `embedding_service.py` | Steps 5/7/8, Skill Scoring | Text/code pair | Similarity 0.0–1.0 |
| 3 | Jaccard Index | `code_similarity.py` | Step 8 pre-filter | Two file-path sets | Overlap 0.0–1.0 |
| 4 | Top-K% Mean Aggregation | `code_similarity.py` | Step 8 | Chunk similarity array | Repo similarity 0.0–1.0 |
| 5 | Weighted Mean + Max-Bonus | `evidence_scorer.py` | Skill scoring | Per-section cosine sims | Score 0–10 |
| 6 | Dynamic Weight Redistribution | `signal_fusion.py` | Step 12 | Available signal values | Fused score 0–100 |
| 7 | Linear Decay | `github_service.py` | Step 4 | Days since last push | Recency 0.0–1.0 |
| 8 | Behavioral Composite (4-sub-score mean) | `behavioral_analysis.py` | Step 9 | Commit history | Auth score 0.0–1.0 |
| 9 | Population Std Dev | `signal_fusion.py` | Step 12 | Signal values array | Confidence HIGH/MEDIUM/LOW |
| 10 | LRU + SHA-256 Cache | `code_similarity.py` | Step 8 | Code chunk text | Cached embedding array |
| 11 | Hash-Map Alias Resolution | `normalizer.py` | Skill scoring | Raw skill string | Canonical string |
| 12 | Threshold Rule Engine | `signal_fusion.py` + `config.py` | Step 13 | Raw signal values | Red flag messages |
| 13 | LLM Chain-of-Fallback | `llm_provider.py` | Step 13b | Code context | {verdict, reasoning, confidence} |

---

## 7. Implementation Deep-Dive: The 15-Step GitHub Pipeline

The GitHub verification pipeline (`github_service.py`) executes 15 sequential steps:

| Step | Operation | Algorithm Used | File |
|---|---|---|---|
| 1 | Extract GitHub username | Regex URL parsing | `github_service.py` |
| 2 | Fail-fast if no username | Guard clause | `github_service.py` |
| 3 | Fetch all public repos | GitHub REST API | `github_client.py` |
| 4 | Compute RepositoryAuthenticity | Weighted composite (#7, #8) | `github_service.py` |
| 5 | Resume→Repo matching | Levenshtein (#1), Cosine (#2) | `project_matcher.py` |
| 6 | Select top-N repos for deep analysis | Priority sort | `github_service.py` |
| 7 | README similarity | Cosine similarity (#2) | `readme_similarity.py` |
| 8 | Code clone detection | Jaccard (#3), Cosine (#2), Top-K% (#4) | `code_similarity.py` |
| 9 | Behavioral analysis | Composite (#8) | `behavioral_analysis.py` |
| 10 | OSS contribution detection | Step function | `behavioral_analysis.py` |
| 11 | Normalise all signals to 0–1 | Clamping | `github_service.py` |
| 12 | Signal fusion | Dynamic redistribution (#6), Std dev (#9) | `signal_fusion.py` |
| 13 | Explainability / red flags | Rule engine (#12) | `signal_fusion.py` |
| 13b | LLM escalation (conditional) | Chain-of-fallback (#13) | `llm_provider.py` |
| 14 | Build MongoDB document | Pydantic serialization | `github_service.py` |
| 15 | Return result | — | `github_service.py` |

---

## 8. Implementation Deep-Dive: Unified Skill Scoring Pipeline

The skill matching pipeline (`skill_matching/pipeline.py`) executes 4 steps:

| Step | Operation | Algorithm | File |
|---|---|---|---|
| 1 | Extract text corpora from resume sections + GitHub data | String extraction | `section_embedder.py` |
| 2 | Embed all sections concurrently (one vector per section) | MiniLM-L6-v2, CLS pooling (#2) | `section_embedder.py` |
| 3 | For each required skill: normalise → build phrase → embed → cosine vs sections → weighted score | Alias resolution (#11), Cosine (#2), Weighted mean (#5) | `normalizer.py`, `evidence_scorer.py` |
| 4 | Aggregate: `jd_match_score = mean(all skill scores)` | Arithmetic mean | `pipeline.py` |

**Skill Phrase Enrichment (from `evidence_scorer.py`):**
Instead of embedding the bare skill token "kubernetes", the system embeds a natural-language phrase:
```python
def _skill_phrase(canonical: str) -> str:
    return f"candidate with hands-on experience using {canonical} in production"
```
This dramatically improves cosine similarity with phrases like "deployed clusters on GKE" that don't mention "kubernetes" literally.

---

## 9. Implementation Deep-Dive: System Regression Testing

ResumeAI validates code through `tests/test_full_system_regression.py`. This script mocks total API traversal to ensure no internal routing logic breaks when components iterate.

### 9.1 Path Execution & AsyncMocks
The test mocks physical endpoint routes mimicking a "Job creation → Resume Upload → Evaluation" flow. 

```python
with patch(
    "app.routes.job_routes.db", mock_db
), patch(
    "app.services.embedding_service.generate_embedding",
    return_value=[0.1] * 384,
):
    resp = await client.post("/api/jobs", json=sample_job_data)
    assert resp.status_code == 200, f"Job creation failed: {resp.text}"
```

### 9.2 Bypassing Long Running Web-Workers
Instead of executing real Gemini evaluations which would take 45+ seconds and breach rate limit constraints during CI pipelines, the core verification methods are entirely overridden utilizing `side_effect` testing paradigms:

```python
@patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
@patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
@patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
async def test_all_three_sources_concurrent(self, mock_web, mock_li, mock_gh, mock_db):
    gh_result = MagicMock()
    gh_result.success = True
    gh_result.score100 = 80.0
    mock_gh.return_value = gh_result
    
    # Asserts that if GitHub fails, LinkedIn and WebSearch still proceed unharmed.
```

---

## 10. Implementation Deep-Dive: The Frontend Service Tier & UX State

Because the API models variables heavily in standard python configuration (`snake_case`), directly placing them onto the React V-DOM causes structural messiness and typing errors (`myVar.total_candidates` vs `myVar.totalCandidates`).

### 10.1 Interceptor and Transformation Adapters
Located in `src/services/jobService.js`, the React code defines explicit boundary layers mapping fields out:
```javascript
const transformJobFromAPI = (job) => ({
    id: job.id,
    title: job.job_title,
    description: job.job_description,
    status: job.is_active ? 'Active' : 'Closed',
    totalCandidates: job.total_candidates || 0,
});
```

### 10.2 Component Modularity & UI State Machines (`Settings.jsx`)
In modern components, logic loops render arrays dynamically utilizing custom atomic blocks `<Panel>` and `<PanelHeader>` ensuring consistency.
```javascript
const TABS = [
  { id: 'users',         label: 'Users',         Icon: Users },
  { id: 'billing',       label: 'Billing',        Icon: CreditCard },
  { id: 'integrations',  label: 'Integrations',   Icon: Plug },
  { id: 'api',           label: 'API Keys',        Icon: Key },
];

{TABS.map(({ id, label }) => (
  <button
    key={id}
    onClick={() => setActiveTab(id)}
    className={`px-5 py-2.5 text-sm font-semibold border-b-2`}
  >
    {label}
  </button>
))}
```
This forces all UI updates to cascade from standard color configurations (`COLOR.primary`) bridging CSS Root parameters dynamically.

---

## 11. Data Persistence & Pydantic Schema Guards

Data structures are fully modeled natively via Pydantic `BaseModel` classes inside `backend/app/models/verification_data_model.py`. MongoDB natively lacks schema enforcement; therefore, Pydantic intercepts faulty data bounds natively *before* they reach the hard drive. 

### 11.1 Complex Nesting Guards
```python
class GitHubDataModel(BaseModel):
    username: Optional[str] = None
    success: bool = False
    score: float = 0
    # --- V2 fields ---
    score100: Optional[float] = None
    confidenceLevel: Optional[str] = None  # HIGH / MEDIUM / LOW
    
    breakdown: Optional[GitHubScoreBreakdown] = None
    repositoryStats: Optional[GitHubRepositoryStats] = None
    commitStats: Optional[GitHubCommitStats] = None
    
class VerificationDataModel(BaseModel):
    """Main verification data document for MongoDB"""
    candidateId: str
    githubData: Optional[GitHubDataModel] = None
    
    def to_mongo_dict(self) -> dict:
        return self.model_dump(exclude_none=True) # Explicitly drops floating nulls.
```
If the github service tries committing `{ "score100": "eighty-two" }`, Pydantic intercepts the HTTP transaction explicitly returning a FastApi `422 Unprocessable Entity` preventing MongoDB schema corruption natively.

---

## 12. Defensive Engineering & Lock Mechanics

Given the severe footprint of ML model definitions, Python standard architecture will crash if parallel endpoints request access to `AutoModel.from_pretrained()`.

### 12.1 Asyncio Double-Check Locks
In `project_matcher.py` & `code_similarity.py`, the global lock protects instantiation:

```python
_bge_lock = asyncio.Lock()

async def _ensure_bge_model():
    # Primary bypass
    if _bge_model is not None:
        return

    lock = _get_bge_lock()
    async with lock:
        # Double check post-lock
        if _bge_model is not None: 
            return
            
        def _load():
            torch.set_num_threads(NUM_THREADS)
            _bge_model = AutoModel.from_pretrained(BGE_MODEL)
            # ...
        await asyncio.to_thread(_load)
```
Pushing the torch generation onto `asyncio.to_thread(_load)` ensures that threading does not break the standard Python Global Interpreter Lock (GIL) maintaining optimal FastApi throughput across standard routing structures.

---
> **End of Algorithms & Implementation Report Version 5.**
> This document catalogues every algorithm, its mathematical formula, the exact file implementing it, and the pipeline step where it executes — providing a complete implementation-level blueprint of the ResumeAI evaluation system.
