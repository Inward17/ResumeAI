"""
Test Script - Validates the GitHub Ownership Score implementation
Run this to ensure all modules are working correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github.services.github_client import GitHubClient
from github.services.repo_analyzer import RepoAnalyzer
from github.services.readme_analyzer import ReadmeAnalyzer
from github.services.score_engine import ScoreEngine
from github.persistence.github_writer import GitHubWriter
from github.utils.constants import WEIGHTS, OSS_ALLOWLIST, RED_FLAGS
from github.utils.text_utils import extract_keywords_from_text, is_trivial_repo_name
from github.utils.date_utils import analyze_commit_spread, parse_github_date


def test_constants():
    """Test that constants are properly defined"""
    print("Testing constants...")
    assert sum(WEIGHTS.values()) == 95  # Should sum to 95 (100 - 5 for flexibility)
    assert len(OSS_ALLOWLIST) > 30
    assert len(RED_FLAGS) == 6
    print("✅ Constants test passed")


def test_text_utils():
    """Test text utility functions"""
    print("\nTesting text utilities...")
    
    # Test keyword extraction
    readme = "This is a Python project using Django and FastAPI"
    keywords = extract_keywords_from_text(readme)
    assert "Python" in keywords
    print(f"  Detected languages: {keywords}")
    
    # Test trivial repo detection
    assert is_trivial_repo_name("todo-app", ["todo"]) == True
    assert is_trivial_repo_name("awesome-project", ["todo"]) == False
    print("✅ Text utils test passed")


def test_date_utils():
    """Test date utility functions"""
    print("\nTesting date utilities...")
    
    # Test commit spread analysis
    dates = [
        "2024-01-01T10:00:00Z",
        "2024-01-01T11:00:00Z",
        "2024-01-01T12:00:00Z",
        "2024-01-02T10:00:00Z",
        "2024-01-15T10:00:00Z",
    ]
    
    spread = analyze_commit_spread(dates)
    assert spread["total_commits"] == 5
    assert spread["unique_days"] == 3
    assert spread["is_dump_pattern"] == True  # 3 commits on same day
    print(f"  Spread analysis: {spread}")
    print("✅ Date utils test passed")


def test_github_client_structure():
    """Test GitHub client structure (without making API calls)"""
    print("\nTesting GitHub client structure...")
    
    client = GitHubClient()
    assert hasattr(client, 'get_user_repos')
    assert hasattr(client, 'get_repo_languages')
    assert hasattr(client, 'get_repo_readme')
    assert hasattr(client, 'get_repo_commits')
    print("✅ GitHub client structure test passed")


def test_score_engine():
    """Test score engine with mock data"""
    print("\nTesting score engine...")
    
    engine = ScoreEngine()
    
    # Mock data
    repo_analysis = {
        "repositoryStats": {
            "total": 10,
            "original": 8,
            "forked": 2,
            "original_ratio": 0.8
        },
        "commitStats": {
            "total": 200,
            "average_per_repo": 20.0,
            "repos_with_low_commits": 1,
        },
        "commitSpread": {
            "total_commits": 200,
            "unique_days": 50,
            "is_dump_pattern": False,
        },
        "ossContributions": 2,
        "trivialRepos": 1,
        "reposDumpPattern": 0,
    }
    
    readme_analysis = {
        "readmeStats": {
            "repos_with_readme": 8,
            "repos_without_readme": 2,
            "readme_presence_ratio": 0.8,
        },
        "languageMatchStats": {
            "repos_with_mismatch": 0,
            "has_global_mismatch": False,
        }
    }
    
    result = engine.compute_score(repo_analysis, readme_analysis)
    
    assert 0 <= result["score"] <= 100
    assert "components" in result
    assert "redFlags" in result
    print(f"  Mock score: {result['score']}/100")
    print(f"  Red flags: {result['redFlags']}")
    print("✅ Score engine test passed")


def test_github_writer():
    """Test GitHub writer structure"""
    print("\nTesting GitHub writer...")
    
    writer = GitHubWriter()
    assert hasattr(writer, 'write_github_data')
    assert hasattr(writer, 'get_github_data')
    print("✅ GitHub writer structure test passed")


def test_full_pipeline_structure():
    """Test that all components can be initialized together"""
    print("\nTesting full pipeline structure...")
    
    client = GitHubClient()
    repo_analyzer = RepoAnalyzer(client)
    readme_analyzer = ReadmeAnalyzer(client)
    score_engine = ScoreEngine()
    writer = GitHubWriter()
    
    print("✅ Full pipeline structure test passed")


def test_integration_mock():
    """Integration test with fully mocked data"""
    print("\nTesting integration with mock data...")
    
    # This tests the scoring logic without hitting GitHub API
    engine = ScoreEngine()
    
    # High-quality profile mock
    high_quality = {
        "repositoryStats": {"total": 20, "original": 18, "forked": 2, "original_ratio": 0.9},
        "commitStats": {"total": 500, "average_per_repo": 25.0, "repos_with_low_commits": 1},
        "commitSpread": {"is_dump_pattern": False},
        "ossContributions": 3,
        "trivialRepos": 1,
        "reposDumpPattern": 0,
    }
    
    high_quality_readme = {
        "readmeStats": {"repos_with_readme": 18, "readme_presence_ratio": 0.9},
        "languageMatchStats": {"has_global_mismatch": False}
    }
    
    result_high = engine.compute_score(high_quality, high_quality_readme)
    
    # Low-quality profile mock
    low_quality = {
        "repositoryStats": {"total": 10, "original": 3, "forked": 7, "original_ratio": 0.3},
        "commitStats": {"total": 30, "average_per_repo": 3.0, "repos_with_low_commits": 7},
        "commitSpread": {"is_dump_pattern": True},
        "ossContributions": 0,
        "trivialRepos": 5,
        "reposDumpPattern": 3,
    }
    
    low_quality_readme = {
        "readmeStats": {"repos_with_readme": 3, "readme_presence_ratio": 0.3},
        "languageMatchStats": {"has_global_mismatch": True}
    }
    
    result_low = engine.compute_score(low_quality, low_quality_readme)
    
    print(f"  High-quality profile score: {result_high['score']}/100")
    print(f"  Low-quality profile score: {result_low['score']}/100")
    
    assert result_high["score"] > result_low["score"]
    assert result_high["score"] >= 70
    assert result_low["score"] <= 50
    print("✅ Integration mock test passed")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("GitHub Ownership Score - Test Suite")
    print("=" * 60)
    
    try:
        test_constants()
        test_text_utils()
        test_date_utils()
        test_github_client_structure()
        test_score_engine()
        test_github_writer()
        test_full_pipeline_structure()
        test_integration_mock()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nSystem is ready for use!")
        print("Next steps:")
        print("1. Set GITHUB_TOKEN environment variable")
        print("2. Run: python example_usage.py")
        print("3. Integrate with your application")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
