import requests
import os
from collections import defaultdict
from dotenv import load_dotenv

# =========================
# ENV + CONFIG
# =========================
load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    print("❌ GITHUB_TOKEN not found")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "GitHub-Full-Profile-Bot"
}

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

MAX_ACTIVE_REPOS = 5
MAX_COMMITS_PER_REPO = 30

# =========================
# GRAPHQL: PINNED REPOS
# =========================
def get_pinned_repos(username):
    query = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: [REPOSITORY]) {
          nodes {
            ... on Repository {
              nameWithOwner
              stargazerCount
              forkCount
              languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                edges {
                  size
                  node { name }
                }
              }
            }
          }
        }
      }
    }
    """
    r = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": {"login": username}},
        headers=HEADERS
    )
    return r.json()["data"]["user"]["pinnedItems"]["nodes"]

# =========================
# REST HELPERS
# =========================
def get_repo_languages(owner, repo):
    url = f"{REST_URL}/repos/{owner}/{repo}/languages"
    r = requests.get(url, headers=HEADERS)
    return r.json() if r.status_code == 200 else {}

def count_user_commits(owner, repo, username):
    url = f"{REST_URL}/repos/{owner}/{repo}/commits"
    r = requests.get(
        url,
        headers=HEADERS,
        params={"author": username, "per_page": MAX_COMMITS_PER_REPO}
    )
    return len(r.json()) if r.status_code == 200 else 0

def get_repo_files(owner, repo):
    url = f"{REST_URL}/repos/{owner}/{repo}/contents"
    r = requests.get(url, headers=HEADERS)
    return [f["name"] for f in r.json()] if r.status_code == 200 else []

# =========================
# FRAMEWORK DETECTION
# =========================
def detect_frameworks(owner, repo):
    files = get_repo_files(owner, repo)
    frameworks = set()

    if "package.json" in files:
        frameworks.update(["React", "Next.js", "Express"])
    if "requirements.txt" in files or "manage.py" in files:
        frameworks.update(["Django", "Flask"])
    if "pom.xml" in files or "build.gradle" in files:
        frameworks.add("Spring")

    return list(frameworks)

# =========================
# LANGUAGE PERCENTAGES
# =========================
def lang_percentages(lang_map):
    total = sum(lang_map.values())
    return {
        k: round((v / total) * 100, 2)
        for k, v in lang_map.items()
    } if total else {}

# =========================
# MOST ACTIVE REPOS
# =========================
def get_most_active_repos(username):
    url = f"{REST_URL}/users/{username}/repos?per_page=100"
    repos = requests.get(url, headers=HEADERS).json()

    active = []
    for repo in repos:
        commits = count_user_commits(
            repo["owner"]["login"],
            repo["name"],
            username
        )
        if commits > 0:
            langs = get_repo_languages(repo["owner"]["login"], repo["name"])
            active.append({
                "name": repo["full_name"],
                "owner": repo["owner"]["login"],
                "repo": repo["name"],
                "stars": repo["stargazers_count"],
                "commits": commits,
                "languages": lang_percentages(langs),
                "frameworks": detect_frameworks(repo["owner"]["login"], repo["name"])
            })

    return sorted(active, key=lambda x: x["commits"], reverse=True)[:MAX_ACTIVE_REPOS]

# =========================
# WEIGHTED STACK
# =========================
def weighted_stack(repos):
    weights = defaultdict(float)

    for repo in repos:
        weight = repo.get("stars", 0) + repo.get("commits", 0) + 1
        for lang, percent in repo["languages"].items():
            weights[lang] += percent * weight

    total = sum(weights.values())
    return {
        k: round((v / total) * 100, 2)
        for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)
    }

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    username = input("Enter GitHub username: ").strip()

    pinned = get_pinned_repos(username)
    active = get_most_active_repos(username)

    print("\n📌 PINNED REPOS – TECH STACK\n")
    for repo in pinned:
        langs = {
            e["node"]["name"]: e["size"]
            for e in repo["languages"]["edges"]
        }
        print(f"🔹 {repo['nameWithOwner']}")
        for k, v in list(lang_percentages(langs).items())[:3]:
            print(f"   {k}: {v}%")
        print()

    print("\n🔥 MOST ACTIVE REPOS\n")
    for repo in active:
        print(f"🔹 {repo['name']} ({repo['commits']} commits)")
        for k, v in list(repo["languages"].items())[:3]:
            print(f"   {k}: {v}%")
        if repo["frameworks"]:
            print(f"   Frameworks: {', '.join(repo['frameworks'])}")
        print()

    combined = active
    weighted = weighted_stack(combined)

    print("\n📊 OVERALL WEIGHTED TECH STACK\n")
    for k, v in list(weighted.items())[:10]:
        print(f"{k}: {v}%")
