import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

from app.database import db
from app.services.fact_checker_service import fact_check

async def main():
    # Pick a candidate
    candidate_doc = await db.candidates.find_one()
    if not candidate_doc:
        print("No candidates found.")
        return

    candidate_id = candidate_doc.get("candidateId") or candidate_doc.get("candidate_id")
    candidate_name = candidate_doc.get("parsed", {}).get("personal_info", {}).get("name", "Test Candidate")

    print(f"Using Candidate: {candidate_name} ({candidate_id})")

    # Tests for deep search & summaries
    test_queries = [
        ("Deep Code Search Demo", "Does the candidate have experience using axios or fetch APIs internally?"),
        ("Project Summary Demo", "Can you summarize their most impressive project?")
    ]

    for test_id, query in test_queries:
        print(f"\n--- Running {test_id} ---")
        print(f"Interviewer: {query}")
        try:
            res = await fact_check(candidate_id, query, candidate_name)
            print(f"\nInternal Condition Routed: {res['condition']}")
            print(f"Response:\n{res['response']}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
