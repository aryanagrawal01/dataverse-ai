"""Apply an accepted CleaningPlan to a DataFrame."""

import pandas as pd

from dataverse.core.cleaning.rules import EXECUTION_ORDER, REGISTRY
from dataverse.schemas.cleaning import CleaningLogEntry, CleaningPlan
from dataverse.utils.errors import CleaningError


def execute_plan(
    df: pd.DataFrame, plan: CleaningPlan
) -> tuple[pd.DataFrame, list[CleaningLogEntry]]:
    """Returns (cleaned_df, log). Raises CleaningError on any rule failure —
    callers must treat the run as all-or-nothing."""
    log: list[CleaningLogEntry] = []
    out = df

    ordered = sorted(plan.items, key=lambda i: EXECUTION_ORDER.index(i.rule))
    for item in ordered:
        rule_fn = REGISTRY.get(item.rule)
        if rule_fn is None:
            raise CleaningError(f"unknown rule {item.rule!r}")
        params = {**item.params}
        if item.column is not None:
            params.setdefault("column", item.column)
        out, affected, detail = rule_fn(out, params)
        log.append(
            CleaningLogEntry(
                rule=item.rule,
                column=item.column,
                params=params,
                rows_affected=affected,
                detail=detail,
            )
        )

    if out.empty:
        raise CleaningError(
            "cleaning removed every row",
            user_message=(
                "This cleaning plan would remove every row of data. "
                "Loosen the drop/remove rules and try again."
            ),
        )
    return out.reset_index(drop=True), log
