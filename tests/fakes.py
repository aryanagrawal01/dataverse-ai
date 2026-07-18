"""Test doubles for the LLM layer."""

import json
from typing import Any

from dataverse.llm.pricing import estimate_cost_usd
from dataverse.llm.provider import LLMResult, LLMUsage, UsageTracker


class FakeProvider:
    """Returns queued responses in order; records the prompts it received."""

    def __init__(self, responses: list[str | dict[str, Any]]) -> None:
        self._queue = [r if isinstance(r, str) else json.dumps(r) for r in responses]
        self.prompts: list[tuple[str, str]] = []
        self.tracker = UsageTracker()

    @property
    def available(self) -> bool:
        return True

    def complete(
        self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 1200
    ) -> LLMResult:
        self.prompts.append((system, user))
        if not self._queue:
            raise AssertionError("FakeProvider queue exhausted")
        text = self._queue.pop(0)
        usage = LLMUsage(
            model="fake-model",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=estimate_cost_usd("gpt-4o-mini", 100, 50),
        )
        self.tracker.add(usage)
        return LLMResult(text=text, usage=usage)
