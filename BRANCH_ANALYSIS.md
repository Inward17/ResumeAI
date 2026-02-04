# Branch Analysis Feature

## 🌿 Multi-Branch Commit Analysis

By default, the system now analyzes commits from **all branches**, not just the main/master branch.

---

## Why This Matters

### ❌ Old Behavior (Main Branch Only)
```
User has:
- main branch: 5 commits
- feature-branch-1: 20 commits
- feature-branch-2: 15 commits

Old system counted: 5 commits ❌
```

### ✅ New Behavior (All Branches)
```
User has:
- main branch: 5 commits
- feature-branch-1: 20 commits
- feature-branch-2: 15 commits

New system counts: 40 commits ✅ (deduplicated)
```

This gives a much more accurate picture of actual development activity!

---

## Configuration

Edit `github/utils/constants.py`:

```python
# ============================================
# API CONFIGURATION
# ============================================

# Analyze all branches (recommended for accuracy)
ANALYZE_ALL_BRANCHES = True   # ✅ More accurate, slightly slower

# OR analyze main branch only (faster but less accurate)
ANALYZE_ALL_BRANCHES = False  # ⚡ Faster, may undercount

# Maximum branches to check (to prevent rate limit issues)
MAX_BRANCHES_TO_ANALYZE = 10  # Default: 10 branches
```

---

## Performance Impact

### With `ANALYZE_ALL_BRANCHES = True`:

**Pros:**
- ✅ More accurate commit counts
- ✅ Captures feature branch work
- ✅ Better reflects actual development activity
- ✅ Handles multi-branch workflows correctly

**Cons:**
- ⏱️ Slightly slower (1-2 extra API calls per repo)
- 📊 Uses more API rate limit

**API Calls:**
- Main branch only: 1 call per repo
- All branches: 1 + N calls per repo (N = number of branches, max 10)

### With `ANALYZE_ALL_BRANCHES = False`:

**Pros:**
- ⚡ Faster analysis
- 📊 Lower API usage

**Cons:**
- ❌ May undercount commits
- ❌ Misses feature branch work
- ❌ Less accurate for developers who work on multiple branches

---

## How It Works

### Step 1: Fetch All Branches
```python
GET /repos/{owner}/{repo}/branches
# Returns: ['main', 'develop', 'feature-1', 'feature-2', ...]
```

### Step 2: Fetch Commits from Each Branch
```python
# For each branch:
GET /repos/{owner}/{repo}/commits?author={username}&sha={branch_name}
```

### Step 3: Deduplicate Commits
```python
# Commits are deduplicated by SHA hash
# Same commit in multiple branches = counted once
```

---

## Examples

### Developer Working on Multiple Branches

```python
# User: alice
# Repo: awesome-project

Branches:
- main: alice has 10 commits
- develop: alice has 25 commits (includes main commits)
- feature-x: alice has 5 new commits
- feature-y: alice has 8 new commits

With ANALYZE_ALL_BRANCHES = True:
Total unique commits: 10 + 15 + 5 + 8 = 38 commits ✅

With ANALYZE_ALL_BRANCHES = False:
Total commits: 10 commits (main only) ❌ Undercounted by 28!
```

### Repository with Many Branches

```python
# Repo with 50 branches
# System analyzes first 10 branches only (configurable)

MAX_BRANCHES_TO_ANALYZE = 10

# This prevents:
# - Excessive API calls
# - Rate limit issues
# - Slow analysis
```

---

## Rate Limit Considerations

### Without Multi-Branch Analysis:
```
100 repos × 1 API call = 100 calls
```

### With Multi-Branch Analysis:
```
100 repos × ~5 API calls avg = 500 calls
(assuming average of 5 branches per repo)
```

### With GitHub Token:
- **Rate Limit:** 5,000 calls/hour
- **Can analyze:** ~1,000 repos/hour (with multi-branch)
- **Can analyze:** ~5,000 repos/hour (main branch only)

**Recommendation:** Keep `ANALYZE_ALL_BRANCHES = True` unless you're analyzing thousands of repos.

---

## Best Practices

### ✅ Use Multi-Branch When:
- Analyzing individual developers
- Accuracy is important
- You have API rate limit headroom
- Developers use feature branches
- Small to medium batch sizes (< 100 profiles)

### ⚡ Use Main Branch Only When:
- Batch processing thousands of profiles
- Speed is critical
- Rate limits are a concern
- Quick screening phase
- Most developers work on main branch

---

## Customization

### Change Maximum Branches Analyzed

```python
# In constants.py
MAX_BRANCHES_TO_ANALYZE = 20  # Analyze up to 20 branches

# More branches = more accurate but slower
# Fewer branches = faster but may miss commits
```

### Disable Multi-Branch Analysis

```python
# In constants.py
ANALYZE_ALL_BRANCHES = False

# System will only count commits on default branch
```

### Dynamic Configuration

```python
# You can override per analysis
from github.routes.github_routes import GitHubAnalysisService

service = GitHubAnalysisService()

# Option 1: Modify the constant temporarily
import github.utils.constants as constants
constants.ANALYZE_ALL_BRANCHES = False

result = service.analyze_github_profile("https://github.com/user")
```

---

## Migration from Old Version

If you were using the old version:

### Old Behavior
```python
# Only counted main branch commits
# No configuration needed
```

### New Behavior (Default)
```python
# Counts all branch commits (up to 10 branches)
# Configuration available in constants.py
ANALYZE_ALL_BRANCHES = True  # Default
```

### If You Want Old Behavior
```python
# Set in constants.py
ANALYZE_ALL_BRANCHES = False
```

---

## Technical Details

### Deduplication Algorithm

```python
all_commits = {}  # Dictionary for O(1) lookup

for branch in branches[:MAX_BRANCHES_TO_ANALYZE]:
    commits = fetch_commits(branch)
    for commit in commits:
        sha = commit["sha"]
        if sha not in all_commits:
            all_commits[sha] = commit  # Store unique commits only

return list(all_commits.values())
```

### Fallback Behavior

If branch fetching fails:
```python
try:
    branches = get_branches()
    if not branches:
        # Fallback to main branch only
        return get_commits_from_main_branch()
except:
    # Fallback to main branch only
    return get_commits_from_main_branch()
```

---

## API Endpoints Used

1. **Get Branches:**
   ```
   GET /repos/{owner}/{repo}/branches
   ```

2. **Get Commits (per branch):**
   ```
   GET /repos/{owner}/{repo}/commits?author={username}&sha={branch}
   ```

---

## Testing

Test with a multi-branch repository:

```python
from github.routes.github_routes import GitHubAnalysisService

service = GitHubAnalysisService()

# Analyze a repo you know has multiple branches
result = service.analyze_github_profile("https://github.com/username")

print(f"Total commits: {result['commitStats']['total']}")
```

Compare with GitHub's web UI to verify accuracy.

---

## Summary

| Feature | Main Branch Only | All Branches |
|---------|-----------------|--------------|
| **Accuracy** | Lower ❌ | Higher ✅ |
| **Speed** | Faster ⚡ | Slightly slower |
| **API Calls** | Fewer 📊 | More 📊 |
| **Use Case** | Batch processing | Individual analysis |
| **Default** | No | **Yes** ✅ |

**Recommendation:** Keep the default (`ANALYZE_ALL_BRANCHES = True`) for most accurate results.

---

## Questions?

- Check `github/services/github_client.py` - see `get_repo_commits()` method
- Check `github/utils/constants.py` - see `ANALYZE_ALL_BRANCHES` setting
- Test with your own profile to see the difference!
