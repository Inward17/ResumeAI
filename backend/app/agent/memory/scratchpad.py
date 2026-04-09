"""
Scratchpad — Section 6.9

Stores intermediate LLM reasoning output for debugging and
observability.  Cleared at the end of each request.
"""

from typing import Any, Dict, List


class Scratchpad:
    """Ephemeral store for intermediate reasoning artefacts."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []

    def add(self, stage: str, data: Any):
        """Record a reasoning step (prompt, raw LLM output, parsed plan, etc.)."""
        self._entries.append({"stage": stage, "data": data})

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()
