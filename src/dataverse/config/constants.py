"""Product-level constants that are not environment-tunable."""

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Semantic column types produced by profiling type inference.
SEMANTIC_NUMERIC = "numeric"
SEMANTIC_CATEGORICAL = "categorical"
SEMANTIC_DATETIME = "datetime"
SEMANTIC_TEXT = "text"
SEMANTIC_BOOLEAN = "boolean"
SEMANTIC_ID = "id"

PROJECT_STATUS_UPLOADED = "uploaded"
PROJECT_STATUS_PROFILED = "profiled"
PROJECT_STATUS_CLEANED = "cleaned"
PROJECT_STATUS_READY = "ready"
PROJECT_STATUS_FAILED = "failed"

DATASET_KIND_RAW = "raw"
DATASET_KIND_CLEANED = "cleaned"

# Display-layer guardrails
MAX_PREVIEW_ROWS = 100
MAX_CHART_POINTS = 50_000

BCRYPT_ROUNDS = 12
MIN_PASSWORD_LENGTH = 8
