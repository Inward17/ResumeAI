"""
Assign jobs created before authentication existed to a user.

Jobs are now private to the user who created them (``owner_uid``). Jobs from
before that change have no owner and are hidden from everyone until assigned:

    cd backend
    python -m scripts.assign_job_owner --email recruiter@company.com   # user must have signed in once
    python -m scripts.assign_job_owner --uid <firebase-uid>
    python -m scripts.assign_job_owner --email ... --dry-run
"""
import argparse
import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.database import client, db  # noqa: E402

UNOWNED = {"$or": [{"owner_uid": {"$exists": False}}, {"owner_uid": None}]}


async def main(args):
    uid = args.uid
    if args.email:
        user = await db.users.find_one({"email": args.email})
        if not user:
            raise SystemExit(f"No user with email {args.email}. Sign in to the app once, then re-run.")
        uid = user["uid"]

    jobs = await db.jobs.find(UNOWNED, {"job_title": 1}).to_list(length=None)
    print(f"{len(jobs)} job(s) without an owner")
    for job in jobs:
        print(f"  {job['_id']}  {job.get('job_title', '')}")

    if jobs and not args.dry_run:
        job_ids = [str(job["_id"]) for job in jobs]
        await db.jobs.update_many(UNOWNED, {"$set": {"owner_uid": uid}})
        # Keep candidate de-duplication working for the migrated candidates
        candidate_ids = await db.applications.distinct("candidate_id", {"job_id": {"$in": job_ids}})
        await db.candidates.update_many(
            {"candidate_id": {"$in": candidate_ids}, **UNOWNED}, {"$set": {"owner_uid": uid}}
        )
        print(f"Assigned {len(jobs)} job(s) and {len(candidate_ids)} candidate(s) to {uid}")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--uid")
    who.add_argument("--email")
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args()))
