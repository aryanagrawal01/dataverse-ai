"""PDF report generation: cover, summary, KPIs, charts, insights, appendix.

Charts are rendered to PNG with matplotlib (see core/dashboard/report_images.py
for why not Kaleido); if a chart fails to render, the report still generates
without it (graceful degradation).
"""

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dataverse.models import Report
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.dashboard import ChartSpec
from dataverse.services import dashboard_service, insight_service, pipeline_service
from dataverse.storage import get_storage
from dataverse.utils.errors import NotFoundError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_INK = colors.HexColor("#1A1D27")
_PRIMARY = colors.HexColor("#4F46E5")
_SOFT = colors.HexColor("#5A6072")
_BORDER = colors.HexColor("#E7E8EF")


class ReportHandle:
    def __init__(self, report_id: str, filename: str, data: bytes) -> None:
        self.report_id = report_id
        self.filename = filename
        self.data = data


def generate_pdf(user_id: str, project_id: str) -> ReportHandle:
    with session_scope() as s:
        project = ProjectRepository(s).by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        project_name = project.name
        health = project.health_score
        rows, cols_n = project.row_count, project.column_count

    spec = dashboard_service.build(user_id, project_id)
    insights = insight_service.generate(user_id, project_id)
    cleaning_log = pipeline_service.get_cleaning_log(user_id, project_id)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=f"DataVerse AI Report — {project_name}",
    )
    styles = _styles()
    story: list = []

    # --- Cover ---
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("◆ DataVerse AI", styles["brand"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(project_name, styles["cover_title"]))
    story.append(Spacer(1, 0.5 * cm))
    meta = (
        f"{rows:,} rows · {cols_n} columns"
        + (f" · Health score {health}/100" if health is not None else "")
        + f" · Generated {datetime.now(UTC):%B %d, %Y}"
    )
    story.append(Paragraph(meta, styles["muted"]))
    story.append(PageBreak())

    # --- Executive summary ---
    summary = next((i for i in insights.items if i.kind == "executive_summary"), None)
    if summary is not None:
        story.append(Paragraph("Executive summary", styles["h1"]))
        story.append(_rule())
        story.append(Paragraph(summary.content, styles["body"]))
        story.append(Spacer(1, 0.6 * cm))

    # --- KPIs ---
    if spec.kpis:
        story.append(Paragraph("Key metrics", styles["h1"]))
        story.append(_rule())
        kpi_cells = [
            [Paragraph(k.label, styles["kpi_label"]), Paragraph(k.value, styles["kpi_value"])]
            + (
                [Paragraph(k.delta, styles["muted"])]
                if k.delta
                else [Paragraph("", styles["muted"])]
            )
            for k in spec.kpis
        ]
        table = Table(kpi_cells, colWidths=[6 * cm, 5 * cm, 6 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, _BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.6 * cm))

    # --- Charts ---
    chart_images = _chart_images(spec.charts[:6])
    if chart_images:
        story.append(Paragraph("Dashboard highlights", styles["h1"]))
        story.append(_rule())
        for png in chart_images:
            story.append(Image(io.BytesIO(png), width=16 * cm, height=8 * cm))
            story.append(Spacer(1, 0.4 * cm))

    # --- Insights & recommendations ---
    others = [i for i in insights.items if i.kind not in ("executive_summary",)]
    if others:
        story.append(PageBreak())
        story.append(Paragraph("AI insights", styles["h1"]))
        story.append(_rule())
        for item in others:
            story.append(Paragraph(item.title, styles["h2"]))
            story.append(Paragraph(item.content, styles["body"]))
            story.append(Spacer(1, 0.3 * cm))

    # --- Cleaning appendix ---
    if cleaning_log:
        story.append(PageBreak())
        story.append(Paragraph("Appendix: data cleaning log", styles["h1"]))
        story.append(_rule())
        story.append(
            Paragraph(
                "The following transformations were reviewed and applied before analysis. "
                "The original raw file is preserved unchanged.",
                styles["muted"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        for entry in cleaning_log:
            story.append(Paragraph(f"• {_escape(entry.detail)}", styles["body"]))

    doc.build(story)
    pdf = buf.getvalue()

    storage = get_storage()
    with session_scope() as s:
        report = Report(project_id=project_id, format="pdf", storage_key="", size_bytes=len(pdf))
        s.add(report)
        s.flush()
        key = f"{user_id}/{project_id}/reports/{report.id}.pdf"
        report.storage_key = key
        storage.put(key, pdf)
        report_id = report.id

    log.info("report.generated", project_id=project_id, bytes=len(pdf))
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in project_name)[:60]
    return ReportHandle(report_id, f"{safe_name} - DataVerse Report.pdf", pdf)


def list_reports(user_id: str, project_id: str) -> list[dict]:
    from sqlalchemy import select

    with session_scope() as s:
        if ProjectRepository(s).by_id_for_user(user_id, project_id) is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        rows = list(
            s.execute(
                select(Report)
                .where(Report.project_id == project_id)
                .order_by(Report.created_at.desc())
            ).scalars()
        )
        return [
            {
                "id": r.id,
                "created_at": r.created_at,
                "size_bytes": r.size_bytes,
                "storage_key": r.storage_key,
            }
            for r in rows
        ]


def download_report(user_id: str, project_id: str, report_id: str) -> bytes:
    reports = {r["id"]: r for r in list_reports(user_id, project_id)}
    if report_id not in reports:
        raise NotFoundError(f"report {report_id} not found")
    return get_storage().get(reports[report_id]["storage_key"])


def _chart_images(specs: list[ChartSpec]) -> list[bytes]:
    from dataverse.core.dashboard.report_images import render_png

    images: list[bytes] = []
    for spec in specs:
        try:
            png = render_png(spec)
        except Exception as exc:
            log.warning("report.chart_image_failed", chart=spec.title, error=str(exc))
            continue
        if png is not None:
            images.append(png)
    return images


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Title"], fontSize=16, textColor=_PRIMARY, alignment=1
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontSize=30, textColor=_INK, alignment=1
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=16, textColor=_INK, spaceAfter=2
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12, textColor=_PRIMARY, spaceAfter=2
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=10, leading=15, textColor=_INK
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["BodyText"], fontSize=9, textColor=_SOFT, alignment=1
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["BodyText"], fontSize=10, textColor=_SOFT
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", parent=base["BodyText"], fontSize=13, textColor=_INK
        ),
    }


def _rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=8)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "")
