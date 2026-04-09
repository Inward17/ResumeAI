from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Optional, Any

class SignalFreshness(BaseModel):
    signal: str           # "github" | "linkedin" | "web_search"
    last_verified: Optional[datetime]
    is_fresh: bool
    confidence: float     # 0.0 to 1.0

class AgentContext(BaseModel):
    candidate_id: str
    job_id: str
    verification_data: dict          # raw MongoDB doc
    freshness: List[SignalFreshness]
    job: dict                        # job title, required_skills, jd_embedding
    evaluation: dict                 # jd_match scores
    history: List[str]               # previous agent actions this session

class VerificationPlan(BaseModel):
    actions: List[str]               # e.g. ["github", "web_search"]
    skip: List[str]                  # e.g. ["linkedin"]
    reasoning: Dict[str, str]        # per-signal explanation
    source: str                      # "rule" | "score" | "llm"

class ToolResult(BaseModel):
    tool: str
    status: str                      # "completed" | "skipped" | "error"
    data: Optional[Dict[str, Any]]
    reason: Optional[str]            # populated when status != "completed"
    duration_ms: int
