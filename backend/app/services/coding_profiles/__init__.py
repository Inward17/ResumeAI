"""Competitive-programming profile checks (LeetCode, HackerRank, HackerEarth, Codeforces, CodeChef)."""
from app.services.coding_profiles.handles import extract_coding_profiles, profile_url, valid_handle
from app.services.coding_profiles.fetchers import fetch_all
from app.services.coding_profiles.claims import check_profiles, coding_bonus, detect_claims, summary_line

__all__ = ["extract_coding_profiles", "profile_url", "valid_handle", "fetch_all",
           "check_profiles", "coding_bonus", "detect_claims", "summary_line"]
