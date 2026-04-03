"""
Agent Loop — Section 6.2 + Section 11 (Observability)

The main orchestration loop.  One call to ``run()`` executes a full
agent run for a single candidate × job pair:

    SessionMemory init
        → context_builder.build
        → rule_engine.apply_rules
        → scoring_engine.score_signals / apply_scores
        → planner.call_planner  (only when needs_llm is non-empty)
        → executor.execute_plan
        → memory.update
        → completion check
    repeat up to MAX_STEPS or TOTAL_TIMEOUT_SEC

After the loop, an observability document is written to ``agent_runs``
and ``memory.get_summary()`` is returned.
"""

import time
import uuid
import logging
from datetime import datetime

from app.database import db, agent_runs_col
from app.agent.config.agent_config import MAX_STEPS, TOTAL_TIMEOUT_SEC
from app.agent.memory.session_memory import SessionMemory
from app.agent.decision import context_builder
from app.agent.decision.rule_engine import apply_rules
from app.agent.decision.scoring_engine import score_signals, apply_scores
from app.agent.core.planner import call_planner
from app.agent.core.executor import execute_plan
from app.agent.core.verifier import check_completion

logger = logging.getLogger(__name__)


async def run(candidate_id: str, job_id: str) -> dict:
    """
    Execute the full agent verification loop for one candidate.

    Returns
    -------
    dict
        Summary produced by ``SessionMemory.get_summary()``.
    """
    run_id = str(uuid.uuid4())
    memory = SessionMemory(candidate_id)
    step = 0
    start = time.monotonic()

    logger.info(
        "Agent run %s started for candidate=%s job=%s",
        run_id, candidate_id, job_id,
    )

    try:
        while step < MAX_STEPS:
            # ── Hard timeout guard ──────────────────────────────────
            elapsed_sec = time.monotonic() - start
            if elapsed_sec >= TOTAL_TIMEOUT_SEC:
                logger.warning(
                    "Agent run %s hit TOTAL_TIMEOUT_SEC (%ds) at step %d",
                    run_id, TOTAL_TIMEOUT_SEC, step,
                )
                break

            # ── 1. Build context from MongoDB ───────────────────────
            context = await context_builder.build(candidate_id, job_id, memory)

            # ── 2. Rule engine — deterministic decisions ────────────
            plan, undecided = apply_rules(context)
            print(f"[AGENT] Step {step}: rule_engine → actions={plan.actions}, skip={plan.skip}, undecided={undecided}, reasoning={plan.reasoning}")

            # ── 3. Scoring engine — priority formula ────────────────
            if undecided:
                scores = score_signals(undecided, context)
                plan, needs_llm = apply_scores(scores, plan)
                print(f"[AGENT] Step {step}: scoring → scores={scores}, needs_llm={needs_llm}, final_actions={plan.actions}, final_skip={plan.skip}")
            else:
                scores = {}
                needs_llm = []

            # ── 4. LLM planner — ambiguity resolution (if needed) ──
            if needs_llm:
                llm_plan = await call_planner(needs_llm, scores, context)
                plan.actions.extend(llm_plan.actions)
                plan.skip.extend(llm_plan.skip)
                plan.reasoning.update(llm_plan.reasoning)
                plan.source = llm_plan.source
                print(f"[AGENT] Step {step}: LLM planner → added actions={llm_plan.actions}, added skip={llm_plan.skip}")

            # ── 5. Nothing left to do? Exit loop ───────────────────
            if not plan.actions:
                print(f"[AGENT] Step {step}: no actions remaining, exiting loop")
                logger.info("Agent run %s — no actions remaining, exiting loop", run_id)
                break

            # ── 6. Execute planned tools concurrently ───────────────
            print(f"[AGENT] Step {step}: executing tools: {plan.actions}")
            results = await execute_plan(plan, context)
            for name, res in results.items():
                print(f"[AGENT] Step {step}: tool '{name}' → status={res.status}, reason={res.reason}, duration={res.duration_ms}ms")

            # ── 7. Update memory ────────────────────────────────────
            memory.update(plan, results)

            step += 1

            # ── 8. Completion check ─────────────────────────────────
            if check_completion(context, results):
                logger.info("Agent run %s — completion check passed at step %d", run_id, step)
                break

    except Exception as e:
        logger.exception("Agent run %s failed with error: %s", run_id, e)

    # ── Observability: write run document to agent_runs_col ──────────
    elapsed_ms = int((time.monotonic() - start) * 1000)
    try:
        await agent_runs_col.insert_one({
            "run_id":          run_id,
            "candidate_id":    candidate_id,
            "job_id":          job_id,
            "timestamp":       datetime.utcnow(),
            "plan_source":     memory.plan_source,
            "actions_taken":   memory.action_history,
            "signals_skipped": memory.skipped,
            "run_duration_ms": elapsed_ms,
        })
    except Exception as e:
        logger.error("Failed to write agent_runs observability doc: %s", e)

    # ── Write merged results back to verification_data ──────────────
    try:
        all_results = memory.get_all_results()
        update_fields = {}
        for signal_name, tool_result in all_results.items():
            if tool_result.status == "completed" and tool_result.data:
                # Map signal names to verification_data keys
                key_map = {
                    "github":     "githubData",
                    "linkedin":   "linkedinData",
                    "web_search": "webSearchData",
                }
                db_key = key_map.get(signal_name)
                if db_key:
                    # Inject last_verified into the data dict itself before storing.
                    # MongoDB rejects $set on both 'linkedinData' and 'linkedinData.last_verified'
                    # simultaneously (path conflict), so we merge the timestamp into the object.
                    data_with_ts = dict(tool_result.data) if isinstance(tool_result.data, dict) else {"raw": tool_result.data}
                    data_with_ts["last_verified"] = datetime.utcnow()
                    update_fields[db_key] = data_with_ts

        if update_fields:
            # Fix 1: Always include candidateId so the doc can be found later
            update_fields["candidateId"] = candidate_id

            import os
            # Use separate collection when in Dual Run mode to avoid breaking legacy pipeline data
            dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
            target_collection_name = "verification_data_agent" if dual_run else "verification_data"
            target_collection = db[target_collection_name]

            # Read existing doc so we can merge scores for signals that weren't re-run
            existing_doc = await target_collection.find_one(
                {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
            ) or {}

            # Merge: for each signal, use current run data if available, else existing DB data
            gh_data = update_fields.get("githubData", existing_doc.get("githubData", {}))
            li_data = update_fields.get("linkedinData", existing_doc.get("linkedinData", {}))
            ws_data = update_fields.get("webSearchData", existing_doc.get("webSearchData", {}))

            # Fix 2: Check for actual success, not just presence of data key
            existing_status = existing_doc.get("verificationStatus", {})
            v_status = {
                "linkedin": ("verified" if (li_data and not li_data.get("error")) else ("unverified" if li_data else existing_status.get("linkedin", "pending"))),
                "github":   ("verified" if (gh_data and (gh_data.get("success", False) or gh_data.get("score100", 0) > 0)) else ("unverified" if gh_data else existing_status.get("github", "pending"))),
                "webCheck": ("verified" if (ws_data and not ws_data.get("error")) else ("unverified" if ws_data else existing_status.get("webCheck", "pending"))),
            }
            update_fields["verificationStatus"] = v_status

            # Calculate match scores using merged data (current run + existing DB)
            github_data = gh_data
            linkedin_data = li_data
            web_search_data = ws_data

            experience_match = 0
            if web_search_data and isinstance(web_search_data, dict) and "results" in web_search_data:
                for res in web_search_data["results"]:
                    if isinstance(res, dict) and "experience" in res and res["experience"]:
                        experience_match = max(experience_match, res["experience"].get("average_score", 0))
            # Also check non-nested format from legacy
            if not experience_match and web_search_data and isinstance(web_search_data, dict):
                exp_data = web_search_data.get("experience", {})
                if isinstance(exp_data, dict):
                    experience_match = exp_data.get("average_score", 0)

            github_score = github_data.get("score100", github_data.get("score", 0)) if github_data else 0

            overall = 0.0
            weights = 0.0
            
            if github_data and (github_data.get("success", False) or github_score > 0):
                overall += github_score * 0.5
                weights += 0.5
            if linkedin_data and (linkedin_data.get("profileId") or linkedin_data.get("profile")):
                overall += 100 * 0.2
                weights += 0.2
            if web_search_data and ("results" in web_search_data or "education" in web_search_data):
                overall += experience_match * 0.3
                weights += 0.3

            overall_credibility = round(overall / weights, 2) if weights > 0 else 0

            match_score = {
                "overallCredibility": overall_credibility,
                "experienceMatch": experience_match,
                "skillsMatch": github_score,
                "educationMatch": 0
            }
            update_fields["matchScore"] = match_score
            print(f"[AGENT] Writing to DB: overallCredibility={overall_credibility}, github={github_score}, exp={experience_match}")
            
            await target_collection.update_one(
                {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]},
                {"$set": update_fields},
                upsert=True,
            )
    except Exception as e:
        logger.error("Failed to write verification_data results: %s", e)

    summary = memory.get_summary()
    summary["run_id"] = run_id
    summary["run_duration_ms"] = elapsed_ms
    summary["status"] = "partial" if elapsed_ms >= TOTAL_TIMEOUT_SEC * 1000 else "complete"

    logger.info(
        "Agent run %s finished in %dms — actions=%s skipped=%s",
        run_id, elapsed_ms, memory.action_history, memory.skipped,
    )

    return summary
