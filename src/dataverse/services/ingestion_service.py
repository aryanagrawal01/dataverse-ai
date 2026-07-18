"""File ingestion: validation → encoding/delimiter sniffing → parse → Parquet.

Raw bytes never touch disk under a user-controlled name; the parsed frame is
stored as Parquet under a server-generated key.
"""

import csv
import io
from pathlib import PurePosixPath, PureWindowsPath

import pandas as pd
from charset_normalizer import from_bytes as detect_charset

from dataverse.config import get_settings
from dataverse.config.constants import DATASET_KIND_RAW, SUPPORTED_EXTENSIONS
from dataverse.models import DatasetVersion
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.project import ProjectSummary
from dataverse.storage import get_storage
from dataverse.utils.dataframe import dedupe_column_names, to_parquet_bytes
from dataverse.utils.errors import (
    FileTooLargeError,
    ParseError,
    QuotaExceededError,
    UnsupportedFormatError,
)
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_SNIFF_BYTES = 65536
_DELIMITERS = ",;\t|"


def _extension(filename: str) -> str:
    # Use both parsers so "C:\evil\x.csv" and "a/b/x.csv" reduce to the basename.
    name = PureWindowsPath(PurePosixPath(filename).name).name
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""


def _display_name(filename: str) -> str:
    name = PureWindowsPath(PurePosixPath(filename).name).name
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (stem.replace("_", " ").replace("-", " ").strip() or "Untitled project")[:120]


def detect_encoding(data: bytes) -> str:
    best = detect_charset(data[:_SNIFF_BYTES]).best()
    return best.encoding if best is not None else "utf-8"


def detect_delimiter(sample_text: str) -> str:
    try:
        return csv.Sniffer().sniff(sample_text, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        return ","


def parse_csv(data: bytes) -> pd.DataFrame:
    if not data.strip():
        raise ParseError("empty file", user_message="This file is empty.")
    encoding = detect_encoding(data)
    try:
        text_sample = data[:_SNIFF_BYTES].decode(encoding, errors="replace")
        delimiter = detect_delimiter(text_sample)
        df = pd.read_csv(
            io.BytesIO(data),
            sep=delimiter,
            encoding=encoding,
            skip_blank_lines=True,
            on_bad_lines="skip",
        )
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(
            f"csv parse failed: {type(exc).__name__}: {exc}", encoding=encoding
        ) from exc
    return _validate_frame(df)


def excel_sheet_names(data: bytes, ext: str) -> list[str]:
    try:
        xl = pd.ExcelFile(io.BytesIO(data), engine="xlrd" if ext == ".xls" else "openpyxl")
        return [str(s) for s in xl.sheet_names]
    except Exception as exc:
        raise ParseError(f"excel open failed: {type(exc).__name__}: {exc}") from exc


def parse_excel(data: bytes, ext: str, sheet: str | None = None) -> pd.DataFrame:
    try:
        engine = "xlrd" if ext == ".xls" else "openpyxl"
        df = pd.read_excel(  # type: ignore[call-overload]
            io.BytesIO(data), sheet_name=sheet or 0, engine=engine
        )
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"excel parse failed: {type(exc).__name__}: {exc}") from exc
    return _validate_frame(df)


def _validate_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty or len(df.columns) == 0:
        raise ParseError(
            "no data rows after parse",
            user_message="This file has headers but no data rows we could read.",
        )
    df.columns = dedupe_column_names([str(c) for c in df.columns])
    return df.reset_index(drop=True)


def parse_upload(filename: str, data: bytes, sheet: str | None = None) -> pd.DataFrame:
    """Validate and parse an upload without touching the database (pure-ish)."""
    settings = get_settings()
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(f"rejected extension {ext!r} for {filename!r}")
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"{len(data)} bytes > limit {settings.max_upload_bytes}",
            user_message=(
                f"This file is {len(data) / 1_048_576:.0f} MB — the limit is "
                f"{settings.max_upload_mb} MB. Try splitting it or sampling rows."
            ),
        )
    if ext == ".csv":
        return parse_csv(data)
    return parse_excel(data, ext, sheet)


def create_project_from_upload(
    user_id: str, filename: str, data: bytes, sheet: str | None = None
) -> ProjectSummary:
    """Full ingestion: parse, quota-check, persist project + raw Parquet version."""
    settings = get_settings()
    df = parse_upload(filename, data, sheet)
    parquet = to_parquet_bytes(df)

    storage = get_storage()
    with session_scope() as s:
        repo = ProjectRepository(s)
        used = repo.total_bytes_for_user(user_id)
        if used + len(parquet) > settings.user_quota_mb * 1024 * 1024:
            raise QuotaExceededError(f"quota exceeded: used={used}, incoming={len(parquet)}")
        display = _display_name(filename)
        project = repo.create(user_id, display, PureWindowsPath(filename).name[:255])
        key = f"{user_id}/{project.id}/raw.parquet"
        storage.put(key, parquet)
        s.add(
            DatasetVersion(
                project_id=project.id,
                kind=DATASET_KIND_RAW,
                storage_key=key,
                row_count=len(df),
                size_bytes=len(parquet),
            )
        )
        project.row_count = len(df)
        project.column_count = len(df.columns)
        result = ProjectSummary.model_validate(project)

    log.info(
        "ingest.completed",
        project_id=result.id,
        rows=len(df),
        columns=len(df.columns),
        parquet_bytes=len(parquet),
    )
    return result
