"""Dashboard orchestration: pick best dataset version, build the spec."""

from dataverse.config.constants import DATASET_KIND_CLEANED, DATASET_KIND_RAW
from dataverse.core.dashboard import build_dashboard
from dataverse.core.profiling import profile_dataframe
from dataverse.schemas.dashboard import DashboardFilters, DashboardSpec
from dataverse.services import pipeline_service
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def build(user_id: str, project_id: str, filters: DashboardFilters | None = None) -> DashboardSpec:
    profile = pipeline_service.get_stored_profile(user_id, project_id, DATASET_KIND_CLEANED)
    kind = DATASET_KIND_CLEANED if profile is not None else DATASET_KIND_RAW
    df = pipeline_service.load_dataframe(user_id, project_id, kind)
    if profile is None:
        profile = pipeline_service.get_stored_profile(user_id, project_id, DATASET_KIND_RAW)
    if profile is None:
        profile = profile_dataframe(df)
    spec = build_dashboard(df, profile, kind, filters)
    log.info(
        "dashboard.built",
        project_id=project_id,
        kind=kind,
        kpis=len(spec.kpis),
        charts=len(spec.charts),
    )
    return spec
