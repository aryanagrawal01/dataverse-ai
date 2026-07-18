"""Turn a DatasetProfile into reviewable cleaning suggestions."""

from dataverse.schemas.cleaning import CleaningSuggestion
from dataverse.schemas.profiling import DatasetProfile


def suggest_cleaning(profile: DatasetProfile) -> list[CleaningSuggestion]:
    suggestions: list[CleaningSuggestion] = []

    if profile.duplicate_row_count > 0:
        suggestions.append(
            CleaningSuggestion(
                id="deduplicate",
                rule="deduplicate",
                title=f"Remove {profile.duplicate_row_count:,} duplicate rows",
                description=(
                    f"{profile.duplicate_row_count:,} rows are exact copies of other rows "
                    f"({profile.duplicate_row_count / profile.row_count * 100:.1f}% of the data)."
                ),
                estimated_rows=profile.duplicate_row_count,
            )
        )

    for c in profile.columns:
        if c.suggested_type is not None:
            suggestions.append(
                CleaningSuggestion(
                    id=f"coerce_type:{c.name}",
                    rule="coerce_type",
                    column=c.name,
                    params={"column": c.name, "target": c.suggested_type},
                    title=f"Convert `{c.name}` from text to {c.suggested_type}",
                    description=(
                        f"{c.parse_success_pct:.0f}% of values parse cleanly as "
                        f"{c.suggested_type}; the rest become missing (fixable below)."
                    ),
                    estimated_rows=profile.row_count - c.missing_count,
                )
            )

    for c in profile.columns:
        if c.missing_count > 0 and c.semantic_type in ("numeric", "categorical", "boolean", "text"):
            if c.semantic_type == "numeric":
                strategy, options = "median", ["median", "mean", "zero", "drop_rows"]
                how = "the median"
            else:
                strategy, options = "unknown_label", ["unknown_label", "mode", "drop_rows"]
                how = 'an "Unknown" label'
            suggestions.append(
                CleaningSuggestion(
                    id=f"impute_missing:{c.name}",
                    rule="impute_missing",
                    column=c.name,
                    params={"column": c.name, "strategy": strategy},
                    title=f"Fill {c.missing_count:,} missing values in `{c.name}`",
                    description=f"{c.missing_pct:.1f}% of `{c.name}` is empty — fill with {how}.",
                    estimated_rows=c.missing_count,
                    strategy_options=options,
                )
            )

    for c in profile.columns:
        if c.semantic_type == "numeric" and c.outlier_count_iqr > 0:
            suggestions.append(
                CleaningSuggestion(
                    id=f"handle_outliers:{c.name}",
                    rule="handle_outliers",
                    column=c.name,
                    params={"column": c.name, "strategy": "keep"},
                    title=f"Review {c.outlier_count_iqr:,} outliers in `{c.name}`",
                    description=(
                        "Statistical outliers can be real events (spikes, big orders). "
                        "Default is to keep them — cap or remove only if you know "
                        "they're errors."
                    ),
                    estimated_rows=c.outlier_count_iqr,
                    enabled_by_default=False,
                    strategy_options=["keep", "cap", "remove_rows"],
                )
            )

    for c in profile.columns:
        if c.is_constant:
            suggestions.append(
                CleaningSuggestion(
                    id=f"drop_constant_column:{c.name}",
                    rule="drop_constant_column",
                    column=c.name,
                    params={"column": c.name},
                    title=f"Drop constant column `{c.name}`",
                    description="Every row has the same value — the column carries no signal.",
                    estimated_rows=profile.row_count,
                    enabled_by_default=False,
                )
            )

    return suggestions
