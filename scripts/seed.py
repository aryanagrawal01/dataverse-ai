"""Seed a demo user with a fully-processed sample project.

Usage:
    alembic upgrade head
    python scripts/seed.py

Creates demo@dataverse.ai / demo-pass-1 with the retail sample uploaded,
profiled, cleaned, and insights generated (template mode without an API key).
Idempotent: running twice is a no-op.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dataverse.core.cleaning import suggest_cleaning  # noqa: E402
from dataverse.schemas.cleaning import CleaningPlan, PlanItem  # noqa: E402
from dataverse.services import (  # noqa: E402
    auth_service,
    ingestion_service,
    insight_service,
    pipeline_service,
)
from dataverse.utils.errors import EmailTakenError  # noqa: E402

DEMO_EMAIL = "demo@dataverse.ai"
DEMO_PASSWORD = "demo-pass-1"


def main() -> None:
    try:
        user = auth_service.register(DEMO_EMAIL, DEMO_PASSWORD, "Demo User").user
    except EmailTakenError:
        print(f"Seed already applied - sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}")
        return

    sample = Path(__file__).resolve().parents[1] / "sample_data" / "retail_sales_demo.csv"
    project = ingestion_service.create_project_from_upload(
        user.id, sample.name, sample.read_bytes()
    )
    profile = pipeline_service.profile_project(user.id, project.id)

    plan = CleaningPlan(
        items=[
            PlanItem(rule=s.rule, column=s.column, params=s.params)
            for s in suggest_cleaning(profile)
            if s.enabled_by_default
        ]
    )
    result = pipeline_service.apply_cleaning(user.id, project.id, plan)
    insight_service.generate(user.id, project.id)

    print(
        f"Seeded {DEMO_EMAIL} / {DEMO_PASSWORD} - project '{project.name}': "
        f"health {result.comparison.health_before} -> {result.comparison.health_after}"
    )


if __name__ == "__main__":
    main()
