"""
Tests for GitHub services: GitHubClient, RepoAnalyzer, ReadmeAnalyzer, ScoreEngine.
All GitHub API calls mocked via unittest.mock.
"""
import pytest
import base64
from unittest.mock import patch, MagicMock, PropertyMock

from app.services.github_services.github_client import GitHubClient
from app.services.github_services.repo_analyzer import RepoAnalyzer
from app.services.github_services.readme_analyzer import ReadmeAnalyzer
from app.services.github_services.score_engine import ScoreEngine


# ============================================================================
# GitHubClient tests
# ============================================================================
class TestGitHubClient:
    def setup_method(self):
        self.client = GitHubClient(token="fake-token")

    def test_init_with_token(self):
        assert self.client.token == "fake-token"
        assert "Authorization" in self.client.session.headers

    def test_init_without_token(self):
        client = GitHubClient()
        assert client.token is None
        assert "Authorization" not in client.session.headers

    def test_get_user_repos_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "repo1", "owner": {"login": "testuser"}},
            {"name": "repo2", "owner": {"login": "testuser"}},
        ]
        self.client.session.get = MagicMock(return_value=mock_response)

        repos = self.client.get_user_repos("testuser")
        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"

    def test_get_user_repos_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        self.client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(ValueError, match="not found"):
            self.client.get_user_repos("nonexistent")

    def test_get_user_repos_rate_limited(self):
        mock_response = MagicMock()
        mock_response.status_code = 403
        self.client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(Exception, match="Rate limit"):
            self.client.get_user_repos("testuser")

    def test_get_user_repos_api_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        self.client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(Exception, match="GitHub API error"):
            self.client.get_user_repos("testuser")

    def test_get_user_repos_pagination(self):
        # First page returns 100 repos, second page returns 50
        page1 = [{"name": f"repo{i}", "owner": {"login": "testuser"}} for i in range(100)]
        page2 = [{"name": f"repo{i}", "owner": {"login": "testuser"}} for i in range(100, 150)]

        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = page1

        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = page2

        self.client.session.get = MagicMock(side_effect=[mock_resp1, mock_resp2])
        repos = self.client.get_user_repos("testuser")
        assert len(repos) == 150

    def test_get_repo_languages(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Python": 50000, "JavaScript": 20000}
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_languages("testuser", "my-repo")
        assert result["Python"] == 50000

    def test_get_repo_languages_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_languages("testuser", "missing-repo")
        assert result == {}

    def test_get_repo_readme(self):
        encoded = base64.b64encode(b"# My Project\nThis is a README").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": encoded}
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_readme("testuser", "my-repo")
        assert "My Project" in result

    def test_get_repo_readme_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_readme("testuser", "no-readme")
        assert result is None

    def test_get_repo_commits(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"sha": "abc123", "commit": {"author": {"date": "2024-01-15T10:00:00Z"}}},
        ]
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_commits("testuser", "my-repo", "testuser")
        assert len(result) == 1

    def test_get_repo_commits_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.get_repo_commits("testuser", "my-repo", "testuser")
        assert result == []

    def test_check_rate_limit(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rate": {"remaining": 4999}}
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.check_rate_limit()
        assert result["rate"]["remaining"] == 4999

    def test_check_rate_limit_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        self.client.session.get = MagicMock(return_value=mock_response)

        result = self.client.check_rate_limit()
        assert result == {}


# ============================================================================
# RepoAnalyzer tests
# ============================================================================
class TestRepoAnalyzer:
    def setup_method(self):
        self.mock_client = MagicMock(spec=GitHubClient)
        self.analyzer = RepoAnalyzer(self.mock_client)

    def test_analyze_repos_basic(self, sample_github_repos, sample_commits):
        self.mock_client.get_repo_commits.return_value = sample_commits
        self.mock_client.get_repo_languages.return_value = {"Python": 50000}

        result = self.analyzer.analyze_repos("testuser", sample_github_repos)

        assert result["repositoryStats"]["total"] == 3
        assert result["repositoryStats"]["original"] >= 1
        assert result["commitStats"]["total"] > 0

    def test_analyze_repos_fork_detection(self, sample_github_repo):
        forked = {**sample_github_repo, "fork": True, "name": "forked"}
        self.mock_client.get_repo_commits.return_value = []
        self.mock_client.get_repo_languages.return_value = {}

        result = self.analyzer.analyze_repos("testuser", [sample_github_repo, forked])
        assert result["repositoryStats"]["forked"] >= 1

    def test_analyze_repos_empty(self):
        result = self.analyzer.analyze_repos("testuser", [])
        assert result["repositoryStats"]["total"] == 0

    def test_oss_contribution_detection(self, sample_github_repo):
        oss_repo = {
            **sample_github_repo,
            "fork": True,
            "full_name": "tensorflow/tensorflow",
            "name": "tensorflow",
        }
        # 10+ commits from allowlisted org counts as OSS
        commits = [{"commit": {"author": {"date": f"2024-01-{i:02d}T10:00:00Z"}}} for i in range(1, 15)]
        self.mock_client.get_repo_commits.return_value = commits
        self.mock_client.get_repo_languages.return_value = {"Python": 100000}

        result = self.analyzer.analyze_repos("testuser", [oss_repo])
        assert result["ossContributions"] >= 1

    def test_trivial_repo_count(self, sample_github_repos, sample_commits):
        self.mock_client.get_repo_commits.return_value = sample_commits
        self.mock_client.get_repo_languages.return_value = {}

        result = self.analyzer.analyze_repos("testuser", sample_github_repos)
        # "todo-app" is trivial
        assert result["trivialRepos"] >= 1

    def test_dump_pattern_aggregation(self, sample_github_repo):
        # All commits on same day
        dump_commits = [{"commit": {"author": {"date": "2024-01-15T10:00:00Z"}}} for _ in range(10)]
        self.mock_client.get_repo_commits.return_value = dump_commits
        self.mock_client.get_repo_languages.return_value = {}

        result = self.analyzer.analyze_repos("testuser", [sample_github_repo])
        assert result["reposDumpPattern"] >= 1


# ============================================================================
# ReadmeAnalyzer tests
# ============================================================================
class TestReadmeAnalyzer:
    def setup_method(self):
        self.mock_client = MagicMock(spec=GitHubClient)
        self.analyzer = ReadmeAnalyzer(self.mock_client)

    def _make_enriched_repo(self, name="test-repo", languages=None):
        return {
            "name": name,
            "owner": "testuser",
            "full_name": f"testuser/{name}",
            "languages": languages or {"Python": 50000},
        }

    def test_analyze_readmes_with_readme(self):
        repo = self._make_enriched_repo()
        self.mock_client.get_repo_readme.return_value = (
            "# My Python Project\nThis project uses Python and FastAPI to build APIs."
        )

        result = self.analyzer.analyze_readmes([repo])
        assert result["readmeStats"]["repos_with_readme"] == 1
        assert result["readmeStats"]["repos_without_readme"] == 0
        assert result["readmeStats"]["readme_presence_ratio"] == 1.0

    def test_analyze_readmes_without_readme(self):
        repo = self._make_enriched_repo()
        self.mock_client.get_repo_readme.return_value = None

        result = self.analyzer.analyze_readmes([repo])
        assert result["readmeStats"]["repos_without_readme"] == 1
        assert result["readmeStats"]["readme_presence_ratio"] == 0.0

    def test_short_readme_detection(self):
        repo = self._make_enriched_repo()
        self.mock_client.get_repo_readme.return_value = "Short"  # < 100 chars

        result = self.analyzer.analyze_readmes([repo])
        assert result["readmeStats"]["repos_with_short_readme"] == 1

    def test_language_mismatch_detected(self):
        # README mentions Python but repo is Java
        repo = self._make_enriched_repo(languages={"Java": 50000})
        self.mock_client.get_repo_readme.return_value = (
            "# Python Project\nThis project uses Python and Django framework."
        )

        result = self.analyzer.analyze_readmes([repo])
        # Single repo mismatch won't trigger global mismatch (needs 2+)
        assert result["languageMatchStats"]["repos_with_mismatch"] >= 1

    def test_no_language_mismatch(self):
        repo = self._make_enriched_repo(languages={"Python": 50000})
        self.mock_client.get_repo_readme.return_value = (
            "# Python Project\nBuilt with Python and FastAPI."
        )

        result = self.analyzer.analyze_readmes([repo])
        assert result["languageMatchStats"]["repos_with_mismatch"] == 0

    def test_global_mismatch_threshold(self):
        """Global mismatch only when 2+ repos have mismatch."""
        repos = [
            self._make_enriched_repo("repo1", {"Java": 50000}),
            self._make_enriched_repo("repo2", {"Rust": 50000}),
        ]
        self.mock_client.get_repo_readme.return_value = (
            "# Python Project\nBuilt with Python and Django."
        )

        result = self.analyzer.analyze_readmes(repos)
        assert result["languageMatchStats"]["has_global_mismatch"] is True

    def test_get_dominant_languages(self):
        languages = {"Python": 50000, "JavaScript": 20000, "CSS": 5000, "HTML": 3000}
        result = self.analyzer.get_dominant_languages(languages, top_n=2)
        assert result == ["Python", "JavaScript"]

    def test_get_dominant_languages_empty(self):
        assert self.analyzer.get_dominant_languages({}) == []


# ============================================================================
# ScoreEngine tests
# ============================================================================
class TestScoreEngine:
    def setup_method(self):
        self.engine = ScoreEngine()

    def _make_analysis(
        self,
        original_ratio=0.8,
        avg_commits=15.0,
        readme_ratio=0.8,
        has_mismatch=False,
        oss=0,
        trivial=0,
        dump_pattern=0,
    ):
        repo_analysis = {
            "repositoryStats": {
                "total": 10,
                "original": int(10 * original_ratio),
                "forked": 10 - int(10 * original_ratio),
                "original_ratio": original_ratio,
            },
            "commitStats": {
                "total": int(avg_commits * 10),
                "average_per_repo": avg_commits,
                "repos_with_low_commits": 2,
                "lastCommitDate": "2024-06-01T00:00:00Z",
            },
            "commitSpread": {
                "is_dump_pattern": dump_pattern > 0,
                "total_commits": int(avg_commits * 10),
                "unique_days": 20,
                "max_day_ratio": 0.3,
            },
            "ossContributions": oss,
            "trivialRepos": trivial,
            "reposDumpPattern": dump_pattern,
            "enrichedRepositories": [],
        }
        readme_analysis = {
            "readmeStats": {
                "repos_with_readme": int(10 * readme_ratio),
                "repos_without_readme": 10 - int(10 * readme_ratio),
                "repos_with_short_readme": 0,
                "readme_presence_ratio": readme_ratio,
            },
            "languageMatchStats": {
                "repos_with_mismatch": 3 if has_mismatch else 0,
                "has_global_mismatch": has_mismatch,
            },
            "enhancedRepositories": [],
        }
        return repo_analysis, readme_analysis

    def test_good_profile_high_score(self):
        repo_a, readme_a = self._make_analysis(
            original_ratio=1.0, avg_commits=50, readme_ratio=1.0, oss=3
        )
        result = self.engine.compute_score(repo_a, readme_a)
        assert result["score"] >= 80
        assert len(result["redFlags"]) == 0

    def test_poor_profile_low_score(self):
        repo_a, readme_a = self._make_analysis(
            original_ratio=0.2, avg_commits=2, readme_ratio=0.2, has_mismatch=True, trivial=5
        )
        result = self.engine.compute_score(repo_a, readme_a)
        assert result["score"] < 50
        assert len(result["redFlags"]) > 0

    def test_red_flags_mostly_forked(self):
        repo_a, readme_a = self._make_analysis(original_ratio=0.3)
        result = self.engine.compute_score(repo_a, readme_a)
        assert "Mostly forked" in " ".join(result["redFlags"])

    def test_red_flags_low_commit(self):
        repo_a, readme_a = self._make_analysis(avg_commits=2)
        result = self.engine.compute_score(repo_a, readme_a)
        assert any("commit" in f.lower() for f in result["redFlags"])

    def test_red_flags_missing_readme(self):
        repo_a, readme_a = self._make_analysis(readme_ratio=0.3)
        result = self.engine.compute_score(repo_a, readme_a)
        assert any("readme" in f.lower() for f in result["redFlags"])

    def test_red_flags_tech_mismatch(self):
        repo_a, readme_a = self._make_analysis(has_mismatch=True)
        result = self.engine.compute_score(repo_a, readme_a)
        assert any("match" in f.lower() for f in result["redFlags"])

    def test_red_flags_trivial_repos(self):
        repo_a, readme_a = self._make_analysis(trivial=5)
        result = self.engine.compute_score(repo_a, readme_a)
        assert any("trivial" in f.lower() for f in result["redFlags"])

    def test_score_capped_at_100(self):
        repo_a, readme_a = self._make_analysis(
            original_ratio=1.0, avg_commits=100, readme_ratio=1.0, oss=5
        )
        result = self.engine.compute_score(repo_a, readme_a)
        assert result["score"] <= 100

    def test_score_minimum_zero(self):
        repo_a, readme_a = self._make_analysis(
            original_ratio=0.0, avg_commits=0, readme_ratio=0.0, has_mismatch=True, trivial=8, dump_pattern=5
        )
        result = self.engine.compute_score(repo_a, readme_a)
        assert result["score"] >= 0

    def test_oss_bonus_applied(self):
        repo_no_oss, readme = self._make_analysis(oss=0)
        repo_oss, _ = self._make_analysis(oss=3)
        score_no_oss = self.engine.compute_score(repo_no_oss, readme)
        score_oss = self.engine.compute_score(repo_oss, readme)
        assert score_oss["score"] > score_no_oss["score"]

    def test_penalty_capped(self):
        """Penalty is capped at RED_FLAG_PENALTY_MAX (25)."""
        repo_a, readme_a = self._make_analysis(
            original_ratio=0.1, avg_commits=1, readme_ratio=0.1, has_mismatch=True, trivial=8, dump_pattern=5
        )
        result = self.engine.compute_score(repo_a, readme_a)
        assert result["components"]["penalty"] <= 25

    def test_components_present(self):
        repo_a, readme_a = self._make_analysis()
        result = self.engine.compute_score(repo_a, readme_a)
        assert "original_ratio" in result["components"]
        assert "commit_depth" in result["components"]
        assert "readme_presence" in result["components"]
        assert "language_match" in result["components"]
        assert "oss_bonus" in result["components"]
        assert "penalty" in result["components"]

    def test_breakdown_present(self):
        repo_a, readme_a = self._make_analysis()
        result = self.engine.compute_score(repo_a, readme_a)
        assert "raw_score" in result["breakdown"]
        assert "total_penalty" in result["breakdown"]
        assert "final_score" in result["breakdown"]
