import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

from app.database import db
from app.services.fact_checker_service import fact_check

async def main():
    candidate_doc = await db.candidates.find_one()
    if not candidate_doc:
        print("No candidates found in the database. Cannot run live tests.")
        return

    candidate_id = candidate_doc.get("candidateId") or candidate_doc.get("candidate_id")
    candidate_name = candidate_doc.get("parsed", {}).get("personal_info", {}).get("name", "Test Candidate")

    print(f"Using Candidate: {candidate_name} ({candidate_id})")
    
    test_queries = [
        ("TC_F_01 Basic skill check", "Does the student know React?"),
        ("TC_F_02 Multiple skills query", "Does the student know React and Node?"),
        ("TC_F_03 Unknown skill", "Does the student know Rust?"),
        ("TC_F_04 Conceptual question", "What is blockchain?"),
        ("TC_F_05 Mixed query", "Does student know React and what is React?"),
        ("TC_F_06 Project-based query", "Show projects using Angular"),
        ("TC_F_07 Resume-only skill", "Does student know Docker?"),
        ("TC_F_08 Case-insensitive input", "rEACT knowledge?"),
        ("TC_F_09 Synonym handling", "Does student know frontend frameworks?"),
        ("TC_F_10 Follow-up question", "What about backend?")
    ]

    results = []
    for test_id, query in test_queries:
        print(f"\nRunning {test_id}...")
        try:
            res = await fact_check(candidate_id, query, candidate_name)
            output = f"**{test_id}**\n*Query*: {query}\n*Condition*: {res['condition']}\n*Response*: {res['response']}\n---"
            results.append(output)
            print(output)
        except Exception as e:
            output = f"**{test_id}**\n*Query*: {query}\n*Error*: {str(e)}\n---"
            results.append(output)
            print(output)
            
    with open("live_results.md", "w") as f:
        f.write("# Live Functional Test Results\n\n")
        for r in results:
            f.write(r + "\n")

if __name__ == "__main__":
    asyncio.run(main())
