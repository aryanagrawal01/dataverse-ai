from pathlib import Path

import pytest


@pytest.fixture
def ready_project():
    from dataverse.services import auth_service, ingestion_service, pipeline_service

    user = auth_service.register("rep@example.com", "password9").user
    data = Path("sample_data/retail_sales_demo.csv").read_bytes()
    project = ingestion_service.create_project_from_upload(user.id, "Q2 Sales.csv", data)
    pipeline_service.profile_project(user.id, project.id)
    return user, project


def test_pdf_generates_and_persists(ready_project):
    from dataverse.services import report_service

    user, project = ready_project
    handle = report_service.generate_pdf(user.id, project.id)

    assert handle.data.startswith(b"%PDF")
    assert len(handle.data) > 10_000  # has real content
    assert handle.filename.endswith(".pdf")

    past = report_service.list_reports(user.id, project.id)
    assert len(past) == 1
    downloaded = report_service.download_report(user.id, project.id, handle.report_id)
    assert downloaded == handle.data


def test_report_ownership_enforced(ready_project):
    from dataverse.services import auth_service, report_service
    from dataverse.utils.errors import NotFoundError

    user, project = ready_project
    intruder = auth_service.register("intruder@example.com", "password9").user
    with pytest.raises(NotFoundError):
        report_service.generate_pdf(intruder.id, project.id)
    with pytest.raises(NotFoundError):
        report_service.list_reports(intruder.id, project.id)
