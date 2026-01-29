# GitHub Ownership Score System

A clean, modular, industry-standard implementation for analyzing GitHub profiles and computing ownership scores based on EASY-FIRST signals.

## 🎯 Overview

This system analyzes GitHub profiles to compute an ownership score (0-100) that reflects genuine development activity and code ownership, helping identify authentic developer profiles from artificially inflated ones.

### Key Features

- ✅ **Modular Architecture** - Clean separation of concerns, easy to test
- ✅ **EASY Signals** - Rule-based, explainable, no ML required
- ✅ **Production Ready** - Rate-limit friendly, error handling, logging
- ✅ **Extendable** - Ready for future enhancements (clone detection, etc.)
- ✅ **Audit-Ready** - Clear red flags with recruiter-friendly explanations

## 📊 Scoring Components

| Signal | Weight | Description |
|--------|--------|-------------|
| Original Repo Ratio | 30% | Percentage of original vs forked repositories |
| Commit Depth | 25% | Number and distribution of commits |
| README Presence | 15% | Presence and quality of README files |
| README-Language Match | 15% | Consistency between README and code |
| OSS Contribution Bonus | 10% | Meaningful contributions to major OSS projects |
| Red Flag Penalty | -25 max | Deductions for suspicious patterns |

## 🏗️ Architecture

```
github/
├── routes/
│   └── github_routes.py        # API entry point & orchestration
│
├── services/
│   ├── github_client.py        # Raw GitHub API calls
│   ├── repo_analyzer.py        # Repository-level analysis
│   ├── readme_analyzer.py      # README parsing & keyword extraction
│   └── score_engine.py         # Scoring logic & red flag detection
│
├── utils/
│   ├── constants.py            # Thresholds, weights, allowlists
│   ├── text_utils.py           # Keyword extraction helpers
│   └── date_utils.py           # Commit pattern analysis
│
└── persistence/
    └── github_writer.py        # Database persistence layer
```

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install requests
```

### Basic Usage

```python
from github.routes.github_routes import GitHubAnalysisService

# Initialize service (GitHub token optional but recommended)
service = GitHubAnalysisService(github_token="your_token_here")

# Analyze a profile
result = service.analyze_github_profile(username="octocat")

if result["success"]:
    print(f"Score: {result['score']}/100")
    print(f"Red Flags: {result['redFlags']}")
    print(f"Components: {result['components']}")
```

### With Persistence

```python
# Initialize with database client
service = GitHubAnalysisService(
    github_token="your_token_here",
    db_client=your_db_client
)

# Analyze and persist to verification_data.githubData
result = service.analyze_github_profile(
    username="octocat",
    user_id="user_12345"
)
```

## 🔍 Analysis Signals

### 1. Original vs Forked Repos (30 points)

- **Original repos** get full credit
- **Forked repos** are treated as original if:
  - User has 10+ commits in the fork, OR
  - Fork is from a recognized OSS organization (Apache, Kubernetes, etc.)

### 2. Commit Depth (25 points)

- Analyzes total commits and distribution
- Flags profiles with:
  - < 5 commits per repo on average
  - 70%+ commits concentrated in 1-2 days (dump pattern)

### 3. README Presence (15 points)

- Checks for README existence and quality
- Minimum length threshold: 100 characters
- Penalizes profiles with < 50% README coverage

### 4. README-Language Match (15 points)

- Extracts technology keywords from README
- Compares with actual repository languages
- Flags mismatches across multiple repos

### 5. OSS Contributions (10 points bonus)

- Bonus for contributions to major OSS projects
- Requires meaningful commits (10+ commits)
- Recognizes 40+ major OSS organizations

## 🚩 Red Flags

The system identifies six types of red flags:

1. **Mostly Forked** - < 40% original repositories
2. **Low Commit Depth** - < 5 commits per repo average
3. **Commit Dump Pattern** - 70%+ commits in 1-2 days
4. **Missing README** - < 50% repos have README
5. **Tech Stack Mismatch** - README doesn't match code languages
6. **Trivial Repos** - > 40% repos are tutorials/demos

Each flag incurs a 5-point penalty (max 25 points total).

## 📦 Output Structure

```json
{
  "success": true,
  "username": "octocat",
  "score": 78.5,
  "redFlags": ["Low commit depth"],
  "components": {
    "original_ratio": 27.0,
    "commit_depth": 18.5,
    "readme_presence": 13.5,
    "language_match": 15.0,
    "oss_bonus": 10.0,
    "penalty": 5.0
  },
  "repositoryStats": {
    "total": 25,
    "original": 23,
    "forked": 2,
    "original_ratio": 0.92
  },
  "commitStats": {
    "total": 487,
    "average_per_repo": 19.5,
    "lastCommitDate": "2024-01-15T10:30:00"
  },
  "readmeStats": {
    "repos_with_readme": 21,
    "readme_presence_ratio": 0.84
  }
}
```

## 🔧 Configuration

Edit `github/utils/constants.py` to customize:

- **Scoring weights** - Adjust component importance
- **Thresholds** - Min commits, README length, etc.
- **OSS allowlist** - Add/remove recognized organizations
- **Trivial patterns** - Keyword patterns for low-effort repos
- **Language keywords** - Technology detection keywords

## 🧪 Testing

```python
# Test individual components
from github.services.github_client import GitHubClient
from github.services.repo_analyzer import RepoAnalyzer

client = GitHubClient(token="your_token")
analyzer = RepoAnalyzer(client)

repos = client.get_user_repos("octocat")
analysis = analyzer.analyze_repos("octocat", repos)
print(analysis)
```

## 📊 GitHub API Usage

The system makes efficient use of the GitHub API:

- **Endpoints used**: `/users/{user}/repos`, `/repos/{owner}/{repo}/languages`, `/repos/{owner}/{repo}/readme`, `/repos/{owner}/{repo}/commits`
- **Rate limits**: 5,000/hour with token, 60/hour without
- **Optimization**: Batch fetching, minimal redundant calls

### Rate Limit Management

```python
service = GitHubAnalysisService(github_token="your_token")
rate_limit = service.get_rate_limit_status()
print(f"Remaining: {rate_limit['resources']['core']['remaining']}")
```

## 🔐 Security & Privacy

- ✅ No code cloning or storage
- ✅ No sensitive data collection
- ✅ Only public repository data
- ✅ Token authentication required for production
- ✅ No embeddings or ML models

## 🛣️ Roadmap

### Phase 1 (Current) ✅
- Original vs forked analysis
- Commit depth analysis
- README presence & quality
- README-language matching
- OSS contribution detection
- Red flag system

### Phase 2 (Future)
- Clone detection using embeddings
- Code quality signals
- Pull request analysis
- Contribution graph analysis
- Team collaboration signals

## 📝 Example Use Cases

### 1. Recruitment Screening
```python
# Screen candidates before technical interview
result = service.analyze_github_profile(candidate_username)
if result["score"] < 50:
    print("Consider additional technical assessment")
```

### 2. Batch Analysis
```python
# Analyze multiple profiles
candidates = ["user1", "user2", "user3"]
for username in candidates:
    result = service.analyze_github_profile(username)
    print(f"{username}: {result['score']}/100")
```

### 3. Integration with Verification System
```python
# Add to existing verification pipeline
def verify_developer(user_id, github_username):
    result = service.analyze_github_profile(
        username=github_username,
        user_id=user_id
    )
    
    # Store in verification_data.githubData
    return {
        "verified": result["score"] >= 60,
        "score": result["score"],
        "flags": result["redFlags"]
    }
```

## 🤝 Contributing

This is a production-ready implementation. For extensions:

1. Keep modules under 150 LOC
2. Maintain single responsibility principle
3. Add tests for new features
4. Update documentation

## 📄 License

Internal use only. Not for public distribution.

## 🙋 Support

For questions or issues:
- Check example_usage.py for common patterns
- Review constants.py for configuration options
- Ensure GitHub token is properly configured
