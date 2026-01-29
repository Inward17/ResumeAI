# Deployment & Integration Guide

## 📋 Pre-Deployment Checklist

- [ ] Python 3.8+ installed
- [ ] GitHub Personal Access Token created
- [ ] Database configured (if using persistence)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Environment variables configured (`.env` file)
- [ ] Tests passing (`python test_system.py`)

## 🚀 Deployment Options

### Option 1: Standalone Script

**Use Case**: Simple integration, scheduled jobs, CLI tools

```python
# your_application.py
from github.routes.github_routes import GitHubAnalysisService

service = GitHubAnalysisService(github_token="your_token")
result = service.analyze_github_profile("username")
```

**Pros**: Simple, no server needed  
**Cons**: No API endpoint, manual integration

---

### Option 2: FastAPI REST API

**Use Case**: Microservice, web application backend, multi-client access

```bash
# Install dependencies
pip install fastapi uvicorn python-dotenv

# Run server
python fastapi_integration.py
# or
uvicorn fastapi_integration:app --host 0.0.0.0 --port 8000
```

**Endpoints**:
- `POST /analyze` - Analyze single profile
- `POST /batch-analyze` - Analyze multiple profiles
- `GET /rate-limit` - Check API rate limits
- `GET /health` - Health check

**Pros**: RESTful, scalable, easy to integrate  
**Cons**: Requires server infrastructure

---

### Option 3: Background Job/Queue

**Use Case**: Async processing, high volume, avoiding rate limits

```python
# celery_task.py
from celery import Celery
from github.routes.github_routes import GitHubAnalysisService

app = Celery('github_tasks', broker='redis://localhost:6379')

@app.task
def analyze_github_async(username, user_id):
    service = GitHubAnalysisService(github_token="your_token")
    result = service.analyze_github_profile(username, user_id)
    return result

# Usage
analyze_github_async.delay("octocat", "user_123")
```

**Pros**: Async, handles rate limits well, scalable  
**Cons**: Requires queue infrastructure (Redis, RabbitMQ)

---

## 🔧 Configuration

### 1. GitHub Token

```bash
# Get token at: https://github.com/settings/tokens
# Required scope: public_repo

export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

**Rate Limits**:
- Without token: 60 requests/hour
- With token: 5,000 requests/hour

### 2. Database Setup

#### MongoDB Example

```python
from pymongo import MongoClient
from github.routes.github_routes import GitHubAnalysisService

client = MongoClient("mongodb://localhost:27017")
db = client.your_database

service = GitHubAnalysisService(
    github_token="your_token",
    db_client=db
)
```

#### PostgreSQL Example

```python
from sqlalchemy import create_engine
from github.persistence.github_writer import GitHubWriter

engine = create_engine("postgresql://user:pass@localhost/db")

# Adapt GitHubWriter for SQL
writer = GitHubWriter(db_client=engine)
```

### 3. Customizing Thresholds

Edit `github/utils/constants.py`:

```python
# Adjust scoring weights
WEIGHTS = {
    "original_repo_ratio": 30,
    "commit_depth": 25,
    "readme_presence": 15,
    "readme_language_match": 15,
    "oss_contribution_bonus": 10
}

# Adjust thresholds
MIN_COMMITS_PER_REPO = 5
MIN_README_LENGTH = 100
COMMIT_DUMP_RATIO = 0.70
```

---

## 🔄 Integration Patterns

### Pattern 1: Verification Pipeline

```python
def verify_developer(user_id, github_username):
    """Add GitHub verification to existing pipeline"""
    service = GitHubAnalysisService(github_token=TOKEN)
    
    result = service.analyze_github_profile(
        username=github_username,
        user_id=user_id
    )
    
    # Update user record
    return {
        "user_id": user_id,
        "github_verified": result["score"] >= 60,
        "github_score": result["score"],
        "red_flags": result["redFlags"],
        "verified_at": datetime.utcnow()
    }
```

### Pattern 2: Batch Processing

```python
def process_candidate_batch(candidates):
    """Process multiple candidates efficiently"""
    service = GitHubAnalysisService(github_token=TOKEN)
    
    results = []
    for candidate in candidates:
        try:
            result = service.analyze_github_profile(
                username=candidate["github_username"],
                user_id=candidate["id"]
            )
            results.append({
                "candidate_id": candidate["id"],
                "score": result["score"],
                "verified": result["score"] >= 60
            })
        except Exception as e:
            results.append({
                "candidate_id": candidate["id"],
                "error": str(e),
                "verified": False
            })
    
    return results
```

### Pattern 3: Webhook Integration

```python
@app.post("/webhook/github-verified")
async def github_verified_webhook(user_id: str, github_username: str):
    """Handle GitHub verification webhook"""
    service = GitHubAnalysisService(github_token=TOKEN)
    
    result = service.analyze_github_profile(
        username=github_username,
        user_id=user_id
    )
    
    # Trigger follow-up actions
    if result["score"] >= 80:
        send_email("high_score_notification", user_id)
    elif len(result["redFlags"]) > 2:
        send_email("review_required", user_id)
    
    return result
```

---

## 📊 Monitoring & Logging

### Add Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# In your code
logger = logging.getLogger(__name__)

result = service.analyze_github_profile(username)
logger.info(f"Analyzed {username}: score={result['score']}")
```

### Monitor Rate Limits

```python
def monitor_rate_limits():
    """Check rate limits before batch processing"""
    service = GitHubAnalysisService(github_token=TOKEN)
    rate_limit = service.get_rate_limit_status()
    
    core = rate_limit["resources"]["core"]
    remaining = core["remaining"]
    
    if remaining < 100:
        logger.warning(f"Low rate limit: {remaining} requests remaining")
        # Wait or use different token
    
    return remaining
```

---

## 🔒 Security Best Practices

1. **Never commit tokens to version control**
   ```bash
   # Add to .gitignore
   .env
   *.pem
   config/secrets.py
   ```

2. **Use environment variables**
   ```python
   import os
   token = os.getenv("GITHUB_TOKEN")
   if not token:
       raise ValueError("GITHUB_TOKEN not set")
   ```

3. **Rotate tokens regularly**
   - Create new token every 90 days
   - Use different tokens for different environments

4. **Limit token scope**
   - Use `public_repo` scope only
   - Don't request admin or write permissions

---

## 🧪 Testing in Production

### Smoke Test

```python
def smoke_test():
    """Quick test after deployment"""
    service = GitHubAnalysisService(github_token=TOKEN)
    
    # Test with known user
    result = service.analyze_github_profile("octocat")
    
    assert result["success"] == True
    assert 0 <= result["score"] <= 100
    assert isinstance(result["redFlags"], list)
    
    print("✅ Smoke test passed")
```

### Load Test

```python
import concurrent.futures

def load_test(usernames, max_workers=5):
    """Test under load"""
    service = GitHubAnalysisService(github_token=TOKEN)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(service.analyze_github_profile, username)
            for username in usernames
        ]
        
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    return results
```

---

## 🚨 Troubleshooting

### Issue: Rate Limit Exceeded

**Symptom**: `403` errors from GitHub API

**Solutions**:
1. Add GitHub token to increase limit (60 → 5000/hour)
2. Implement caching for repeated analyses
3. Use queue system for batch processing
4. Add exponential backoff retry logic

### Issue: Slow Performance

**Symptom**: Analysis takes > 30 seconds

**Solutions**:
1. Check network latency to GitHub API
2. Enable caching for repo data
3. Reduce `MAX_COMMITS_PER_REPO` in constants
4. Use async/parallel processing

### Issue: Inconsistent Scores

**Symptom**: Same user gets different scores

**Causes**:
- Commits pushed between analyses
- Fork status changed
- Repos added/deleted

**Solution**: Cache results with TTL, show "last analyzed" timestamp

---

## 📈 Scaling Strategies

### Horizontal Scaling

```python
# Deploy multiple API instances behind load balancer
# Each instance uses same GitHub token pool

# nginx.conf
upstream github_api {
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
}
```

### Caching Layer

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedGitHubService:
    def __init__(self, service, ttl_hours=24):
        self.service = service
        self.cache = {}
        self.ttl = timedelta(hours=ttl_hours)
    
    def analyze(self, username):
        if username in self.cache:
            result, timestamp = self.cache[username]
            if datetime.now() - timestamp < self.ttl:
                return result
        
        result = self.service.analyze_github_profile(username)
        self.cache[username] = (result, datetime.now())
        return result
```

### Database Indexing

```javascript
// MongoDB indexes
db.verification_data.createIndex({"githubData.username": 1})
db.verification_data.createIndex({"githubData.score": -1})
db.verification_data.createIndex({"githubData.analyzedAt": -1})
```

---

## 🎯 Performance Benchmarks

**Single Analysis**:
- Small profile (< 10 repos): ~2-5 seconds
- Medium profile (10-50 repos): ~5-15 seconds
- Large profile (50+ repos): ~15-30 seconds

**Batch Processing** (with token):
- 100 profiles: ~10-15 minutes
- 1000 profiles: ~2-3 hours

**API Calls per Analysis**:
- Minimum: 2 (repos + commits)
- Average: 4-6 (+ languages, READMEs)
- Maximum: 10-15 (large profiles with many repos)

---

## 📞 Support Checklist

Before asking for help, verify:

- [ ] Test suite passes (`python test_system.py`)
- [ ] GitHub token is valid and has correct scopes
- [ ] Rate limits are not exceeded
- [ ] Network connectivity to api.github.com
- [ ] Python version is 3.8+
- [ ] All dependencies installed
- [ ] Error messages and logs available

---

## 🔄 Update & Maintenance

### Monthly Tasks
- Check for GitHub API changes
- Review and update OSS allowlist
- Analyze false positive rate
- Update language keywords

### Quarterly Tasks
- Audit scoring weights based on feedback
- Review red flag thresholds
- Update documentation
- Security audit (token rotation)

### Version Control
```bash
# Tag releases
git tag -a v1.0.0 -m "Initial production release"
git push origin v1.0.0
```
