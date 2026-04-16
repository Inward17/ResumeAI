"""
Fact Checker Service — AI-powered claim verification for interviewers.

Orchestration layer that classifies an interviewer's prompt into one of
four conditions and routes to the appropriate verification logic:

  Condition 1 — General Q&A:  Generate follow-up questions from resume data.
  Condition 2 — Tech Stack:   Verify a tech-stack claim via GitHub repos.
  Condition 3 — Project:      Verify a project claim via GitHub repos.
  Condition 4 — Authenticity:  Check if a GitHub project is truly built
                               by the candidate (fork / commit analysis).

Cost-optimisation: DB-stored verification data is checked FIRST.
External GitHub API calls are only made as a fallback.
"""

import json
import os
import re
import logging
from typing import Any, Dict, Optional, List

import httpx

from app.database import db


def _normalize(text: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, strip noise words, remove separators."""
    text = text.lower().strip()
    # Remove common noise words
    for word in ("project", "app", "application", "system", "tool", "based", "the", "a", "an"):
        text = re.sub(rf'\b{word}\b', '', text)
    # Replace hyphens, underscores, dots with spaces, collapse whitespace
    text = re.sub(r'[-_.]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _fuzzy_match(query: str, target: str) -> bool:
    """Check if query matches target using normalized substring + token overlap."""
    nq = _normalize(query)
    nt = _normalize(target)
    if not nq or not nt:
        return False
    # Direct substring match
    if nq in nt or nt in nq:
        return True
    # Token overlap: if all significant query tokens appear in target
    q_tokens = set(nq.split())
    t_tokens = set(nt.split())
    if q_tokens and q_tokens.issubset(t_tokens):
        return True
    return False

logger = logging.getLogger(__name__)

# ── Groq config ─────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# ═════════════════════════════════════════════════════════════════════
# 1. ROUTER — Classify the interviewer's prompt
# ═════════════════════════════════════════════════════════════════════

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a hiring platform's AI Fact Checker.
Given the interviewer's message, classify it into EXACTLY ONE of these categories:

1. "general_qa"   — The interviewer wants follow-up questions, general advice, or discussion about the candidate.
2. "verify_tech"  — The interviewer wants to verify whether a candidate actually knows a specific technology/framework/language that may NOT be on their resume.
3. "verify_project" — The interviewer wants to verify whether a candidate has actually built or worked on a specific project (by name or description).
4. "verify_authenticity" — The interviewer wants to check if a project on the candidate's GitHub is genuinely built by them (not forked/copied).

Return ONLY a JSON object with these fields:
{
  "condition": "<one of: general_qa, verify_tech, verify_project, verify_authenticity>",
  "extracted_query": "<the specific tech/project/claim extracted from the message, or the full message for general_qa>"
}

Return ONLY the JSON, no markdown, no explanation."""


async def _call_groq(system: str, user: str, temperature: float = 0.3, response_format: dict = None) -> Optional[str]:
    """Make a single Groq chat completion call. Returns the assistant text or None."""
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.error("[FactChecker] No GROQ_API_KEY configured")
        return None

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": 2000,
    }
    if response_format:
        payload["response_format"] = response_format
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("[FactChecker] Groq HTTP %d: %s", resp.status_code, resp.text[:300])
            return None
        data = resp.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception as e:
        logger.error("[FactChecker] Groq call failed: %s", e)
        return None


async def _classify_intent(user_message: str, candidate_name: str) -> Dict[str, str]:
    """Route the interviewer's prompt to one of the 4 conditions."""
    if not user_message or not user_message.strip():
        return {"condition": "general_qa", "extracted_query": ""}

    user_prompt = f"Candidate name: {candidate_name}\nInterviewer message: {user_message}"
    raw = await _call_groq(ROUTER_SYSTEM_PROMPT, user_prompt, response_format={"type": "json_object"})
    if not raw:
        return {"condition": "general_qa", "extracted_query": user_message}

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
        condition = parsed.get("condition", "general_qa")
        if condition not in ("general_qa", "verify_tech", "verify_project", "verify_authenticity"):
            condition = "general_qa"
        return {
            "condition": condition,
            "extracted_query": parsed.get("extracted_query", user_message),
        }
    except Exception as e:
        logger.warning(f"Failed to parse classification JSON: {e} | Raw: {raw}")
        return {"condition": "general_qa", "extracted_query": user_message}


# ═════════════════════════════════════════════════════════════════════
# 2. DATA FETCHER — Get candidate + verification data from MongoDB
# ═════════════════════════════════════════════════════════════════════

async def _fetch_candidate_context(candidate_id: str) -> Dict[str, Any]:
    """Load candidate resume data and verification data from MongoDB."""
    candidate_doc = await db.candidates.find_one(
        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
    )
    verification_doc = await db.verification_data.find_one(
        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
    )
    return {
        "candidate": candidate_doc or {},
        "verification": verification_doc or {},
    }


def _get_github_repos(verification: dict) -> List[Dict[str, Any]]:
    """Extract repository list from stored githubData."""
    github_data = verification.get("githubData", {}) or {}
    # The v2 pipeline stores repo details in cloneAnalysis.repoDetails
    repos = github_data.get("repositories", [])
    if not repos:
        # Try to extract from cloneAnalysis
        clone = github_data.get("cloneAnalysis", {}) or {}
        repos = clone.get("repoDetails", [])
    return repos


def _get_github_username(candidate: dict, verification: dict) -> Optional[str]:
    """Extract GitHub username from candidate or verification data."""
    # From verification data
    github_data = verification.get("githubData", {}) or {}
    username = github_data.get("username")
    if username:
        return username

    # From candidate parsed resume
    parsed = candidate.get("parsed", {}) or {}
    personal = parsed.get("personal_info", {}) or {}
    github_url = personal.get("github", "")
    if github_url:
        return github_url.rstrip("/").split("/")[-1]

    return None


# ═════════════════════════════════════════════════════════════════════
# 3. CONDITION HANDLERS
# ═════════════════════════════════════════════════════════════════════

# ── Condition 1: General Q&A ────────────────────────────────────────

async def _handle_general_qa(
    query: str,
    candidate: dict,
    verification: dict,
    candidate_name: str,
) -> str:
    """Use Groq to answer a general question about the candidate."""
    parsed = candidate.get("parsed", {}) or {}
    skills = parsed.get("skills", "N/A")
    if isinstance(skills, list):
        skills = ", ".join(skills[:15])
    experience = parsed.get("experience", [])
    exp_text = ""
    if isinstance(experience, list):
        for exp in experience[:3]:
            if isinstance(exp, str):
                exp_text += f"- {exp[:120]}\n"
            elif isinstance(exp, dict):
                exp_text += f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')})\n"

    projects = parsed.get("projects", [])
    proj_text = ""
    if isinstance(projects, list):
        for p in projects[:5]:
            if isinstance(p, dict):
                proj_text += f"- {p.get('name', 'Unnamed')}: {p.get('description', '')[:100]}\n"
            elif isinstance(p, str):
                proj_text += f"- {p[:100]}\n"

    # Include GitHub score if available
    github_data = verification.get("githubData", {}) or {}
    github_score = github_data.get("score100", "N/A")
    red_flags = github_data.get("redFlags", [])

    system = """You are an AI assistant helping an interviewer during a live technical interview.
You have access to the candidate's resume and verification data.
If asked to summarize a project, provide a clean, bulleted breakdown of what the project is, its tech stack, and any related metrics.
Provide helpful, concise, and actionable responses.
Be direct and professional. Keep the response under 150 words."""

    user_msg = f"""Candidate: {candidate_name}
Skills: {skills}
Experience:
{exp_text if exp_text else 'No experience data'}
Projects:
{proj_text if proj_text else 'No project data'}
GitHub Score: {github_score}/100
Red Flags: {', '.join(red_flags) if red_flags else 'None'}

Interviewer's question: {query}"""

    response = await _call_groq(system, user_msg, temperature=0.5)
    return response or "I'm sorry, I couldn't process that request right now. Please try again."


# ── Condition 2: Verify Tech Stack ──────────────────────────────────

async def _handle_verify_tech(
    tech_query: str,
    candidate: dict,
    verification: dict,
    candidate_name: str,
) -> str:
    """
    Check if the candidate has experience with a specific technology.
    Step 1: Check resume skills.
    Step 2: Check stored GitHub verification data (technologies_combined, repo languages).
    Step 3: Fallback — live GitHub API search.
    """
    parsed = candidate.get("parsed", {}) or {}
    tech_lower = tech_query.lower().strip()

    # ── Step 1: Check resume ────────────────────────────────────────
    skills_raw = parsed.get("skills", "")
    if isinstance(skills_raw, list):
        skills_str = ", ".join(skills_raw)
    else:
        skills_str = str(skills_raw)

    resume_has_tech = tech_lower in skills_str.lower()

    # ── Step 2: Check stored GitHub data ────────────────────────────
    github_data = verification.get("githubData", {}) or {}
    tech_combined = (github_data.get("technologies_combined", "") or "").lower()
    github_has_tech = tech_lower in tech_combined

    # Also check individual repo languages from repoDetails / cloneAnalysis
    clone_details = (github_data.get("cloneAnalysis", {}) or {}).get("repoDetails", [])
    matching_repos = []
    for repo in clone_details:
        repo_name = repo.get("repoName", repo.get("name", ""))
        lang = (repo.get("language", "") or "").lower()
        desc = (repo.get("description", "") or "").lower()
        topics = [t.lower() for t in repo.get("topics", [])]
        if tech_lower in lang or tech_lower in desc or tech_lower in " ".join(topics) or _fuzzy_match(tech_query, repo_name):
            matching_repos.append(repo_name)

    # ── Step 3: Fallback — live GitHub API ──────────────────────────
    username = _get_github_username(candidate, verification)
    live_repos_found = []
    deep_code_matches = []
    if not github_has_tech and not matching_repos and username:
        try:
            from app.services.github_services_v2.github_client import GitHubClient
            client = GitHubClient()
            try:
                all_repos = await client.get_user_repos(username)
                for repo in all_repos:
                    lang = (repo.get("language", "") or "").lower()
                    desc = (repo.get("description", "") or "").lower()
                    rname = repo.get("name", "") or ""
                    topics = [t.lower() for t in repo.get("topics", [])]
                    if tech_lower in lang or tech_lower in desc or tech_lower in " ".join(topics) or _fuzzy_match(tech_query, rname):
                        live_repos_found.append(rname or "unknown")
                
                # Deep code search fallback if no top-level repo matched
                if not live_repos_found:
                    code_hits = await client.search_user_code(username, tech_query, limit=3)
                    for hit in code_hits:
                        deep_code_matches.append(f"{hit['repo_name']}/{hit['file_name']}")
            finally:
                await client.close()
            print(f"[FactChecker] Live GitHub check for '{tech_query}': found {len(live_repos_found)} repos, {len(deep_code_matches)} files")
        except Exception as e:
            logger.warning("[FactChecker] Live GitHub fallback failed: %s", e)

    # ── Build response via Groq ─────────────────────────────────────
    evidence_parts = []
    if resume_has_tech:
        evidence_parts.append(f"✅ **Resume:** '{tech_query}' IS listed in the candidate's skills.")
    else:
        evidence_parts.append(f"⚠️ **Resume:** '{tech_query}' is NOT listed in the candidate's resume skills.")

    if github_has_tech or matching_repos:
        repos_list = ", ".join(matching_repos[:5]) if matching_repos else "detected in tech stack"
        evidence_parts.append(f"✅ **GitHub (cached):** Found evidence of '{tech_query}' — {repos_list}.")
    elif live_repos_found:
        evidence_parts.append(f"✅ **GitHub (live):** Found {len(live_repos_found)} repos using '{tech_query}': {', '.join(live_repos_found[:5])}.")
    elif deep_code_matches:
        evidence_parts.append(f"✅ **GitHub Code Search**: Found '{tech_query}' actively used inside repository files: {', '.join(deep_code_matches)}.")
    else:
        evidence_parts.append(f"❌ **GitHub:** No repositories or active code found using '{tech_query}'.")

    evidence = "\n".join(evidence_parts)

    system = """You are an AI fact-checker verifying a candidate's tech stack claim during a live interview.
Based on the evidence provided, give a clear verdict and recommendation to the interviewer.
Be direct, concise (under 120 words), and helpful. Use the evidence to justify your answer."""

    user_msg = f"""Candidate: {candidate_name}
Claim: Candidate says they know "{tech_query}"

Evidence:
{evidence}

Provide a clear verdict: Does the evidence support this claim?"""

    response = await _call_groq(system, user_msg, temperature=0.3)
    return response or f"Evidence gathered:\n{evidence}"


# ── Condition 3: Verify Project ─────────────────────────────────────

async def _handle_verify_project(
    project_query: str,
    candidate: dict,
    verification: dict,
    candidate_name: str,
) -> str:
    """
    Check if a claimed project actually exists on the candidate's GitHub.
    Step 1: Check resume projects.
    Step 2: Check stored GitHub resumeVerification matches.
    Step 3: Fallback — live GitHub API search for matching repo name.
    """
    parsed = candidate.get("parsed", {}) or {}

    # ── Step 1: Check resume ────────────────────────────────────────
    resume_projects = parsed.get("projects", []) or []
    resume_match = None
    for p in resume_projects:
        if isinstance(p, dict):
            pname = p.get("name", "") or ""
            pdesc = p.get("description", "") or ""
            if _fuzzy_match(project_query, pname) or _fuzzy_match(project_query, pdesc):
                resume_match = p.get("name", project_query)
                break
        elif isinstance(p, str) and _fuzzy_match(project_query, p):
            resume_match = p
            break

    # ── Step 2: Check stored GitHub verification ────────────────────
    github_data = verification.get("githubData", {}) or {}
    resume_verification = github_data.get("resumeVerification", {}) or {}
    matches = resume_verification.get("matches", []) or []

    github_match = None
    for m in matches:
        if _fuzzy_match(project_query, m.get("projectName", "") or "") or \
           _fuzzy_match(project_query, m.get("repoName", "") or ""):
            github_match = m
            break

    # ── Step 3: Fallback — live GitHub API ──────────────────────────
    username = _get_github_username(candidate, verification)
    live_match = None
    if not github_match and username:
        try:
            from app.services.github_services_v2.github_client import GitHubClient
            client = GitHubClient()
            try:
                all_repos = await client.get_user_repos(username)
                for repo in all_repos:
                    repo_name = repo.get("name", "") or ""
                    repo_desc = repo.get("description", "") or ""
                    if _fuzzy_match(project_query, repo_name) or _fuzzy_match(project_query, repo_desc):
                        live_match = {
                            "name": repo.get("name"),
                            "description": repo.get("description", ""),
                            "language": repo.get("language", ""),
                            "stars": repo.get("stargazers_count", 0),
                            "fork": repo.get("fork", False),
                            "url": repo.get("html_url", ""),
                        }
                        break
            finally:
                await client.close()
            print(f"[FactChecker] Live GitHub project search for '{project_query}': {'found' if live_match else 'not found'}")
        except Exception as e:
            logger.warning("[FactChecker] Live GitHub project search failed: %s", e)

    # ── Build evidence ──────────────────────────────────────────────
    evidence_parts = []
    if resume_match:
        evidence_parts.append(f"✅ **Resume:** Project '{resume_match}' IS listed on the resume.")
    else:
        evidence_parts.append(f"⚠️ **Resume:** No project matching '{project_query}' found on the resume.")

    if github_match:
        evidence_parts.append(
            f"✅ **GitHub (cached):** A match was found! Repo '{github_match.get('repoName', '')}' matches the query "
            f"(similarity: {github_match.get('similarity', 'N/A')}, "
            f"match rating: {github_match.get('matchStrength', 'N/A')})."
        )
    elif live_match:
        fork_note = " ⚠️ (NOTE: THIS REPOSITORY IS A FORK, NOT ORIGINAL)" if live_match["fork"] else "✅ (This is an original, non-forked repository)"
        evidence_parts.append(
            f"✅ **GitHub (live):** A match was found! The repository '{live_match['name']}' matches the project '{project_query}'.\n"
            f"   - {fork_note}\n"
            f"   - Language: {live_match['language'] or 'Unknown'}\n"
            f"   - Stars: {live_match['stars']}"
        )
    else:
        evidence_parts.append(f"❌ **GitHub:** No matching repository found for '{project_query}'.")

    evidence = "\n".join(evidence_parts)

    system = """You are an AI fact-checker verifying a candidate's project claim during a live interview.
If the interviewer asks for a summary of a project, provide a clean, bulleted breakdown of the repository's purpose, tech stack, and originality using the evidence.
Based on the evidence provided, give a clear verdict and recommendation to the interviewer.
Be direct, concise (under 120 words), and helpful."""

    user_msg = f"""Candidate: {candidate_name}
Claim: Candidate says they built a project called "{project_query}"

Evidence:
{evidence}

Provide a clear verdict: Does the evidence support this claim? If the repository is a fork, emphasize that."""

    response = await _call_groq(system, user_msg, temperature=0.3)
    return response or f"Evidence gathered:\n{evidence}"


# ── Condition 4: Verify Authenticity ────────────────────────────────

async def _handle_verify_authenticity(
    project_query: str,
    candidate: dict,
    verification: dict,
    candidate_name: str,
) -> str:
    """
    Check if a project on GitHub is genuinely built by the candidate.
    Step 1: Check stored clone analysis / behavioral analysis.
    Step 2: Fallback — live GitHub check (fork status, commits by user).
    """
    github_data = verification.get("githubData", {}) or {}

    # ── Step 1: Check stored analysis ───────────────────────────────
    clone_analysis = github_data.get("cloneAnalysis", {}) or {}
    behavioral = github_data.get("behavioralAnalysis", {}) or {}
    repo_stats = github_data.get("repositoryStats", {}) or {}

    # Overall signals
    code_verdict = clone_analysis.get("codeVerdict", "UNKNOWN")
    readme_verdict = clone_analysis.get("readmeVerdict", "UNKNOWN")
    code_originality = clone_analysis.get("codeOriginality", None)
    behavioral_auth = behavioral.get("behavioralAuthenticity", None)
    commit_consistency = behavioral.get("commitConsistency", None)
    burst_risk = behavioral.get("burstRisk", None)
    overall_score = github_data.get("score100", None)
    red_flags = github_data.get("redFlags", []) or []

    has_stored_analysis = any(v is not None for v in [code_originality, behavioral_auth, overall_score])

    # ── Step 2: Fallback — live GitHub check ────────────────────────
    username = _get_github_username(candidate, verification)
    live_evidence = None
    if not has_stored_analysis and username:
        try:
            from app.services.github_services_v2.github_client import GitHubClient
            project_lower = project_query.lower().strip()
            client = GitHubClient()
            try:
                all_repos = await client.get_user_repos(username)
                target_repo = None
                for repo in all_repos:
                    if project_lower in (repo.get("name", "") or "").lower():
                        target_repo = repo
                        break

                if target_repo:
                    repo_name = target_repo["name"]
                    is_fork = target_repo.get("fork", False)
                    # Fetch commits by this user
                    commits = await client.get_repo_commits(username, repo_name, username, max_commits=20)
                    live_evidence = {
                        "repo_name": repo_name,
                        "is_fork": is_fork,
                        "commit_count": len(commits),
                        "language": target_repo.get("language", ""),
                        "stars": target_repo.get("stargazers_count", 0),
                        "size_kb": target_repo.get("size", 0),
                    }
            finally:
                await client.close()
            print(f"[FactChecker] Live authenticity check for '{project_query}': {live_evidence}")
        except Exception as e:
            logger.warning("[FactChecker] Live authenticity check failed: %s", e)

    # ── Build evidence ──────────────────────────────────────────────
    evidence_parts = []

    if has_stored_analysis:
        evidence_parts.append(f"📊 **GitHub Verification Score:** {overall_score}/100")
        if code_originality is not None:
            evidence_parts.append(f"🔍 **Code Originality:** {round(code_originality * 100, 1)}% — Verdict: {code_verdict}")
        if readme_verdict != "UNKNOWN":
            evidence_parts.append(f"📝 **README Verdict:** {readme_verdict}")
        if behavioral_auth is not None:
            evidence_parts.append(f"🧠 **Behavioral Authenticity:** {round(behavioral_auth * 100, 1)}%")
        if commit_consistency is not None:
            evidence_parts.append(f"📈 **Commit Consistency:** {round(commit_consistency * 100, 1)}%")
        if burst_risk is not None:
            risk_label = "HIGH" if burst_risk > 0.7 else "MODERATE" if burst_risk > 0.4 else "LOW"
            evidence_parts.append(f"⚡ **Burst Risk (cramming):** {risk_label} ({round(burst_risk * 100, 1)}%)")
        if red_flags:
            evidence_parts.append(f"🚩 **Red Flags:** {', '.join(red_flags)}")
        evidence_parts.append(f"📦 **Repo Stats:** {repo_stats.get('total', '?')} total, {repo_stats.get('original', '?')} original, {repo_stats.get('forked', '?')} forked")
    elif live_evidence:
        fork_status = "⚠️ YES — this is a FORK" if live_evidence["is_fork"] else "✅ NO — this is an original repo"
        evidence_parts.append(f"📦 **Repository:** {live_evidence['repo_name']}")
        evidence_parts.append(f"🔀 **Is Fork?** {fork_status}")
        evidence_parts.append(f"📝 **Commits by candidate:** {live_evidence['commit_count']}")
        evidence_parts.append(f"💻 **Language:** {live_evidence['language'] or 'N/A'}")
        evidence_parts.append(f"⭐ **Stars:** {live_evidence['stars']}")
        if live_evidence["commit_count"] < 5:
            evidence_parts.append("🚩 **Warning:** Very few commits by the candidate — may indicate copied work.")
    else:
        evidence_parts.append("❌ No analysis data available and could not perform live verification.")

    evidence = "\n".join(evidence_parts)

    system = """You are an AI fact-checker verifying whether a candidate genuinely built a project during a live interview.
Based on the evidence provided (clone analysis, behavioral patterns, commit history, fork status), give a clear authenticity verdict.
Be direct, concise (under 150 words), and helpful. Highlight any red flags clearly."""

    user_msg = f"""Candidate: {candidate_name}
Query: Is the project "{project_query}" genuinely built by this candidate?

Evidence:
{evidence}

Provide a clear authenticity verdict."""

    response = await _call_groq(system, user_msg, temperature=0.3)
    return response or f"Authenticity Evidence:\n{evidence}"


# ═════════════════════════════════════════════════════════════════════
# 4. PUBLIC API — Main entrypoint
# ═════════════════════════════════════════════════════════════════════

async def fact_check(candidate_id: str, user_message: str, candidate_name: str = "the candidate") -> Dict[str, Any]:
    """
    Main entrypoint for the Fact Checker service.

    Parameters
    ----------
    candidate_id : str
        The candidate's ID in MongoDB.
    user_message : str
        The interviewer's free-form question or claim.
    candidate_name : str
        Display name for the candidate.

    Returns
    -------
    dict
        {"response": str, "condition": str, "extracted_query": str}
    """
    print(f"[FactChecker] Received: candidate={candidate_id}, msg='{user_message[:80]}...'")
    
    user_message = user_message.strip()
    words = user_message.split()
    if len(words) > 500:
        user_message = " ".join(words[:500]) + "..."

    # Step 1: Classify intent
    intent = await _classify_intent(user_message, candidate_name)
    condition = intent["condition"]
    extracted = intent["extracted_query"]
    print(f"[FactChecker] Routing → {condition} | extracted='{extracted[:60]}'")

    # Step 2: Fetch candidate context from DB
    ctx = await _fetch_candidate_context(candidate_id)
    candidate = ctx["candidate"]
    verification = ctx["verification"]

    # Step 3: Route to the correct handler
    if condition == "verify_tech":
        response = await _handle_verify_tech(extracted, candidate, verification, candidate_name)
    elif condition == "verify_project":
        response = await _handle_verify_project(extracted, candidate, verification, candidate_name)
    elif condition == "verify_authenticity":
        response = await _handle_verify_authenticity(extracted, candidate, verification, candidate_name)
    else:
        response = await _handle_general_qa(extracted, candidate, verification, candidate_name)

    print(f"[FactChecker] ✅ Response generated ({len(response)} chars) for condition={condition}")

    return {
        "response": response,
        "condition": condition,
        "extracted_query": extracted,
    }
