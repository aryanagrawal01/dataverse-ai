"""The torture suite run against the parser."""

import pytest

from dataverse.services import ingestion_service as ing
from dataverse.utils.errors import (
    FileTooLargeError,
    ParseError,
    UnsupportedFormatError,
)
from tests.fixtures import torture


class TestValidation:
    def test_rejects_unsupported_extension(self):
        with pytest.raises(UnsupportedFormatError):
            ing.parse_upload("report.pdf", torture.not_a_table_pdf())

    def test_rejects_oversized_file(self, monkeypatch):
        from dataverse.config import get_settings

        monkeypatch.setenv("MAX_UPLOAD_MB", "1")
        get_settings.cache_clear()
        big = b"a,b\n" + b"1,2\n" * 300_000  # ~1.8 MB
        with pytest.raises(FileTooLargeError):
            ing.parse_upload("big.csv", big)

    def test_rejects_empty_file(self):
        with pytest.raises(ParseError):
            ing.parse_upload("empty.csv", torture.empty_file())

    def test_rejects_header_only(self):
        with pytest.raises(ParseError):
            ing.parse_upload("headers.csv", torture.header_only_csv())

    def test_path_traversal_filename_reduced_to_basename(self):
        df = ing.parse_upload("..\\..\\evil\\..\\sales.csv", torture.clean_sales_csv())
        assert len(df) == 10


class TestCsvParsing:
    def test_clean_csv(self):
        df = ing.parse_upload("s.csv", torture.clean_sales_csv())
        assert df.shape == (10, 5)

    def test_single_row(self):
        assert len(ing.parse_upload("s.csv", torture.single_row_csv())) == 1

    def test_single_column(self):
        df = ing.parse_upload("s.csv", torture.single_column_csv())
        assert df.shape == (5, 1)

    def test_semicolon_delimiter(self):
        df = ing.parse_upload("de.csv", torture.semicolon_csv())
        assert list(df.columns) == ["id", "name", "betrag"]
        assert len(df) == 3

    def test_tab_delimiter(self):
        df = ing.parse_upload("t.csv", torture.tab_delimited_csv())
        assert df.shape == (3, 3)

    def test_quoted_commas(self):
        df = ing.parse_upload("q.csv", torture.quoted_commas_csv())
        assert df.shape == (3, 3)
        assert df["company"].iloc[0] == "Acme, Inc."

    def test_utf8_bom(self):
        df = ing.parse_upload("bom.csv", torture.utf8_bom_csv())
        assert "città" in df.columns

    def test_latin1_encoding(self):
        df = ing.parse_upload("l1.csv", torture.latin1_csv())
        assert df["name"].iloc[0] == "Café Münster"

    def test_utf16_encoding(self):
        df = ing.parse_upload("u16.csv", torture.utf16_csv())
        assert df.shape == (2, 3)

    def test_duplicate_and_blank_column_names_deduped(self):
        df = ing.parse_upload("dup.csv", torture.duplicate_column_names_csv())
        assert len(set(df.columns)) == len(df.columns)
        assert all(c.strip() for c in df.columns)


class TestExcelParsing:
    def test_simple_xlsx(self):
        df = ing.parse_upload("wb.xlsx", torture.excel_simple())
        assert df.shape == (3, 3)

    def test_sheet_names_listed(self):
        names = ing.excel_sheet_names(torture.excel_multisheet(), ".xlsx")
        assert names == ["Sales", "Costs", "Notes"]

    def test_specific_sheet_parsed(self):
        df = ing.parse_upload("wb.xlsx", torture.excel_multisheet(), sheet="Costs")
        assert "cost" in df.columns

    def test_garbage_xlsx_rejected(self):
        with pytest.raises(ParseError):
            ing.parse_upload("fake.xlsx", b"this is not a zip archive")


class TestEndToEnd:
    def test_create_project_from_upload(self):
        from dataverse.services import auth_service, pipeline_service

        user = auth_service.register("ingest@example.com", "password9").user
        project = ing.create_project_from_upload(user.id, "Q2 Sales.csv", torture.clean_sales_csv())
        assert project.name == "Q2 Sales"
        assert project.row_count == 10

        profile = pipeline_service.profile_project(user.id, project.id)
        assert profile.row_count == 10
        assert pipeline_service.get_stored_profile(user.id, project.id) == profile

        df = pipeline_service.load_dataframe(user.id, project.id)
        assert df.shape == (10, 5)

    def test_quota_enforced(self, monkeypatch):
        from dataverse.config import get_settings
        from dataverse.services import auth_service
        from dataverse.utils.errors import QuotaExceededError

        monkeypatch.setenv("USER_QUOTA_MB", "0")
        get_settings.cache_clear()
        user = auth_service.register("quota@example.com", "password9").user
        with pytest.raises(QuotaExceededError):
            ing.create_project_from_upload(user.id, "s.csv", torture.clean_sales_csv())

    def test_sample_dataset_ingests_cleanly(self):
        from pathlib import Path

        from dataverse.services import auth_service, pipeline_service

        sample = Path("sample_data/retail_sales_demo.csv")
        user = auth_service.register("sample@example.com", "password9").user
        project = ing.create_project_from_upload(user.id, sample.name, sample.read_bytes())
        profile = pipeline_service.profile_project(user.id, project.id)

        assert profile.row_count > 2500
        assert profile.duplicate_row_count > 0  # injected issues are all found
        assert any(i.kind == "missing_values" for i in profile.health.issues)
        assert profile.column("order_date").suggested_type == "datetime"
        assert profile.column("unit_price").suggested_type == "numeric"
        assert profile.column("order_id").semantic_type == "id"
        assert 40 <= profile.health.score < 100
