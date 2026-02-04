import os
from github.routes.github_routes import GitHubAnalysisService

def check_rate_limit():
    token = os.getenv("GITHUB_TOKEN")
    masked_token = f"{token[:4]}...{token[-4:]}" if token else "None"
    print(f"Checking rate limit with token: {masked_token}")
    
    service = GitHubAnalysisService(github_token=token)
    rate_limit = service.get_rate_limit_status()
    
    if rate_limit:
        core = rate_limit.get("resources", {}).get("core", {})
        limit = core.get('limit', 0)
        remaining = core.get('remaining', 0)
        
        print("\n" + "="*40)
        print("GITHUB API STATUS")
        print("="*40)
        print(f"Limit     : {limit}")
        print(f"Remaining : {remaining}")
        
        if limit >= 5000:
            print("\n✅ AUTHENTICATED (Token is working)")
        else:
            print("\n⚠️  UNAUTHENTICATED (Using public IP limit)")
            print("Please check your GITHUB_TOKEN environment variable.")
    else:
        print("❌ Could not fetch rate limit status.")

if __name__ == "__main__":
    check_rate_limit()
