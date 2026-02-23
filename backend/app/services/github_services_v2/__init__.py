"""
Enterprise GitHub Verification Service
Public API: verify_github, GitHubVerificationResult
"""

from .github_service import verify_github
from .models import GitHubVerificationResult

__all__ = ["verify_github", "GitHubVerificationResult"]
