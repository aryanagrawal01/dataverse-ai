"""Exception hierarchy for DataVerse AI.

Every DataVerseError carries a technical `message` (for logs) and a
`user_message` (safe to render in the UI). Upper layers never surface raw
tracebacks or vendor exception types to users.
"""

from typing import Any


class DataVerseError(Exception):
    """Base class for all expected application errors."""

    error_code = "internal_error"
    default_user_message = "Something went wrong. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        user_message: str | None = None,
        **context: Any,
    ) -> None:
        self.message = message or self.default_user_message
        self.user_message = user_message or self.default_user_message
        self.context = context
        super().__init__(self.message)


# --- Input validation ---
class ValidationError(DataVerseError):
    error_code = "validation_error"
    default_user_message = "The provided input is not valid."


# --- Auth ---
class AuthError(DataVerseError):
    error_code = "auth_error"
    default_user_message = "Authentication failed."


class InvalidCredentialsError(AuthError):
    error_code = "invalid_credentials"
    default_user_message = "Invalid email or password."


class AccountLockedError(AuthError):
    error_code = "account_locked"
    default_user_message = (
        "Too many failed attempts. Your account is temporarily locked — try again later."
    )


class EmailTakenError(AuthError):
    error_code = "email_taken"
    default_user_message = "An account with this email already exists."


class WeakPasswordError(AuthError):
    error_code = "weak_password"
    default_user_message = "Password must be at least 8 characters and include at least one number."


class SessionExpiredError(AuthError):
    error_code = "session_expired"
    default_user_message = "Your session has expired. Please sign in again."


# --- Resources ---
class NotFoundError(DataVerseError):
    """Raised for missing resources AND unauthorized access (no existence leak)."""

    error_code = "not_found"
    default_user_message = "The requested resource was not found."


# --- Ingestion ---
class IngestionError(DataVerseError):
    error_code = "ingestion_error"
    default_user_message = "We couldn't process this file."


class UnsupportedFormatError(IngestionError):
    error_code = "unsupported_format"
    default_user_message = "Unsupported file type. Please upload a CSV or Excel file."


class FileTooLargeError(IngestionError):
    error_code = "file_too_large"
    default_user_message = "This file exceeds the upload size limit."


class ParseError(IngestionError):
    error_code = "parse_error"
    default_user_message = "We couldn't read this file. Check that it is a valid CSV or Excel file."


class QuotaExceededError(IngestionError):
    error_code = "quota_exceeded"
    default_user_message = "You've reached your storage quota. Delete a project to free space."


# --- Pipeline ---
class PipelineError(DataVerseError):
    error_code = "pipeline_error"
    default_user_message = "Data processing failed."


class ProfilingError(PipelineError):
    error_code = "profiling_error"
    default_user_message = "We couldn't profile this dataset."


class CleaningError(PipelineError):
    error_code = "cleaning_error"
    default_user_message = "Applying the cleaning plan failed. Your original data is untouched."


# --- Chat ---
class ChatError(DataVerseError):
    error_code = "chat_error"
    default_user_message = "I couldn't answer that question."


class PlanValidationError(ChatError):
    error_code = "plan_invalid"
    default_user_message = "I couldn't turn that question into a data query. Try rephrasing it."


class UnanswerableError(ChatError):
    """Expected product state, not a bug: the data can't answer the question."""

    error_code = "unanswerable"
    default_user_message = "That question can't be answered from this dataset."


# --- Forecasting ---
class ForecastNotApplicableError(DataVerseError):
    error_code = "forecast_not_applicable"
    default_user_message = "Forecasting isn't available for this dataset."


# --- LLM ---
class LLMError(DataVerseError):
    error_code = "llm_error"
    default_user_message = "The AI service is unavailable right now."


class LLMUnavailableError(LLMError):
    error_code = "llm_unavailable"
    default_user_message = "AI features are temporarily unavailable. Everything else keeps working."


class BudgetExceededError(LLMError):
    error_code = "llm_budget_exceeded"
    default_user_message = "The AI usage budget for this project has been reached."


# --- Storage ---
class StorageError(DataVerseError):
    error_code = "storage_error"
    default_user_message = "File storage is unavailable right now."
