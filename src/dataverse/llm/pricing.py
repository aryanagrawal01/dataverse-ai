"""Model pricing (USD per 1M tokens) for cost accounting.

Approximate published prices; used for budget enforcement, not billing.
Unknown models fall back to a conservative estimate.
"""

_PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    # model: (input, output)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    # Groq (served via llm_base_url, OpenAI-compatible)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}

_FALLBACK = (2.50, 10.00)


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = _PRICES_PER_MILLION.get(model, _FALLBACK)
    return round(
        prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price,
        6,
    )
