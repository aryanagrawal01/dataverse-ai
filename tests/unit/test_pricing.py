from dataverse.llm.pricing import estimate_cost_usd


def test_known_openai_model_priced_correctly():
    cost = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.15 + 0.60


def test_known_groq_model_priced_correctly():
    cost = estimate_cost_usd("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
    assert cost == 0.59 + 0.79


def test_groq_model_far_cheaper_than_openai_fallback():
    """Regression guard: an unrecognized Groq-family model must not silently
    fall back to GPT-4o-level pricing and blow through the budget cap."""
    groq_cost = estimate_cost_usd("llama-3.1-8b-instant", 1000, 1000)
    fallback_cost = estimate_cost_usd("some-unknown-model", 1000, 1000)
    assert groq_cost < fallback_cost


def test_zero_tokens_is_zero_cost():
    assert estimate_cost_usd("gpt-4o-mini", 0, 0) == 0.0


def test_unknown_model_uses_conservative_fallback():
    cost = estimate_cost_usd("some-future-model", 1_000_000, 1_000_000)
    assert cost == 2.50 + 10.00
