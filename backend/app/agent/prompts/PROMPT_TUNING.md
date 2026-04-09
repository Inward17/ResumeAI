# Prompt Tuning Guide: ResumeAI Agent Layer

This document outlines the standard operating procedures for editing, tuning, and evaluating the LLM instructions inside the Agent Orchestration loop (`backend/app/agent/prompts/`).

## 1. Philosophy
The Agent Layer is designed to be "Prompt-Driven." The `planning.txt` file is essentially the "source code" of the reasoning engine. When the system makes a "bad call" (e.g., spending tokens to scrape GitHub for a Data Entry Candidate), we do not add complex IF statements in Python. We tune the prompt.

## 2. Core Prompt Library
- `planning.txt`: The main orchestrator prompt. It takes undecided verification signals, the job metadata, and outputs JSON.
- `evaluation.txt`: A QA/Diagnostic prompt that runs post-execution to ascertain if the tools succeeded or failed contextually.

## 3. How to Fix Agent Drift
If the agent behaves erratically:
1. Locate the exact run trace in `agent_runs` (MongoDB).
2. Look at the `actions_taken` and `plan_source` fields.
3. If `plan_source` == `llm_fallback`, the JSON parsing failed. You need to stiffen the JSON formatting rules in `planning.txt` by explicitly stating `Do not add markdown formatting or conversational text.`
4. If it successfully parsed but chose the wrong signals, inspect the `{job_title}` + `{required_skills}` passed to the context. Update section "CRITICAL RULES & EDGE CASES" in the prompt to directly address the anomaly.

## 4. Editing Edge Cases
When adding a new edge case, use this exact syntax inside `planning.txt` to keep it contextually aware:
`N. **[Title]:** [Condition], MUST [Action "verify" | "skip"] for [Signal].`
*Example*: `5. Non-Technical Roles: If the role is non-technical, heavily downweight "github" and "skip" unless explicitly defined.`

## 5. Deployment
Prompts are loaded into memory dynamically per run (since they are disk-read upon module invocation, but wait, currently in `planner.py` they are loaded once at import time `with open(_PROMPT_PATH) as _f`). To apply changes to the prompt files, you currently MUST restart the FastAPI server (`app.main`).

## 6. The 5 Core Monitored Edge Cases
1. Technical Roles
2. Re-Applications (Cache Hits)
3. No-GitHub Compensation
4. Low Confidence
5. Soft-Skill Verification (Non-Tech)
