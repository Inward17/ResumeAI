import requests
import os
from dotenv import load_dotenv

# =========================
# ENV + CONFIG
# =========================
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("❌ ERROR: GITHUB_TOKEN not found")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "User-Agent": "GitHub-Tech-Stack-Bot"
}

GRAPHQL_URL = "https://api.github.com/graphql"

# =========================
# GRAPHQL QUERY
# =========================
def get_pinned_repositories_with_languages(username):
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
                  node {
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": {"login": username}},
        headers=HEADERS
    )

    if response.status_code != 200:
        print("❌ HTTP Error:", response.status_code)
        return []

    data = response.json()
    if "errors" in data:
        print("❌ GraphQL Error:", data["errors"])
        return []

    return data["data"]["user"]["pinnedItems"]["nodes"]

# =========================
# PROCESS TECH STACK
# =========================
def calculate_language_percentages(language_edges):
    total_bytes = sum(edge["size"] for edge in language_edges)
    if total_bytes == 0:
        return []

    percentages = []
    for edge in language_edges:
        lang = edge["node"]["name"]
        size = edge["size"]
        percent = round((size / total_bytes) * 100, 2)
        percentages.append((lang, percent))

    percentages.sort(key=lambda x: x[1], reverse=True)
    return percentages[:3]  # top 3 languages

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    username = input("Enter GitHub username: ").strip()

    repos = get_pinned_repositories_with_languages(username)

    print("\n📌 PINNED REPOSITORIES – TECH STACK BREAKDOWN\n")

    if not repos:
        print("No pinned repositories found.")
        exit(0)

    for repo in repos:
        print(f"🔹 {repo['nameWithOwner']}")
        print(f"⭐ Stars: {repo['stargazerCount']}")
        print(f"🍴 Forks: {repo['forkCount']}")

        lang_edges = repo["languages"]["edges"]
        tech_stack = calculate_language_percentages(lang_edges)

        if not tech_stack:
            print("🧪 Tech Stack: No language data\n")
            continue

        print("🧪 Tech Stack (Top 3):")
        for lang, percent in tech_stack:
            print(f"   - {lang}: {percent}%")

        print()
