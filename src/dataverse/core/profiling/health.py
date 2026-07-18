"""Composite Data Health Score.

Starts at 100 and applies capped penalties per issue family, so one terrible
column can't zero out an otherwise healthy dataset.
"""

from dataverse.schemas.profiling import ColumnProfile, HealthIssue, HealthScore

_CAPS = {
    "missing_values": 30.0,
    "duplicate_rows": 15.0,
    "wrong_type": 15.0,
    "outliers": 10.0,
    "constant_column": 6.0,
    "invalid_records": 10.0,
}


def compute_health(
    row_count: int,
    duplicate_row_count: int,
    columns: list[ColumnProfile],
) -> HealthScore:
    issues: list[HealthIssue] = []

    def add(
        kind: str,
        severity: str,
        description: str,
        affected: int,
        penalty: float,
        column: str | None = None,
    ) -> None:
        issues.append(
            HealthIssue(
                kind=kind,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                column=column,
                description=description,
                affected_rows=affected,
                penalty=round(penalty, 2),
            )
        )

    if row_count == 0:
        return HealthScore(score=0, issues=[])

    # --- Missing values (per column, weighted by share missing) ---
    for c in columns:
        if c.missing_count > 0:
            pct = c.missing_pct
            severity = "high" if pct > 20 else ("medium" if pct > 5 else "low")
            add(
                "missing_values",
                severity,
                f"`{c.name}` is missing {pct:.1f}% of values ({c.missing_count:,} rows)",
                c.missing_count,
                min(pct * 0.4, 12.0),
                c.name,
            )

    # --- Duplicate rows ---
    if duplicate_row_count > 0:
        dup_pct = duplicate_row_count / row_count * 100
        add(
            "duplicate_rows",
            "high" if dup_pct > 5 else "medium",
            f"{duplicate_row_count:,} duplicate rows ({dup_pct:.1f}%)",
            duplicate_row_count,
            min(dup_pct * 0.8, _CAPS["duplicate_rows"]),
        )

    # --- Text-stored types + invalid records within them ---
    for c in columns:
        if c.suggested_type is not None:
            add(
                "wrong_type",
                "medium",
                f"`{c.name}` is stored as text but {c.parse_success_pct:.0f}% "
                f"parses as {c.suggested_type}",
                row_count - c.missing_count,
                5.0,
                c.name,
            )
            if c.parse_success_pct is not None and c.parse_success_pct < 100:
                bad = int(round((100 - c.parse_success_pct) / 100 * (row_count - c.missing_count)))
                if bad > 0:
                    add(
                        "invalid_records",
                        "medium",
                        f"`{c.name}` has ~{bad:,} values that don't parse as {c.suggested_type}",
                        bad,
                        min(bad / row_count * 100 * 0.3, 5.0),
                        c.name,
                    )

    # --- Outliers ---
    for c in columns:
        if c.outlier_count_iqr > 0 and c.semantic_type == "numeric":
            pct = c.outlier_count_iqr / row_count * 100
            add(
                "outliers",
                "low",
                f"`{c.name}` has {c.outlier_count_iqr:,} statistical outliers ({pct:.1f}%)",
                c.outlier_count_iqr,
                min(pct * 0.2, 4.0),
                c.name,
            )

    # --- Constant columns ---
    for c in columns:
        if c.is_constant:
            add(
                "constant_column",
                "low",
                f"`{c.name}` has a single value everywhere — carries no information",
                row_count,
                2.0,
                c.name,
            )

    # Apply per-family caps, then sum.
    total = 0.0
    for kind, cap in _CAPS.items():
        family = sum(i.penalty for i in issues if i.kind == kind)
        total += min(family, cap)

    return HealthScore(score=max(0, min(100, round(100 - total))), issues=issues)
