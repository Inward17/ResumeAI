import requests
from collections import defaultdict

BASE_URL = "https://api.github.com"

HEADERS = {
    "User-Agent": "GitHub-Profile-Bot"
}

MAX_REPOS_TO_SCAN = 10
MAX_COMMITS_PER_REPO = 30


def get_user_repos(username):
    url = f"{BASE_URL}/users/{username}/repos?per_page=100"
    r = requests.get(url, headers=HEADERS)
    return r.json() if r.status_code == 200 else []


def count_user_commits(owner, repo, username):
    url = f"{BASE_URL}/repos/{owner}/{repo}/commits"
    params = {
        "author": username,
        "per_page": MAX_COMMITS_PER_REPO
    }
    r = requests.get(url, headers=HEADERS, params=params)
    return len(r.json()) if r.status_code == 200 else 0

def get_repo_languages(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    r = requests.get(url, headers=HEADERS)
    return list(r.json().keys()) if r.status_code == 200 else []


def get_most_active_repos(username):
    repos = get_user_repos(username)
    activity = []

    for repo in repos[:MAX_REPOS_TO_SCAN]:
        commits = count_user_commits(
            repo["owner"]["login"],
            repo["name"],
            username
        )

        if commits > 0:
            activity.append({
                "repo": repo["full_name"],
                "commits": commits,
                "stars": repo["stargazers_count"],
                "tech_stack": get_repo_languages(
                    repo["owner"]["login"],
                    repo["name"]
                )
            })


    return sorted(activity, key=lambda x: x["commits"], reverse=True)
