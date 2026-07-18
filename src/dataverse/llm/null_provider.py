"""Degraded-mode provider: no API key configured (or forced off).

Raises LLMUnavailableError from complete(); callers fall back to their
deterministic template paths.
"""

from dataverse.llm.provider import LLMResult, UsageTracker
from dataverse.utils.errors import LLMUnavailableError


class NullProvider:
    def __init__(self) -> None:
        self.tracker = UsageTracker()

    @property
    def available(self) -> bool:
        return False

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 1200,
    ) -> LLMResult:
        raise LLMUnavailableError("no LLM configured")
