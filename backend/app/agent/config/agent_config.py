"""
Agent Configuration — Section 6.7 & 12

Defines guardrails, limits, and the tool registry that maps
signal names to their corresponding tool wrapper ``run`` functions.
"""

import os
from typing import Callable

from app.agent.tools import github_tool, linkedin_tool, websearch_tool, verification_tool

# ── Environment-variable limits (with defaults from Section 12) ─────────
MAX_STEPS         = int(os.environ.get("AGENT_MAX_STEPS", 8))
MAX_API_CALLS     = int(os.environ.get("AGENT_MAX_API_CALLS", 10))
TOOL_TIMEOUT_SEC  = int(os.environ.get("AGENT_TOOL_TIMEOUT_SEC", 60))
TOTAL_TIMEOUT_SEC = int(os.environ.get("AGENT_TOTAL_TIMEOUT_SEC", 120))
LLM_RETRIES       = int(os.environ.get("AGENT_LLM_RETRIES", 2))

# ── Tool Registry (Section 6.7) ────────────────────────────────────────
# Each value is an async callable: (AgentContext) -> ToolResult
TOOL_REGISTRY: dict[str, Callable] = {
    "github":       github_tool.run,
    "linkedin":     linkedin_tool.run,
    "web_search":   websearch_tool.run,
    "verification": verification_tool.run,
}
