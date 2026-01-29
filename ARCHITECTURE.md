# GitHub Ownership Score - Architecture Diagram

## System Architecture (ASCII)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          API ENTRY POINT                                  │
│                                                                            │
│  POST /analyze  ────┬────►  GitHubAnalysisService                        │
│  GET /rate-limit    │              (Orchestrator)                         │
│  GET /health        │                                                      │
└─────────────────────┼──────────────────────────────────────────────────┬─┘
                      │                                                    │
                      ▼                                                    │
         ┌────────────────────────┐                                       │
         │   github_routes.py     │                                       │
         │   - Pipeline control   │                                       │
         │   - Error handling     │                                       │
         │   - Result assembly    │                                       │
         └──────────┬─────────────┘                                       │
                    │                                                      │
    ┌───────────────┼───────────────┬──────────────────┐                 │
    ▼               ▼               ▼                  ▼                  │
┌─────────┐   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│ GitHub  │   │    Repo     │  │   README     │  │    Score     │      │
│ Client  │──►│  Analyzer   │─►│  Analyzer    │─►│   Engine     │──────┘
└─────────┘   └─────────────┘  └──────────────┘  └──────────────┘      │
     │              │                 │                    │              │
     │              │                 │                    │              ▼
     │              │                 │                    │      ┌────────────┐
     │              │                 │                    └─────►│  GitHub    │
     │              │                 │                           │  Writer    │
     │              │                 │                           └────────────┘
     │              │                 │                                  │
     ▼              ▼                 ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           UTILITY MODULES                                │
├─────────────────┬─────────────────────┬──────────────────────────────┤
│  constants.py   │   text_utils.py     │      date_utils.py            │
│                 │                     │                                │
│  - Weights      │   - Keywords        │   - Commit spread             │
│  - Thresholds   │   - Extraction      │   - Dump detection            │
│  - OSS List     │   - Matching        │   - Date parsing              │
└─────────────────┴─────────────────────┴──────────────────────────────┘
```

## Data Flow

```
INPUT: github_username
  │
  ├──► 1. GitHubClient.get_user_repos()
  │         └─► Fetch all repositories
  │
  ├──► 2. RepoAnalyzer.analyze_repos()
  │         ├─► For each repo:
  │         │    ├─► Check fork status
  │         │    ├─► Fetch commits by user
  │         │    ├─► Analyze commit spread
  │         │    ├─► Detect OSS contributions
  │         │    ├─► Get languages
  │         │    └─► Check trivial patterns
  │         └─► Output: enriched_repositories[]
  │
  ├──► 3. ReadmeAnalyzer.analyze_readmes()
  │         ├─► For each repo:
  │         │    ├─► Fetch README
  │         │    ├─► Extract keywords
  │         │    ├─► Compare with repo languages
  │         │    └─► Flag mismatches
  │         └─► Output: enhanced_repositories[]
  │
  ├──► 4. ScoreEngine.compute_score()
  │         ├─► Calculate component scores:
  │         │    ├─► Original ratio (30%)
  │         │    ├─► Commit depth (25%)
  │         │    ├─► README presence (15%)
  │         │    ├─► Language match (15%)
  │         │    └─► OSS bonus (10%)
  │         ├─► Identify red flags
  │         ├─► Apply penalties (-25 max)
  │         └─► Output: score (0-100) + flags
  │
  └──► 5. GitHubWriter.write_github_data()
        └─► Store in verification_data.githubData
             ├─► Profile stats
             ├─► Score & components
             ├─► Red flags
             └─► Enhanced repositories[]

OUTPUT: 
  {
    score: 0-100,
    redFlags: [],
    components: {},
    repositoryStats: {},
    commitStats: {},
    readmeStats: {}
  }
```

## Module Dependencies

```
github_routes.py
    │
    ├─── github_client.py
    │
    ├─── repo_analyzer.py
    │       └─── github_client.py
    │       └─── text_utils.py (trivial names)
    │       └─── date_utils.py (commit spread)
    │       └─── constants.py (thresholds, OSS list)
    │
    ├─── readme_analyzer.py
    │       └─── github_client.py
    │       └─── text_utils.py (keyword extraction)
    │       └─── constants.py (language keywords)
    │
    ├─── score_engine.py
    │       └─── constants.py (weights, red flags)
    │
    └─── github_writer.py
            └─── (no dependencies)
```

## Scoring Algorithm (Detailed)

```
┌─────────────────────────────────────────────────┐
│           COMPONENT SCORING                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  1. Original Ratio (30 pts)                     │
│     score = original_ratio × 30                 │
│                                                  │
│  2. Commit Depth (25 pts)                       │
│     ├─ 50+ commits/repo:  25 pts (100%)        │
│     ├─ 20+ commits/repo:  23 pts (92%)         │
│     ├─ 10+ commits/repo:  18 pts (72%)         │
│     ├─ 5+  commits/repo:  10 pts (40%)         │
│     └─ <5  commits/repo:   5 pts (20%)         │
│                                                  │
│  3. README Presence (15 pts)                    │
│     score = readme_ratio × 15                   │
│                                                  │
│  4. Language Match (15 pts)                     │
│     ├─ No mismatch:       15 pts (100%)        │
│     └─ Global mismatch:    4.5 pts (30%)       │
│                                                  │
│  5. OSS Bonus (10 pts)                          │
│     ├─ 3+ contributions:  10 pts (100%)        │
│     ├─ 1-2 contributions:  5 pts (50%)         │
│     └─ 0 contributions:    0 pts (0%)          │
│                                                  │
├─────────────────────────────────────────────────┤
│  RAW SCORE = sum(components) = 0-95             │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│           RED FLAG PENALTIES                     │
├─────────────────────────────────────────────────┤
│                                                  │
│  Each flag = -5 points (max -25)                │
│                                                  │
│  1. Mostly forked (< 40% original)     -5       │
│  2. Low commit depth (< 5 avg)         -5       │
│  3. Commit dump pattern (70%+ in 2d)   -5       │
│  4. Missing README (< 50%)             -5       │
│  5. Tech stack mismatch                -5       │
│  6. Trivial repos (> 40%)              -5       │
│                                                  │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  FINAL SCORE = clamp(RAW - PENALTY, 0, 100)     │
└─────────────────────────────────────────────────┘
```

## Red Flag Detection Logic

```
FOR EACH PROFILE:
  
  IF original_ratio < 0.4:
    ADD "Mostly forked repositories"
  
  IF average_commits_per_repo < 5:
    ADD "Low commit depth"
  
  IF 70%+ commits in 1-2 days:
    ADD "Commit dump pattern"
  
  IF readme_coverage < 50%:
    ADD "README missing"
  
  IF language_mismatch in 2+ repos:
    ADD "Tech stack mismatch"
  
  IF trivial_repos > 40% of total:
    ADD "Trivial repositories"
  
  RETURN red_flags[]
```

## OSS Contribution Detection

```
FOR EACH FORKED REPO:
  
  parent_org = extract_org_from_full_name(repo)
  
  IF parent_org in OSS_ALLOWLIST:
    IF user_commits >= 10:
      MARK as OSS_CONTRIBUTION
      TREAT as ORIGINAL (for scoring)
    ELSE:
      KEEP as FORKED
  ELSE:
    IF user_commits >= 10:
      TREAT as ORIGINAL
    ELSE:
      KEEP as FORKED
```

## Language Matching Logic

```
FOR EACH REPO with README:
  
  readme_keywords = extract_keywords(readme_text)
  repo_languages = get_top_3_languages(repo)
  
  IF readme_keywords ∩ repo_languages = ∅:
    # No overlap
    MARK as MISMATCH
  ELSE:
    MARK as MATCH

IF mismatch_count >= 2:
  SET global_mismatch = TRUE
  ADD to red_flags
```

## Integration Points

```
┌─────────────────────────────────────────┐
│     YOUR APPLICATION                     │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│  Integration Options:                    │
│                                          │
│  1. Direct Call:                         │
│     service.analyze_github_profile()     │
│                                          │
│  2. REST API:                            │
│     POST /analyze                        │
│                                          │
│  3. Queue/Worker:                        │
│     celery.task(analyze_github)          │
│                                          │
│  4. Webhook:                             │
│     @webhook("/github-verified")         │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│   GitHubAnalysisService                  │
│   (handles everything internally)        │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│   verification_data.githubData           │
│   {                                      │
│     username,                            │
│     score,                               │
│     redFlags[],                          │
│     repositoryStats{},                   │
│     repositories[]                       │
│   }                                      │
└─────────────────────────────────────────┘
```

## File Structure (Tree)

```
github-ownership-score/
│
├── github/                    # Main package
│   ├── __init__.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── github_routes.py  # API orchestration (130 LOC)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── github_client.py   # GitHub API (140 LOC)
│   │   ├── repo_analyzer.py   # Repo analysis (145 LOC)
│   │   ├── readme_analyzer.py # README analysis (135 LOC)
│   │   └── score_engine.py    # Scoring logic (148 LOC)
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── constants.py       # Config (95 LOC)
│   │   ├── text_utils.py      # Text helpers (75 LOC)
│   │   └── date_utils.py      # Date helpers (90 LOC)
│   │
│   └── persistence/
│       ├── __init__.py
│       └── github_writer.py   # DB persistence (125 LOC)
│
├── example_usage.py           # Usage examples (180 LOC)
├── test_system.py             # Test suite (200 LOC)
├── fastapi_integration.py     # REST API (320 LOC)
│
├── requirements.txt           # Dependencies
├── .env.template              # Config template
│
├── README.md                  # Main documentation
├── DEPLOYMENT.md              # Deployment guide
├── PROJECT_SUMMARY.md         # Project summary
└── ARCHITECTURE.md            # This file
```

All files in the system are modular, maintainable, and production-ready! ✅
