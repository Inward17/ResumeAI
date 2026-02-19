r"""
test_github_service.py
----------------------
Standalone script to check GitHub PAT rate limit & API usage.

USAGE (run from backend/ with venv active):

    # Check current rate limit only:
    python test_github_service.py

    # Run real GitHub API calls for a username + show usage consumed:
    python test_github_service.py octocat
    python test_github_service.py octocat torvalds
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

# ── Load token from .env ──────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

BASE_URL = "https://api.github.com"

headers = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    headers["Authorization"] = f"token {GITHUB_TOKEN}"
else:
    print("⚠️  No GITHUB_TOKEN found in .env — using unauthenticated (60 req/hr limit)\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_rate_limit() -> dict:
    r = requests.get(f"{BASE_URL}/rate_limit", headers=headers)
    r.raise_for_status()
    return r.json()

def fmt_reset(unix_ts: int) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc).astimezone()
    return dt.strftime("%H:%M:%S %Z")

def print_rate_limit(data: dict, label: str = ""):
    core   = data["resources"]["core"]
    search = data["resources"]["search"]
    graphql = data["resources"].get("graphql", {})

    title = f"  Rate Limit Snapshot{' — ' + label if label else ''}"
    print(f"\n{'─'*55}")
    print(title)
    print(f"{'─'*55}")
    print(f"  {'Category':<10} {'Limit':>6}  {'Used':>6}  {'Remaining':>10}  {'Resets at':>10}")
    print(f"  {'─'*8}  {'─'*6}  {'─'*6}  {'─'*10}  {'─'*10}")

    for name, res in [("core", core), ("search", search), ("graphql", graphql)]:
        if not res:
            continue
        print(f"  {name:<10} {res['limit']:>6}  {res['used']:>6}  {res['remaining']:>10}  {fmt_reset(res['reset']):>10}")

def print_usage_diff(before: dict, after: dict):
    b = before["resources"]["core"]
    a = after["resources"]["core"]
    consumed = a["used"] - b["used"]
    print(f"\n  📊  API calls consumed (core): {consumed}")
    print(f"      Remaining after run      : {a['remaining']}")
    print(f"      Rate limit resets at     : {fmt_reset(a['reset'])}")

# ── Run real GitHub calls for a username (mirrors actual verification code) ───
def run_for_username(username: str):
    print(f"\n{'='*55}")
    print(f"  Testing GitHub API for: {username}")
    print(f"  (mirroring actual verification flow)")
    print(f"{'='*55}")

    before = get_rate_limit()
    print_rate_limit(before, label="BEFORE")

    # ── Step 1: Fetch ALL repos (paginated, 100/page) — same as get_user_repos()
    print(f"\n  [1] Fetching ALL repos for '{username}' ...")
    repos = []
    page = 1
    try:
        while True:
            r = requests.get(
                f"{BASE_URL}/users/{username}/repos",
                headers=headers,
                params={"per_page": 100, "page": page, "type": "owner"},
            )
            if r.status_code == 404:
                print(f"  ❌  User '{username}' not found.")
                return
            if r.status_code == 403:
                print(f"  ⚠️  Rate limit exceeded (403).")
                return
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            repos.extend(data)
            if len(data) < 100:
                break
            page += 1
        print(f"       → {len(repos)} repos fetched ({page} page(s))")
    except Exception as e:
        print(f"  ❌  Error fetching repos: {e}")
        return

    # ── Step 2: For EVERY repo — commits, languages, readme (same as RepoAnalyzer)
    print(f"\n  [2] Fetching commits + languages + README for each repo ...")
    for repo in repos:
        rname = repo["name"]
        owner = repo["owner"]["login"]

        # get_repo_commits()
        requests.get(
            f"{BASE_URL}/repos/{owner}/{rname}/commits",
            headers=headers,
            params={"author": username, "per_page": 100},
        )
        # get_repo_languages()
        requests.get(f"{BASE_URL}/repos/{owner}/{rname}/languages", headers=headers)

        # get_repo_readme()
        requests.get(f"{BASE_URL}/repos/{owner}/{rname}/readme", headers=headers)

        print(f"       → {rname}: commits + languages + readme")

    after = get_rate_limit()
    print_rate_limit(after, label="AFTER")
    print_usage_diff(before, after)

    # Estimate for a full batch
    consumed = after["resources"]["core"]["used"] - before["resources"]["core"]["used"]
    print(f"\n  📐  Est. calls per candidate with {len(repos)} repos:")
    print(f"       1 (repo list) + {len(repos)}×3 (commits+lang+readme) = {1 + len(repos)*3} calls")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    usernames = sys.argv[1:]

    if not usernames:
        # Just check rate limit
        print(f"\n{'='*55}")
        print(f"  GitHub PAT Rate Limit Check")
        auth_status = "✅  Authenticated (PAT)" if GITHUB_TOKEN else "⚠️  Unauthenticated"
        print(f"  Status: {auth_status}")
        print(f"{'='*55}")
        data = get_rate_limit()
        print_rate_limit(data)
        print(f"\n  Tip: run with a GitHub username to also see per-run usage:")
        print(f"       python test_github_service.py octocat\n")
        return

    for username in usernames:
        run_for_username(username)

    print(f"\n{'='*55}")
    print(f"  Done!")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
