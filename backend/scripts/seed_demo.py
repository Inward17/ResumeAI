"""
Demo data for trying the app end to end: jobs in every state, ranked
candidates with scores, verification results and cached interview questions,
plus two teammates and two pending invitations in your workspace.

Everything written is tagged ``seed: true`` so it can be removed cleanly.

    cd backend
    python -m scripts.seed_demo --email you@company.com      # sign in to the app once first
    python -m scripts.seed_demo --email you@company.com --remove

Candidates and teammates are fictional (example.com addresses).
"""
import argparse
import asyncio
import random
import secrets
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from dotenv import load_dotenv

load_dotenv()

from app.database import client, db  # noqa: E402
from app.org import ensure_org  # noqa: E402

SEED = {"seed": True}
NOW = datetime.utcnow()

JOBS = [
    dict(job_title="Senior Frontend Engineer", department="Engineering", location="Pune (Hybrid)", status="Active", days=3, n=9,
         experience_level="Senior Level", salary=(2400000, 3600000),
         required_skills=["React", "TypeScript", "CSS", "Accessibility", "Testing"], preferred_skills=["Next.js", "Design systems"],
         job_description="Own the candidate-facing web app end to end: build React interfaces, keep accessibility and performance high, "
                         "and work closely with design. You will mentor two engineers and set frontend standards across teams."),
    dict(job_title="Backend Engineer (Python)", department="Engineering", location="Bengaluru", status="Active", days=8, n=8,
         experience_level="Mid Level", salary=(1800000, 2800000),
         required_skills=["Python", "FastAPI", "MongoDB", "AWS", "Docker"], preferred_skills=["Kafka"],
         job_description="Design and run the APIs behind resume parsing and verification. You'll own async job processing, data modelling "
                         "in MongoDB and the services' reliability on AWS."),
    dict(job_title="Product Designer", department="Design", location="Remote (India)", status="Active", days=15, n=6,
         experience_level="Mid Level", salary=(1500000, 2400000),
         required_skills=["Figma", "Prototyping", "User research", "Design systems"], preferred_skills=["Motion design"],
         job_description="Shape how recruiters review hundreds of candidates a day. Run research with hiring teams, prototype quickly "
                         "and evolve our design system."),
    dict(job_title="Data Analyst", department="Operations", location="Mumbai", status="Draft", days=1, n=0,
         experience_level="Entry Level", salary=(800000, 1200000),
         required_skills=["SQL", "Python", "Tableau"], preferred_skills=["dbt"],
         job_description="Build the dashboards that tell hiring teams where their funnel leaks. Draft — not open to candidates yet."),
    dict(job_title="DevOps Engineer", department="Engineering", location="Pune", status="Closed", days=62, n=5,
         experience_level="Senior Level", salary=(2200000, 3200000),
         required_skills=["Kubernetes", "Terraform", "AWS", "CI/CD"], preferred_skills=["Observability"],
         job_description="Run our infrastructure as code and keep deploys boring. This role has been filled."),
]

FIRST = ["Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Ananya", "Karan", "Isha", "Arjun", "Meera", "Kabir", "Diya", "Nikhil",
         "Tanvi", "Siddharth", "Aditi", "Varun", "Neha", "Rahul", "Pooja", "Aman", "Riya", "Harsh", "Kavya", "Yash", "Sanya",
         "Dev", "Ira"]
LAST = ["Mehta", "Sharma", "Kulkarni", "Patil", "Desai", "Iyer", "Joshi", "Nair", "Rao", "Kapoor", "Gupta", "Bose",
        "Menon", "Reddy", "Chopra", "Shah", "Pillai", "Verma"]
COMPANIES = ["Acme Corp", "Northwind Labs", "Bluefin Systems", "Kite Analytics", "Orbit Health", "Lumen Retail", "Quill Fintech"]
SCHOOLS = ["B.E. Computer Engineering, Pune University", "B.Tech Information Technology, VIT Vellore",
           "B.Des Interaction Design, NID Ahmedabad", "B.Sc Statistics, St. Xavier's College Mumbai",
           "M.Tech Computer Science, IIIT Hyderabad"]
STATUS_POOL = ["Under Review"] * 5 + ["Shortlisted"] * 3 + ["Interview"] * 2 + ["Offer", "Rejected", "Rejected"]
EXTRA_SKILLS = ["Git", "REST APIs", "Agile", "Jira", "Communication", "Node.js", "GraphQL", "Linux"]


def _person(rng, used):
    while True:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name not in used:
            used.add(name)
            return name


def _questions(job):
    s = job["required_skills"]
    return [
        {"id": 1, "question": f"Walk me through the most complex project where you used {s[0]}. What would you do differently now?",
         "tags": ["Problem framing", "Trade-offs", "Measurable outcome", s[0]]},
        {"id": 2, "question": f"How do you decide when {s[1]} is the wrong tool for a problem?",
         "tags": ["Alternatives considered", "Team constraints", "Concrete example"]},
        {"id": 3, "question": "Tell me about a time a launch went wrong. How did you find out and what changed afterwards?",
         "tags": ["Detection", "Ownership", "Root cause", "Follow-up action"]},
        {"id": 4, "question": f"Your resume mentions {s[-1]}. How would you teach it to a new teammate in their first week?",
         "tags": ["Fundamentals", "Hands-on exercise", "Common pitfalls"]},
    ]


async def seed(owner, rng):
    org_id = await ensure_org(SimpleNamespace(uid=owner["uid"], email=owner.get("email"), name=owner.get("name"), org_id=None))
    if await db.jobs.find_one({"org_id": org_id, **SEED}):
        raise SystemExit("Demo data already exists in this workspace. Run with --remove first to reseed.")

    try:
        from app.services.embedding_service import generate_embedding
    except Exception:  # embeddings only matter if you upload real resumes to a demo job
        generate_embedding = None

    used, counts = set(), {"jobs": 0, "candidates": 0}
    for spec in JOBS:
        job = {k: v for k, v in spec.items() if k not in ("days", "n", "salary")}
        job.update(SEED, org_id=org_id, owner_uid=owner["uid"], employment_type="Full-time",
                   is_active=spec["status"] == "Active", salary_min=spec["salary"][0], salary_max=spec["salary"][1],
                   posted_at=NOW - timedelta(days=spec["days"], hours=rng.randint(0, 20)))
        if generate_embedding:
            text = f"{job['job_title']} {job['job_description']} required skills: {', '.join(job['required_skills'])}"
            job["jd_embedding"] = await asyncio.to_thread(generate_embedding, text)
        job_id = str((await db.jobs.insert_one(job)).inserted_id)
        counts["jobs"] += 1

        for i in range(spec["n"]):
            name = _person(rng, used)
            cid = f"seed-{uuid.uuid4().hex[:12]}"
            handle = "example-" + name.lower().replace(" ", "-")
            strength = rng.betavariate(2.2, 1.6)  # most candidates decent, a few weak
            skill_scores = [{"skill": s, "score": round(max(0, min(10, strength * 10 + rng.uniform(-2.5, 2))), 1)}
                            for s in spec["required_skills"]]
            jd_match = round(sum(x["score"] for x in skill_scores) / len(skill_scores), 2)
            has_github = rng.random() < 0.75
            gh_state = ("verified" if rng.random() < 0.8 else "unverified") if has_github else None
            li_state = "verified" if rng.random() < 0.7 else ("unverified" if rng.random() < 0.6 else None)
            web_state = "verified" if rng.random() < 0.6 else None
            credibility = int(min(98, max(25, 35 + strength * 45 + 10 * (gh_state == "verified") + 8 * (li_state == "verified") + rng.uniform(-8, 8))))
            status = "Hired" if spec["status"] == "Closed" and i == 0 else rng.choice(STATUS_POOL)
            years = rng.randint(1, 9)
            companies = rng.sample(COMPANIES, 2)

            await db.candidates.insert_one({
                **SEED, "candidate_id": cid, "owner_uid": owner["uid"], "filename": f"{name.replace(' ', '_')}_Resume.pdf",
                "github_username": handle if has_github else None,
                "linkedin_url": f"https://www.linkedin.com/in/{handle}" if li_state else None,
                "parsed": {
                    "personal_info": {"full_name": name, "email": f"{handle.removeprefix('example-').replace('-', '.')}@example.com",
                                      "phone_number": f"+91 9{rng.randint(100000000, 999999999)}"},
                    "skills": rng.sample(spec["required_skills"], k=max(2, len(spec["required_skills"]) - rng.randint(0, 2)))
                              + rng.sample(EXTRA_SKILLS, 3),
                    "education": [f"{rng.choice(SCHOOLS)} ({NOW.year - years - 4})"],
                    "experience": [
                        f"{spec['job_title'].split('(')[0].strip()} at {companies[0]} ({NOW.year - min(years, 3)}–present) — "
                        f"led {rng.choice(['a platform rewrite', 'the onboarding redesign', 'a migration to AWS', 'search and filtering'])}",
                        f"{rng.choice(['Engineer', 'Associate', 'Intern'])} at {companies[1]} ({NOW.year - years}–{NOW.year - min(years, 3)})",
                    ],
                },
            })
            app = {
                **SEED, "candidate_id": cid, "job_id": job_id, "status": status,
                "application_date": job["posted_at"] + timedelta(hours=rng.randint(2, 24 * max(1, spec["days"]))),
                "score_details": {"overall_score": credibility, "skills_match_score": rng.randint(45, 95) if gh_state == "verified" else 0,
                                  "jd_match_score": jd_match, "skill_matches": skill_scores, "score_source": "seed"},
                "recruiter_notes": "",
            }
            if app["application_date"] > NOW:
                app["application_date"] = NOW - timedelta(hours=rng.randint(1, 12))
            if status in ("Shortlisted", "Interview", "Offer"):
                app["interview_questions"] = _questions(spec)
            await db.applications.insert_one(app)
            await db.verification_data.insert_one({**SEED, "candidateId": cid, "candidate_id": cid,
                                                   "verificationStatus": {"github": gh_state, "linkedin": li_state, "webCheck": web_state}})
            counts["candidates"] += 1

    # Two teammates and two pending invitations
    for uid, name, email, role in [("seed-member-1", "Neha Kapoor", "neha.kapoor@example.com", "admin"),
                                   ("seed-member-2", "Arjun Rao", "arjun.rao@example.com", "member")]:
        await db.org_members.update_one({"org_id": org_id, "uid": uid},
                                        {"$setOnInsert": {**SEED, "org_id": org_id, "uid": uid, "name": name, "email": email,
                                                          "role": role, "joined_at": NOW - timedelta(days=rng.randint(3, 30))}}, upsert=True)
    for email, role, days in [("hiring.manager@example.com", "member", 2), ("recruiter@example.com", "admin", 6)]:
        await db.invites.insert_one({**SEED, "org_id": org_id, "email": email, "role": role, "token": secrets.token_urlsafe(24),
                                     "status": "pending", "invited_by": owner["uid"], "invited_by_name": owner.get("name") or owner.get("email"),
                                     "created_at": NOW - timedelta(days=days), "expires_at": NOW + timedelta(days=14 - days),
                                     "email_sent": False, "email_error": "Demo invitation"})
    print(f"Seeded {counts['jobs']} jobs, {counts['candidates']} candidates, 2 teammates and 2 pending invites into workspace {org_id}.")


async def remove(owner):
    org_id = await ensure_org(SimpleNamespace(uid=owner["uid"], email=owner.get("email"), name=owner.get("name"), org_id=None))
    job_ids = [str(j["_id"]) async for j in db.jobs.find({"org_id": org_id, **SEED}, {"_id": 1})]
    # Also drops anything you uploaded into the demo jobs while testing
    apps = await db.applications.delete_many({"$or": [SEED, {"job_id": {"$in": job_ids}}]})
    results = {
        "jobs": (await db.jobs.delete_many({"org_id": org_id, **SEED})).deleted_count,
        "applications": apps.deleted_count,
        "candidates": (await db.candidates.delete_many(SEED)).deleted_count,
        "verification records": (await db.verification_data.delete_many(SEED)).deleted_count,
        "teammates": (await db.org_members.delete_many({"org_id": org_id, **SEED})).deleted_count,
        "invites": (await db.invites.delete_many({"org_id": org_id, **SEED})).deleted_count,
    }
    await db.tasks.delete_many({"job_id": {"$in": job_ids}})
    print("Removed " + ", ".join(f"{v} {k}" for k, v in results.items()) + ".")


async def main(args):
    owner = await db.users.find_one({"email": args.email})
    if not owner:
        raise SystemExit(f"No user with email {args.email}. Sign in to the app once, then re-run.")
    try:
        await (remove(owner) if args.remove else seed(owner, random.Random(args.random_seed)))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or remove demo data")
    parser.add_argument("--email", required=True, help="Email of the user who owns the demo workspace")
    parser.add_argument("--remove", action="store_true", help="Delete all demo data")
    parser.add_argument("--random-seed", type=int, default=7)
    asyncio.run(main(parser.parse_args()))
