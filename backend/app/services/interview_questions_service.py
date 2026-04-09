"""
Interview Questions Service — Generate AI-powered interview questions using Groq API.
Questions are tailored to the job description and candidate's verified profile.
"""
import json
import os
import httpx


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _build_prompt(job: dict, candidate: dict, verification: dict | None) -> str:
    """Build a rich prompt from JD + candidate context."""

    # ── Job context ──────────────────────────────────────────────────────
    job_title = job.get("job_title", "Software Engineer")
    job_desc = (job.get("job_description", "") or "")[:800]
    required_skills = ", ".join(job.get("required_skills", [])[:12])
    preferred_skills = ", ".join(job.get("preferred_skills", [])[:8])

    # ── Candidate context ────────────────────────────────────────────────
    parsed = candidate.get("parsed", {})
    personal = parsed.get("personal_info", {})
    candidate_name = personal.get("full_name", "the candidate")

    raw_skills = parsed.get("skills", "") or ""
    if isinstance(raw_skills, list):
        raw_skills = ", ".join(raw_skills[:15])
    candidate_skills = raw_skills[:300]

    experience = parsed.get("experience", []) or []
    exp_summary = ""
    if isinstance(experience, list):
        for exp in experience[:3]:
            if isinstance(exp, str):
                exp_summary += f"- {exp[:120]}\n"
            elif isinstance(exp, dict):
                exp_summary += f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')})\n"

    education = parsed.get("education", []) or []
    edu_summary = ""
    if isinstance(education, list):
        for edu in education[:2]:
            if isinstance(edu, str):
                edu_summary += f"- {edu[:100]}\n"
            elif isinstance(edu, dict):
                edu_summary += f"- {edu.get('degree', '')} from {edu.get('institution', '')}\n"

    # ── Verification context ─────────────────────────────────────────────
    verification_context = ""
    if verification:
        github = verification.get("githubData", {}) or {}
        if github:
            red_flags = github.get("redFlags", [])
            tech_combined = github.get("technologies_combined", "")
            repo_stats = github.get("repositoryStats", {}) or {}
            verification_context += f"GitHub: {repo_stats.get('total', 0)} repos ({repo_stats.get('original', 0)} original). "
            if tech_combined:
                verification_context += f"Tech stack: {tech_combined[:200]}. "
            if red_flags:
                verification_context += f"Red flags: {', '.join(red_flags[:3])}. "

        linkedin = verification.get("linkedinData", {}) or {}
        if linkedin:
            headline = linkedin.get("headline", "")
            if headline:
                verification_context += f"LinkedIn headline: {headline}. "
            positions = linkedin.get("positions", [])
            if positions:
                recent = positions[0] if positions else {}
                verification_context += f"Current role: {recent.get('title', '')} at {recent.get('companyName', '')}. "

    return f"""You are an expert technical interviewer. Generate exactly 5 interview questions for the following candidate applying to a specific job role.

JOB CONTEXT:
- Title: {job_title}
- Description: {job_desc}
- Required Skills: {required_skills}
- Preferred Skills: {preferred_skills}

CANDIDATE CONTEXT:
- Name: {candidate_name}
- Skills: {candidate_skills}
- Experience:
{exp_summary if exp_summary else '  No experience data available'}
- Education:
{edu_summary if edu_summary else '  No education data available'}
{f'- Verification: {verification_context}' if verification_context else ''}

INSTRUCTIONS:
1. Generate 5 interview questions that probe the candidate's fit for THIS specific role.
2. Mix question types: technical depth, system design, behavioral, and problem-solving.
3. Tailor questions to the candidate's background — reference their skills and experience where relevant.
4. For each question, generate 3-6 short keyword tags (2-3 words each) representing key topics the answer should cover.
5. Questions should be challenging but fair — appropriate for a senior-level technical interview.

Return ONLY a valid JSON array with exactly this structure:
[
  {{"question": "Your question here?", "tags": ["Tag1", "Tag2", "Tag3"]}},
  ...
]

Return ONLY the JSON array, no markdown, no explanation."""


async def generate_interview_questions(
    job: dict,
    candidate: dict,
    verification: dict | None = None,
) -> list[dict] | None:
    """Call Groq API to generate interview questions. Returns list of dicts or None on failure."""

    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("[InterviewQ] No GROQ_API_KEY configured")
        return None

    prompt = _build_prompt(job, candidate, verification)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a JSON-only response bot. Return valid JSON arrays only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)

        if resp.status_code != 200:
            print(f"[InterviewQ] Groq HTTP {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        # Parse JSON — handle both raw array and wrapped object
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)

        # Handle if the model wraps in an object like {"questions": [...]}
        if isinstance(parsed, dict):
            # Find the first list value
            for v in parsed.values():
                if isinstance(v, list):
                    parsed = v
                    break

        if not isinstance(parsed, list):
            print(f"[InterviewQ] Unexpected response shape: {type(parsed)}")
            return None

        # Validate structure
        questions = []
        for i, item in enumerate(parsed[:5]):
            if isinstance(item, dict) and "question" in item:
                questions.append({
                    "id": i + 1,
                    "question": item["question"],
                    "tags": item.get("tags", []),
                })

        if not questions:
            print("[InterviewQ] No valid questions parsed from response")
            return None

        print(f"[InterviewQ] ✅ Generated {len(questions)} questions via Groq")
        return questions

    except Exception as e:
        print(f"[InterviewQ] Groq call failed: {e}")
        return None
