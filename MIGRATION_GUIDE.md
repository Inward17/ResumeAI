# Migration Guide - Updated Usage

## 🔄 What Changed

### 1. ✅ GitHub Token from Environment Variable (Automatic)

**OLD WAY** (manual token passing):
```python
github_token = os.getenv("GITHUB_TOKEN")
service = GitHubAnalysisService(github_token=github_token)
```

**NEW WAY** (automatic from environment):
```python
# Just set the environment variable and initialize
# export GITHUB_TOKEN="your_token"
service = GitHubAnalysisService()  # Token automatically loaded
```

### 2. ✅ Accept GitHub URL or Username

**OLD WAY** (username only):
```python
result = service.analyze_github_profile(username="octocat")
```

**NEW WAY** (URL or username):
```python
# Both work now!
result = service.analyze_github_profile("https://github.com/octocat")
result = service.analyze_github_profile("octocat")
```

---

## 📝 Updated Code Examples

### Basic Usage

```python
from github.routes.github_routes import GitHubAnalysisService

# 1. Set environment variable (in terminal or .env file)
# export GITHUB_TOKEN="ghp_your_token_here"

# 2. Initialize service (no token parameter needed!)
service = GitHubAnalysisService()

# 3. Analyze using URL or username
result = service.analyze_github_profile("https://github.com/octocat")
# OR
result = service.analyze_github_profile("octocat")

print(f"Score: {result['score']}/100")
```

### FastAPI Integration

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Service automatically gets token from environment
service = GitHubAnalysisService()

class AnalyzeRequest(BaseModel):
    github_url: str  # Can be URL or username
    user_id: str = None

@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    result = service.analyze_github_profile(
        github_input=request.github_url,
        user_id=request.user_id
    )
    return result
```

### API Request Examples

```bash
# Using GitHub URL
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "github_url": "https://github.com/octocat",
    "user_id": "user_123"
  }'

# Using username only
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "github_url": "octocat",
    "user_id": "user_123"
  }'
```

---

## 🔧 Setup Instructions

### Step 1: Set Environment Variable

**Option A: Terminal (temporary)**
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

**Option B: .env file (recommended)**
```bash
# Create .env file in your project root
echo 'GITHUB_TOKEN=ghp_your_token_here' > .env
```

**Option C: System environment (permanent)**
```bash
# Linux/Mac - Add to ~/.bashrc or ~/.zshrc
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc
source ~/.bashrc

# Windows - Set in System Properties > Environment Variables
# Or use PowerShell:
[System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'ghp_your_token_here', 'User')
```

### Step 2: Verify Setup

```bash
# Check if token is set
echo $GITHUB_TOKEN  # Linux/Mac
echo %GITHUB_TOKEN%  # Windows CMD
$env:GITHUB_TOKEN   # Windows PowerShell
```

### Step 3: Run Examples

```bash
python example_usage.py
```

---

## 🎯 Supported GitHub URL Formats

All of these work:

```python
# Full HTTPS URL
service.analyze_github_profile("https://github.com/octocat")

# HTTP URL
service.analyze_github_profile("http://github.com/octocat")

# URL with trailing slash
service.analyze_github_profile("https://github.com/octocat/")

# URL without protocol
service.analyze_github_profile("github.com/octocat")

# Just username
service.analyze_github_profile("octocat")

# Mixed case (case-insensitive)
service.analyze_github_profile("https://GitHub.com/OctoCat")
```

---

## 🚫 What WON'T Work

These will be properly rejected:

```python
# Repository URLs (not profile URLs)
service.analyze_github_profile("https://github.com/octocat/Hello-World")
# Error: This is a repo, not a profile

# Invalid GitHub paths
service.analyze_github_profile("https://github.com/explore")
# Error: This is not a user profile
```

---

## 📋 Migration Checklist

- [x] Set `GITHUB_TOKEN` environment variable
- [x] Remove manual token passing in code
- [x] Update function calls to use `github_input` parameter
- [x] Update API endpoints to accept `github_url` field
- [x] Test with both URLs and usernames
- [x] Update documentation/comments in your code

---

## 🔍 Code Changes Summary

### Changed Files:

1. **github/routes/github_routes.py**
   - Auto-loads token from `GITHUB_TOKEN` env var
   - Added `extract_username_from_url()` method
   - Updated `analyze_github_profile()` to accept URLs

2. **fastapi_integration.py**
   - Removed manual token parameter
   - Changed `username` to `github_url` in requests
   - Updated all endpoints

3. **example_usage.py**
   - Removed manual token passing
   - Updated all examples to show URL usage

### No Changes Needed:

- Core analysis logic (github_client.py, repo_analyzer.py, etc.)
- Scoring algorithm
- Red flag detection
- Database persistence
- All utilities

---

## ✨ Benefits of New Approach

1. **Simpler Integration**: No need to pass token everywhere
2. **More Flexible**: Accept URLs or usernames
3. **Easier for Users**: Can copy-paste GitHub profile URLs
4. **Better for APIs**: Single input field for frontend
5. **Standard Practice**: Environment variables for secrets

---

## 🆘 Troubleshooting

### Issue: "Rate limit exceeded"

**Solution**: Make sure `GITHUB_TOKEN` is set:
```bash
export GITHUB_TOKEN="your_token_here"
python -c "import os; print('Token set:', bool(os.getenv('GITHUB_TOKEN')))"
```

### Issue: "Could not extract username from URL"

**Solution**: Check URL format. Valid examples:
- `https://github.com/username`
- `github.com/username`
- `username`

### Issue: Token not being read

**Solution**: Verify environment variable:
```python
import os
print(os.getenv('GITHUB_TOKEN'))  # Should print your token
```

---

## 📞 Support

If you have issues:
1. Check that `GITHUB_TOKEN` is set: `echo $GITHUB_TOKEN`
2. Try running `test_system.py` to verify setup
3. Check the examples in `example_usage.py`

---

**All changes are backward compatible!** If you want, you can still pass the token manually:

```python
service = GitHubAnalysisService(github_token="manual_token")
```

But it's no longer necessary! 🎉
