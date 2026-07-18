"""Turn a FactPack into business prose.

LLM path: the model may ONLY rephrase supplied facts — every number it can
cite is in the prompt. Template path: fully deterministic fallback that works
with no LLM at all.
"""

import json

from dataverse.llm.provider import LLMProvider
from dataverse.schemas.insights import FactPack, InsightItem, InsightSet
from dataverse.utils.errors import LLMError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_SYSTEM = """You are a senior business analyst writing for a non-technical executive.
You are given computed FACTS about a dataset as JSON. Write insights using ONLY these facts.
Rules:
- Never invent, estimate, or recompute a number. Cite figures exactly as given.
- Plain business language. No jargon, no hedging boilerplate.
- Return JSON: {"items": [{"kind": ..., "title": ..., "content": ...}]}
- kinds: executive_summary (exactly one, 3-5 sentences, first), trend, segment,
  anomaly, recommendation (1-3 concrete suggested actions, last).
- 4 to 7 items total. Titles under 60 characters. Content 1-4 sentences each.
- If data_notes mention quality caveats, weave one honest caveat in."""


def narrate(facts: FactPack, provider: LLMProvider) -> InsightSet:
    if provider.available:
        try:
            return _narrate_llm(facts, provider)
        except LLMError:
            log.warning("insights.llm_failed_falling_back")
    return _narrate_template(facts)


def _narrate_llm(facts: FactPack, provider: LLMProvider) -> InsightSet:
    result = provider.complete(
        _SYSTEM,
        f"FACTS:\n{facts.model_dump_json(indent=2)}",
        json_mode=True,
        max_tokens=1400,
    )
    try:
        payload = json.loads(result.text)
        items = [InsightItem.model_validate(item) for item in payload["items"]]
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        log.warning("insights.bad_llm_payload", error=str(exc))
        return _narrate_template(facts)
    if not items:
        return _narrate_template(facts)
    return InsightSet(items=items, model_used=result.usage.model, facts=facts)


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.1f}K"
    return f"{v:,.2f}"


def _narrate_template(facts: FactPack) -> InsightSet:
    items: list[InsightItem] = []

    summary_bits: list[str] = [
        f"This dataset covers {facts.row_count:,} records across {facts.column_count} columns"
    ]
    if facts.date_from and facts.date_to:
        summary_bits[0] += f" from {facts.date_from} to {facts.date_to}"
    summary_bits[0] += "."
    if facts.metrics:
        m = facts.metrics[0]
        summary_bits.append(f"Total {m.name} is {_fmt(m.total)} (average {_fmt(m.mean)}).")
        if m.growth_pct is not None:
            direction = "grew" if m.growth_pct >= 0 else "declined"
            summary_bits.append(
                f"{m.name} {direction} {abs(m.growth_pct):.1f}% in the second half "
                "of the period versus the first."
            )
    if facts.segments:
        s = facts.segments[0]
        summary_bits.append(
            f"{s.top_name} leads {s.dimension} with {s.top_share_pct:.1f}% of {s.metric}."
        )
    items.append(
        InsightItem(
            kind="executive_summary", title="Executive summary", content=" ".join(summary_bits)
        )
    )

    for m in facts.metrics:
        if m.growth_pct is None:
            continue
        direction = "up" if m.growth_pct >= 0 else "down"
        content = (
            f"{m.name} is {direction} {abs(m.growth_pct):.1f}% comparing the second half of "
            f"the period to the first."
        )
        if m.best_period:
            content += (
                f" The strongest period began {m.best_period} ({_fmt(m.best_period_value or 0)}); "
                f"the weakest began {m.worst_period} ({_fmt(m.worst_period_value or 0)})."
            )
        items.append(InsightItem(kind="trend", title=f"{m.name} trend", content=content))

    for s in facts.segments:
        items.append(
            InsightItem(
                kind="segment",
                title=f"{s.metric} by {s.dimension}",
                content=(
                    f"{s.top_name} generates {_fmt(s.top_value)} of {s.metric} "
                    f"({s.top_share_pct:.1f}% of the total across {s.segments_count} "
                    f"{s.dimension} values), while {s.bottom_name} trails at "
                    f"{_fmt(s.bottom_value)}."
                ),
            )
        )

    for a in facts.anomalies[:2]:
        items.append(
            InsightItem(
                kind="anomaly",
                title=f"Outliers in {a.column}",
                content=(
                    f"{a.outlier_count:,} values ({a.outlier_pct:.1f}%) in {a.column} fall far "
                    f"outside the typical range (extremes: {a.example_low} to {a.example_high}). "
                    "Verify whether these are real events or data errors."
                ),
            )
        )

    recommendations: list[str] = []
    declining = [m for m in facts.metrics if m.growth_pct is not None and m.growth_pct < 0]
    if declining:
        recommendations.append(
            f"Investigate the {abs(declining[0].growth_pct or 0):.1f}% decline in "
            f"{declining[0].name} before it compounds."
        )
    if facts.segments:
        s = facts.segments[0]
        recommendations.append(
            f"Study what makes {s.top_name} the strongest {s.dimension} and replicate it in "
            f"weaker segments like {s.bottom_name}."
        )
    if facts.data_notes:
        recommendations.append(
            f"Improve data collection: {facts.data_notes[0]} — this limits analysis accuracy."
        )
    if recommendations:
        items.append(
            InsightItem(
                kind="recommendation",
                title="Suggested actions",
                content=" ".join(f"{i + 1}. {r}" for i, r in enumerate(recommendations)),
            )
        )

    return InsightSet(items=items, model_used="template", facts=facts)
