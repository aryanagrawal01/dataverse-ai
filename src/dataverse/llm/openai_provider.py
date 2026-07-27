"""OpenAI-compatible adapter — the only module in the codebase importing the
openai SDK. Works against any provider speaking the same wire protocol
(Groq, etc.) via settings.llm_base_url — no per-provider branching needed."""

import time

from dataverse.config import get_settings
from dataverse.llm.pricing import estimate_cost_usd
from dataverse.llm.provider import LLMResult, LLMUsage, UsageTracker
from dataverse.utils.errors import LLMUnavailableError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_MAX_RETRIES = 2


class OpenAIProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._timeout = settings.llm_timeout_seconds
        self.tracker = UsageTracker()

        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url or None,
            timeout=self._timeout,
        )

    @property
    def available(self) -> bool:
        return True

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 1200,
    ) -> LLMResult:
        import openai

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            started = time.monotonic()
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                    response_format={"type": "json_object"} if json_mode else {"type": "text"},
                )
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0
                usage = LLMUsage(
                    model=self._model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=estimate_cost_usd(self._model, prompt_tokens, completion_tokens),
                )
                self.tracker.add(usage)
                log.info(
                    "llm.call",
                    model=self._model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=usage.cost_usd,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    json_mode=json_mode,
                )
                return LLMResult(text=response.choices[0].message.content or "", usage=usage)
            except (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
            ) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(1.5**attempt)
                    continue
            except openai.AuthenticationError as exc:
                raise LLMUnavailableError(f"openai auth failed: {exc}") from exc
            except openai.APIError as exc:
                last_error = exc
                break
        log.warning("llm.unavailable", error=str(last_error))
        raise LLMUnavailableError(f"openai call failed: {last_error}") from last_error
