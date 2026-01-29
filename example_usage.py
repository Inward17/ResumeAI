"""
Example Usage Script - GitHub Ownership Score Analysis
Demonstrates how to use the GitHub analysis system
"""
import os
import json
from github.routes.github_routes import GitHubAnalysisService


def example_basic_analysis():
    """Basic example: Analyze a GitHub username"""
    
    # Initialize service (with optional GitHub token for higher rate limits)
    github_token = os.getenv("GITHUB_TOKEN")  # Optional but recommended
    service = GitHubAnalysisService(github_token=github_token)
    
    # Analyze a GitHub profile
    username = "Inward17"  # Example username
    print(f"Analyzing GitHub profile: {username}")
    print("=" * 60)
    
    result = service.analyze_github_profile(username)
    
    if result["success"]:
        print(f"\n✅ Analysis Successful")
        print(f"\nGitHub Ownership Score: {result['score']}/100")
        print(f"\nScore Components:")
        for component, score in result['components'].items():
            print(f"  - {component}: {score}")
        
        print(f"\nRed Flags: {len(result['redFlags'])}")
        for flag in result['redFlags']:
            print(f"  ⚠️  {flag}")
        
        print(f"\nRepository Statistics:")
        stats = result['repositoryStats']
        print(f"  - Total repos: {stats['total']}")
        print(f"  - Original repos: {stats['original']}")
        print(f"  - Forked repos: {stats['forked']}")
        print(f"  - Original ratio: {stats['original_ratio']:.2%}")
        
        print(f"\nCommit Statistics:")
        commit_stats = result['commitStats']
        print(f"  - Total commits: {commit_stats['total']}")
        print(f"  - Average per repo: {commit_stats['average_per_repo']:.1f}")
        print(f"  - Last commit: {commit_stats['lastCommitDate'][:10] if commit_stats['lastCommitDate'] else 'N/A'}")
        
        print(f"\nREADME Statistics:")
        readme_stats = result['readmeStats']
        print(f"  - Repos with README: {readme_stats['repos_with_readme']}")
        print(f"  - README presence ratio: {readme_stats['readme_presence_ratio']:.2%}")
    else:
        print(f"\n❌ Analysis Failed: {result['error']}")


def example_with_persistence():
    """Example with database persistence"""
    
    # Initialize service with database client
    # db_client = YourDatabaseClient()  # MongoDB, PostgreSQL, etc.
    service = GitHubAnalysisService(
        github_token=os.getenv("GITHUB_TOKEN"),
        db_client=None  # Pass your DB client here
    )
    
    # Analyze and persist
    result = service.analyze_github_profile(
        username="octocat",
        user_id="user_12345"  # Your application's user ID
    )
    
    if result["success"]:
        print(f"Analysis completed and persisted for user_12345")
        print(f"Score: {result['score']}/100")


def example_check_rate_limit():
    """Check GitHub API rate limit"""
    
    service = GitHubAnalysisService(github_token=os.getenv("GITHUB_TOKEN"))
    
    rate_limit = service.get_rate_limit_status()
    
    if rate_limit:
        core = rate_limit.get("resources", {}).get("core", {})
        print(f"GitHub API Rate Limit:")
        print(f"  - Limit: {core.get('limit', 'N/A')}")
        print(f"  - Remaining: {core.get('remaining', 'N/A')}")
        print(f"  - Reset: {core.get('reset', 'N/A')}")


def example_export_results():
    """Export analysis results to JSON"""
    
    service = GitHubAnalysisService(github_token=os.getenv("GITHUB_TOKEN"))
    
    username = "gvanrossum"  # Example username
    result = service.analyze_github_profile(username)
    
    if result["success"]:
        # Export to JSON file
        output_file = f"{username}_github_analysis.json"
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Results exported to: {output_file}")


def example_batch_analysis():
    """Analyze multiple GitHub profiles"""
    
    service = GitHubAnalysisService(github_token=os.getenv("GITHUB_TOKEN"))
    
    usernames = ["POPPz07", "Rohan-Mohite14", "sohamminiyar", "octocat"]
    results = []
    
    print("Batch Analysis")
    print("=" * 60)
    
    for username in usernames:
        print(f"\nAnalyzing: {username}")
        result = service.analyze_github_profile(username)
        
        if result["success"]:
            print(f"  ✅ Score: {result['score']}/100")
            print(f"  ⚠️  Red Flags: {len(result['redFlags'])}")
            results.append({
                "username": username,
                "score": result["score"],
                "red_flags_count": len(result["redFlags"])
            })
        else:
            print(f"  ❌ Failed: {result['error']}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Batch Summary:")
    for r in results:
        print(f"  {r['username']}: {r['score']}/100 (flags: {r['red_flags_count']})")


if __name__ == "__main__":
    print("GitHub Ownership Score - Example Usage")
    print("=" * 60)
    print()
    
    # Run basic example
    example_basic_analysis()
    
    # Uncomment to run other examples:
    # example_with_persistence()
    # example_check_rate_limit()
    # example_export_results()
    # example_batch_analysis()