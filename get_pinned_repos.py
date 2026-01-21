import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("❌ ERROR: GitHub token not found.")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "User-Agent": "GitHub-Profile-Bot"
}

GRAPHQL_URL = "https://api.github.com/graphql"


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
              primaryLanguage {
                name
              }
              languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
                nodes { name }
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
        print("❌ GraphQL HTTP error:", response.status_code)
        return []

    data = response.json()

    if "errors" in data:
        print("❌ GraphQL errors:", data["errors"])
        return []

    return data["data"]["user"]["pinnedItems"]["nodes"]


if __name__ == "__main__":
    username = input("Enter GitHub username: ").strip()

    pinned = get_pinned_repos(username)

    print("\n📌 PINNED REPOSITORIES\n")

    if not pinned:
        print("No pinned repositories found.")
    else:
        for repo in pinned:
            techs = [lang["name"] for lang in repo["languages"]["nodes"]]

            print(f"🔹 {repo['nameWithOwner']}")
            print(f"⭐ Stars: {repo['stargazerCount']}")
            print(f"🍴 Forks: {repo['forkCount']}")
            print(
                f"🧪 Primary Tech: "
                f"{repo['primaryLanguage']['name'] if repo['primaryLanguage'] else 'N/A'}"
            )
            print(f"🧰 Tech Stack: {', '.join(techs)}\n")
