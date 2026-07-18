from dataverse.config import get_settings
from dataverse.llm.provider import LLMProvider, LLMResult, LLMUsage, UsageTracker


def make_provider() -> LLMProvider:
    """New provider per request-scope (its tracker accumulates that scope's usage)."""
    if get_settings().llm_configured:
        from dataverse.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    from dataverse.llm.null_provider import NullProvider

    return NullProvider()


__all__ = ["LLMProvider", "LLMResult", "LLMUsage", "UsageTracker", "make_provider"]
