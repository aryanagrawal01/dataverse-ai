"""LLM provider protocol.

Everything above this layer depends on the protocol, never on a vendor SDK.
Providers are stateful per request-scope: they accumulate usage so services
can record cost after a call sequence completes.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LLMUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


@dataclass
class UsageTracker:
    calls: list[LLMUsage] = field(default_factory=list)

    def add(self, usage: LLMUsage) -> None:
        self.calls.append(usage)

    @property
    def total_cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.calls)


class LLMProvider(Protocol):
    tracker: UsageTracker

    @property
    def available(self) -> bool: ...

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 1200,
    ) -> LLMResult:
        """Run one completion. Raises LLMUnavailableError on outage/no-config."""
        ...
