# CLAUDE_CONTEXT.md

Condensed long-term memory for AI assistants working on this repository. Verified against the actual codebase, not the aspirational architecture doc — where they disagree, this file says so explicitly. For full detail see `README.md` (comprehensive) and `ARCHITECTURE.md` (original design doc, pre-implementation).

## Project goal

Upload a CSV/Excel file → get automated cleaning, an auto-generated dashboard, AI insights, NL chat, forecasts, and a PDF report. Single Streamlit process, no separate frontend/backend. Core trust rule that shapes everything: **the LLM never computes a number** — it only narrates precomputed facts or emits a validated query plan that a deterministic interpreter executes.

## Architecture (enforced by `import-linter` in CI, `pyproject.toml`)

```
ui → services → (core | repositories | storage | llm) → schemas/models → utils → config
```

- `core/` must NOT import streamlit, sqlalchemy, openai, repositories, models, ui, or services (forbidden-modules contract). Exception: `core.chat`/`core.insights` import `llm.provider` (a `Protocol`) via dependency injection — whitelisted in `ignore_imports`.
- `services/` is the only layer allowed to open a DB session (`repositories.base.session_scope()`).
- `ui/` is the only layer allowed to import `streamlit`.

Two `import-linter` contracts in `pyproject.toml` enforce this on every CI run — if you break the layering, CI fails, not just a lint warning.

## Folder purposes (one line each)

- `config/` — pydantic-settings `Settings` (env vars) + constants. Nothing else reads `os.environ`.
- `models/` — SQLAlchemy ORM, 10 tables, all UUID PKs, `TimestampMixin` on all.
- `schemas/` — Pydantic DTOs. One file per domain (`auth`, `project`, `profiling`, `cleaning`, `dashboard`, `forecast`, `insights`, `chat`).
- `repositories/` — SQL query layer, ownership-scoped (`by_id_for_user`). `base.py` has engine/session factory (both `@lru_cache`d singletons).
- `storage/` — `StorageBackend` Protocol. **Only `LocalStorage` exists.** `get_storage()` raises `NotImplementedError` for `"s3"`.
- `llm/` — `LLMProvider` Protocol. `OpenAIProvider` (works against OpenAI OR any OpenAI-compatible endpoint via `settings.llm_base_url`), `NullProvider` (always raises `LLMUnavailableError`, used when no key configured). `make_provider()` in `__init__.py` picks between them based on `settings.llm_configured`.
- `core/profiling/` — `profile_dataframe()` → `DatasetProfile`. Type inference distinguishes stored dtype from semantic type (detects currency-as-text, dates-as-text, booleans-as-text, ID columns by name pattern + uniqueness).
- `core/cleaning/` — `rules.py` has pure `(df, params) -> (df, rows_affected, detail)` functions with a **fixed execution order** (`EXECUTION_ORDER`, independent of plan order): dedupe → coerce_type → impute_missing → handle_outliers → drop_constant_column.
- `core/dashboard/` — `builder.py` (spec construction) / `semantics.py` (column role ranking) / `figures.py` (Plotly, used by UI) / `report_images.py` (matplotlib, used by PDF reports — deliberately separate from `figures.py`, see Common Pitfalls).
- `core/forecasting/` — `preparer.py` (eligibility + series aggregation with partial-edge-bucket trimming), `models.py` (seasonal_naive, holt_winters), `selector.py` (backtest MAPE picks the winner, refits on full series).
- `core/insights/` — `fact_extractor.py` (all numbers, pure pandas) / `narrator.py` (LLM or template, never invents numbers).
- `core/chat/` — `planner.py` (question → QueryPlan JSON via LLM) / `executor.py` (QueryPlan → pandas, whitelisted ops only, NO eval) / `composer.py` (result → answer text via LLM or template).
- `services/` — one file per user-facing workflow; see README's Module Breakdown table for the full list. This is where DB sessions open and where `core` + `repositories` + `storage` + `llm` get composed.
- `ui/pages_impl/` — one module per page: `auth`, `projects`, `upload`, `data_health`, `dashboard`, `insights`, `chat`, `forecast`, `reports`. `router.py` handles nav; `_project_shell()` builds the 6-tab workspace.

## Coding conventions observed in this repo

- Every `services/*.py` function signature starts with `user_id: str` (and usually `project_id: str`) and enforces ownership via the repository layer, not ad hoc checks.
- Errors are a typed hierarchy in `utils/errors.py`, all subclassing `DataVerseError(message, user_message=..., **context)`. `message` is for logs, `user_message` is what the UI shows. UI pages catch `DataVerseError` and call `st.error(exc.user_message)`.
- `ui/errors.py`'s `page_boundary` decorator wraps every page render; unexpected (non-`DataVerseError`) exceptions get a generated `request_id` shown to the user and logged via `log.exception`.
- Logging is `structlog`, JSON in non-dev environments. Context (`user_id`, `request_id`) is bound via `structlog.contextvars`, not passed as a parameter everywhere.
- Test files mirror `src/dataverse/...` structure 1:1 under `tests/unit/`.
- Migrations are named descriptively and applied incrementally — never edit an already-applied migration; add a new one.
- `Settings` is a singleton via `@lru_cache` on `get_settings()`; tests must call `get_settings.cache_clear()` after `monkeypatch.setenv(...)` (see `tests/conftest.py`'s `isolated_settings` fixture, which does this + clears the engine/storage caches too — autouse on every test).

## Important services (what to touch for common changes)

| If you need to... | Touch |
|---|---|
| Add a cleaning rule | `core/cleaning/rules.py` (pure fn) + `EXECUTION_ORDER` + `suggester.py` (when to suggest it) |
| Add a chart type | `schemas/dashboard.py` (new `ChartSpec` variant) + `core/dashboard/figures.py` (Plotly) + `core/dashboard/report_images.py` (matplotlib, for PDFs — both need updating, they're separate renderers) |
| Add a chat DSL operation | `schemas/chat.py` (`Operation` literal) + `core/chat/executor.py` (`execute_query_plan` dispatch) + `core/chat/planner.py`'s system prompt (describe the new op to the LLM) |
| Change LLM provider/model | `config/settings.py` (`llm_model`, `llm_base_url`) — no code change needed if the provider is OpenAI-compatible; `llm/pricing.py` needs a rate entry or cost estimates fall back to an expensive default |
| Add a DB table | New file in `models/`, register in `models/__init__.py`'s `__all__`, `alembic revision --autogenerate -m "..."`, review the generated migration before applying |
| Add a page | New file in `ui/pages_impl/`, wire into `router.py`'s `_project_shell()` tabs (or top-level nav for non-project pages) |

## Important models (schema summary)

`users` → `sessions` (1:N) → `projects` (1:N, soft-delete via `deleted_at`) → `dataset_versions` (1:N, unique on `(project_id, kind)` where kind ∈ {raw, cleaned}) → `insights` (cached per `dataset_version_id`), `cleaning_logs`, `chat_messages`, `forecasts`, `reports` (all 1:N off `projects`). `llm_usage` is 1:N off both `users` and (nullable) `projects`. Full table-by-table detail in README's Database section.

## Data flow (one sentence)

Upload → validate/parse → raw Parquet (immutable) → profile → optional cleaning → cleaned Parquet (separate `DatasetVersion`) → dashboard/insights/chat/forecast all read "cleaned if it exists, else raw" → PDF report assembles all of the above.

## API overview

**There is no HTTP API.** Streamlit UI calls `services/*` Python functions in-process. Do not invent REST routes when discussing this codebase — if asked to "add an endpoint," clarify whether they mean a new Streamlit page/service function or an actual future FastAPI layer (not yet started).

## Deployment

Local: SQLite + local disk, zero config. Docker Compose: app + Postgres 16. **Live deployment (Render, `render.yaml`) runs on SQLite with no persistent disk** — not Postgres, despite `docker-compose.yml` using Postgres — because the free-tier account already had one free Postgres database in use elsewhere, and Render allows only one per account (this silently hangs the Blueprint sync rather than erroring). `ENVIRONMENT=staging` on that deployment specifically to bypass `validate_for_environment()`'s prod-only SQLite rejection. Live LLM provider is Groq (`llama-3.3-70b-versatile`), not OpenAI, via `LLM_BASE_URL` — verified working with a real API call before wiring in.

## Testing

pytest, 188 test functions / 23 files, 92% coverage (CI gate: 80%). `tests/fakes.py::FakeProvider` mocks the LLM everywhere — no real API calls in the suite. `tests/fixtures/torture.py` has 20+ malformed-file generators for ingestion tests. Two Streamlit `AppTest`-based integration tests drive real UI flows including the register→upload→all-tabs journey. Run: `pytest -m "not slow"`.

## Known limitations (do not claim these exist)

- No S3 backend (config option exists, raises `NotImplementedError`)
- No REST API
- No password reset
- No multi-user/team features
- `MAX_CHART_POINTS` constant is defined but never used (dead code — no chart downsampling)
- No `st.cache_data`/`st.cache_resource` anywhere — every Streamlit rerun reloads from Parquet
- Live deployment loses all data on redeploy (ephemeral SQLite, no disk)
- Chat has no non-LLM fallback (unlike insights) — raises `LLMUnavailableError` outright

## Extension points (designed for this)

- `LLMProvider` Protocol — add a provider by implementing `complete()`, or in most cases (any OpenAI-compatible API) just set `LLM_BASE_URL`, no new class needed.
- `StorageBackend` Protocol — implement `S3Storage` matching `storage/base.py`'s protocol to add real persistence; `get_storage()` already has the `"s3"` branch stubbed to wire it in.
- `services/*` signatures are deliberately REST-route-shaped (`user_id`, `project_id` first params, typed DTO returns) — written so a FastAPI layer could mount onto them later per `ARCHITECTURE.md`'s stated intent.

## Common pitfalls (things that already caused real bugs this session)

1. **Two separate chart renderers exist** (`core/dashboard/figures.py` for Plotly/UI, `core/dashboard/report_images.py` for matplotlib/PDF). Adding a chart type to one without the other means it silently won't appear in reports (or the UI).
2. **`st.chat_message(avatar=...)` only accepts a real emoji or an image path** — passing an arbitrary Unicode glyph (e.g. the brand's `◆`) throws `MediaFileStorageError`. Caused a production crash (fixed in commit `aed4b76`).
3. **`session_scope()` rolls back on any raised exception** — if you need to persist state (e.g. a failed-login counter) before raising a user-facing error, call `s.commit()` explicitly before `raise`, or the write is lost (this was a real bug in `auth_service.login()`, fixed before release).
4. **Time-series resampling can produce partial edge buckets** (an incomplete first/last week or month) that skew backtest MAPE badly (117% observed before the fix). `prepare_series()` in `core/forecasting/preparer.py` trims these — don't bypass it.
5. **Kaleido (Plotly's static-image exporter) is not used and should not be reintroduced** for server-side rendering — it hung reproducibly during development. Use `report_images.py`'s matplotlib path for anything that needs a chart PNG.
6. **Tests that touch `Settings` via `monkeypatch.setenv` must call `get_settings.cache_clear()`** (and `get_engine.cache_clear()` / `get_storage.cache_clear()` if those are affected) — the `isolated_settings` autouse fixture in `tests/conftest.py` already does this per-test, but a manual `monkeypatch` mid-test still needs a manual cache-clear.
7. **`OPENAI_API_KEY` is the credential field name regardless of provider** — when using Groq or any other OpenAI-compatible service, the actual provider key still goes in `OPENAI_API_KEY`; `LLM_BASE_URL` is what redirects it.

## Repository conventions

- Conventional-ish commit prefixes: `feat:`, `fix:`, `release:`, `merge:`. Git flow: `feature/mN-*` branches → `develop` → `main`, tagged per release (`v0.1.0-m0` ... `v1.0.5` as of this writing).
- `ruff format` + `ruff check` (line length 100), `mypy` (strict-ish; `ui/` has `disallow_untyped_defs = false` relaxed), `lint-imports` (layer contracts), `pytest -m "not slow"` — all four must pass; this is what CI runs.
- No TODO/FIXME/HACK comments anywhere in `src/` as of this writing — if you leave one, you're the first.
