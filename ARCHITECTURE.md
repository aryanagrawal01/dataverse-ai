# DataVerse AI — Software Architecture & Product Design Document

| | |
|---|---|
| **Version** | 1.0 (Draft for approval) |
| **Date** | 2026-07-17 |
| **Status** | Awaiting approval — no application code written yet |
| **Author** | Engineering (with Claude Code) |

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Target Users](#2-target-users)
3. [User Journeys](#3-user-journeys)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Complete Feature Breakdown](#6-complete-feature-breakdown)
7. [Technology Stack Decisions](#7-technology-stack-decisions)
8. [Folder Structure](#8-folder-structure)
9. [Database Schema](#9-database-schema)
10. [API Design (Service Layer Contracts)](#10-api-design-service-layer-contracts)
11. [System Architecture](#11-system-architecture)
12. [Data Flow Diagrams](#12-data-flow-diagrams)
13. [Module Dependency Diagram](#13-module-dependency-diagram)
14. [UI Page Hierarchy](#14-ui-page-hierarchy)
15. [Wireframes](#15-wireframes)
16. [Security Considerations](#16-security-considerations)
17. [Error Handling Strategy](#17-error-handling-strategy)
18. [Logging Strategy](#18-logging-strategy)
19. [Testing Strategy](#19-testing-strategy)
20. [Deployment Strategy](#20-deployment-strategy)
21. [Git Branching Strategy](#21-git-branching-strategy)
22. [Development Roadmap & Milestones](#22-development-roadmap--milestones)
23. [Future Enhancements](#23-future-enhancements)
24. [Risks and Trade-offs](#24-risks-and-trade-offs)

---

## 1. Product Overview

**DataVerse AI** is an AI-powered Business Intelligence platform that turns raw spreadsheets into decisions. A user uploads a CSV or Excel file; the platform profiles it, detects and fixes data quality issues (with the user in the loop), auto-generates interactive dashboards, produces AI-written business insights, forecasts time-series metrics, answers natural-language questions about the data, and exports polished PDF reports.

**Value proposition:** "From spreadsheet to boardroom insight in under two minutes — no SQL, no Python, no analyst required."

**What makes it credible as a commercial SaaS:**

- The user never sees a raw stack trace or an empty screen — every state (loading, empty, error, partial) is designed.
- Cleaning is transparent and reversible: every transformation is logged, previewable, and can be accepted or rejected per-rule.
- AI output is grounded: insights and chat answers are computed from the actual data (deterministic aggregations), with the LLM used for language and reasoning — not for arithmetic. This eliminates hallucinated numbers.
- Multi-project persistence: users return to previous work, exactly as a real product requires.

**Explicit non-goals for v1** (to keep scope honest):

- No multi-user collaboration/sharing within an organization.
- No live database/warehouse connectors (files only).
- No scheduled refresh of data.
- No row-level permissions.
- These are captured in [Future Enhancements](#23-future-enhancements).

---

## 2. Target Users

| Persona | Description | Primary needs | Success looks like |
|---|---|---|---|
| **Priya — Small business owner** | Runs an e-commerce shop; exports sales from Shopify to Excel. No technical skills. | "Tell me what's happening in my business." | Uploads file, reads executive summary, acts on 2–3 recommendations. |
| **Marcus — Business analyst** | Mid-size company; drowning in ad-hoc report requests. Knows Excel, not Python. | Speed. Turn a stakeholder's file into a dashboard + report in minutes. | Exports a branded PDF he can forward without editing. |
| **Sofia — Startup founder / PM** | Needs investor-facing metrics and trends from product/revenue exports. | Forecasts and trend narratives she can drop into a deck. | Forecast chart + AI narrative in her pitch appendix. |
| **Dev — Data-curious student / job seeker** | Wants to explore datasets without environment setup. | Zero-friction exploration and "chat with data." | Asks 10 questions, gets grounded answers with charts. |
| **Recruiter / reviewer (meta-persona)** | Evaluates the project as a portfolio piece. | Evidence of engineering maturity: architecture, tests, error handling, polish. | Reads this doc, clones repo, everything runs with one command. |

---

## 3. User Journeys

### Journey A — First-time user, first insight (the "aha" path)

```
Landing → Register → Email/password created → Onboarding empty state
→ "Upload your first dataset" (drag-and-drop or sample dataset button)
→ Upload progress bar → Profiling spinner with step indicators
→ Data Health Report ("87/100 — 3 issues found")
→ Review cleaning suggestions (accept all / per-rule toggle)
→ "Apply cleaning" → Before/After comparison
→ Auto-generated dashboard renders
→ AI Insights panel populates (streamed)
→ User asks in chat: "Which region underperformed last quarter?"
→ Answer with supporting chart
→ Export PDF report → Done
```
Target time from registration to first dashboard: **< 3 minutes**.

### Journey B — Returning user

```
Login → Projects list (cards: name, date, row count, health score)
→ Open project → Dashboard restored from stored cleaned data
→ Continue chat (history preserved) → Download cleaned CSV
```

### Journey C — Data with quality problems

```
Upload messy file → Profiling flags: 12% missing in `revenue`,
340 duplicate rows, `date` stored as text, 5 extreme outliers
→ User reviews each suggestion, rejects outlier removal (they're real Black
  Friday spikes), accepts the rest
→ Cleaning log records decisions → Dashboard built on cleaned data
```

### Journey D — Unsupported / bad input (failure path is a journey too)

```
Upload a PDF → Friendly rejection with supported formats listed
Upload a 900 MB CSV → Clear size-limit message with guidance (sample or split)
Upload an Excel with 6 sheets → Sheet picker appears
Upload a file with no numeric columns → Dashboard adapts (categorical-only
  charts), forecasting tab explains why it is unavailable
```

### Journey E — Forecasting

```
Open project with a detected date column + numeric metric
→ Forecast tab → Select metric + horizon (e.g., 90 days)
→ Model fits with backtest → Chart: history, forecast, confidence band
→ AI narrative: "Revenue is projected to grow 8% next quarter, driven by…"
```

---

## 4. Functional Requirements

Requirements use MoSCoW priority. FR-IDs are referenced by the roadmap and test plan.

### 4.1 Authentication (AUTH)

| ID | Requirement | Priority |
|---|---|---|
| FR-AUTH-1 | Register with email + password (validated: format, strength ≥ 8 chars incl. number) | Must |
| FR-AUTH-2 | Login with email + password | Must |
| FR-AUTH-3 | Passwords stored as bcrypt hashes; never logged or displayed | Must |
| FR-AUTH-4 | Server-side sessions with signed token, idle timeout (60 min), explicit logout | Must |
| FR-AUTH-5 | Rate-limit login attempts (5 failures → 15-min lockout) | Should |
| FR-AUTH-6 | Password reset via emailed token | Could (v1.1) |

### 4.2 File Upload (UPL)

| ID | Requirement | Priority |
|---|---|---|
| FR-UPL-1 | Accept `.csv`, `.xlsx`, `.xls` via drag-and-drop or browse | Must |
| FR-UPL-2 | Validate extension, MIME sniff, and parseability before accepting | Must |
| FR-UPL-3 | Enforce configurable size limit (default 100 MB) with clear messaging | Must |
| FR-UPL-4 | Excel multi-sheet: present sheet picker | Must |
| FR-UPL-5 | Encoding detection (UTF-8, Latin-1, UTF-16) and delimiter sniffing for CSV | Must |
| FR-UPL-6 | Progress indication during upload and parse | Should |
| FR-UPL-7 | Offer bundled sample datasets for instant demo | Should |

### 4.3 Data Profiling (PRF)

| ID | Requirement | Priority |
|---|---|---|
| FR-PRF-1 | Dataset summary: rows, columns, memory, duplicate count | Must |
| FR-PRF-2 | Per-column: inferred semantic type (numeric / categorical / datetime / text / boolean / ID), missing %, unique count, sample values | Must |
| FR-PRF-3 | Statistical summary for numeric columns (mean, median, std, min/max, quartiles, skew) | Must |
| FR-PRF-4 | Correlation matrix (Pearson + Spearman) for numeric columns | Must |
| FR-PRF-5 | Outlier detection per numeric column (IQR and z-score; IsolationForest for multivariate) | Must |
| FR-PRF-6 | Composite Data Health Score (0–100) with issue breakdown | Should |
| FR-PRF-7 | Datetime column detection incl. text-formatted dates | Must |

### 4.4 Automated Cleaning (CLN)

| ID | Requirement | Priority |
|---|---|---|
| FR-CLN-1 | Suggest cleaning actions per detected issue; user accepts/rejects each | Must |
| FR-CLN-2 | Remove exact duplicate rows | Must |
| FR-CLN-3 | Impute missing values (numeric: median/mean; categorical: mode/"Unknown"; datetime: interpolate/drop — strategy per column, user-overridable) | Must |
| FR-CLN-4 | Type coercion: text→numeric (strip currency symbols, thousands separators), text→datetime, text→boolean | Must |
| FR-CLN-5 | Outlier handling options: keep / cap (winsorize) / remove — default **keep** (conservative) | Must |
| FR-CLN-6 | Immutable cleaning log: rule, params, rows affected, timestamp | Must |
| FR-CLN-7 | Before/After comparison view (metrics + sample diff) | Must |
| FR-CLN-8 | Raw file always preserved; cleaning re-runnable from raw | Must |

### 4.5 Dashboard Generator (DSH)

| ID | Requirement | Priority |
|---|---|---|
| FR-DSH-1 | Auto-select charts from column semantics (rules engine, deterministic) | Must |
| FR-DSH-2 | KPI cards: total, average, count, growth % for detected metric columns | Must |
| FR-DSH-3 | Time-series chart when datetime + numeric present | Must |
| FR-DSH-4 | Categorical breakdowns (top-N bar, share donut) | Must |
| FR-DSH-5 | Distribution plots (histogram/box) for key numerics | Must |
| FR-DSH-6 | Correlation heatmap | Must |
| FR-DSH-7 | Interactive charts (hover, zoom, legend toggle) via Plotly | Must |
| FR-DSH-8 | Global filters (date range, top categorical) applied across dashboard | Should |
| FR-DSH-9 | Graceful degradation when expected column types are absent | Must |

### 4.6 AI Insights (INS)

| ID | Requirement | Priority |
|---|---|---|
| FR-INS-1 | Executive summary (3–5 sentences, business language) | Must |
| FR-INS-2 | Trend insights, anomaly callouts, segment comparisons, concentration risks | Must |
| FR-INS-3 | Suggested business actions (recommendations) | Must |
| FR-INS-4 | All numbers in insights computed deterministically by the stats engine; LLM writes narrative around supplied facts only | Must |
| FR-INS-5 | Insights cached per dataset version; regenerate on demand | Should |
| FR-INS-6 | Graceful degradation if LLM unavailable (template-based insights) | Should |

### 4.7 Chat with Data (CHT)

| ID | Requirement | Priority |
|---|---|---|
| FR-CHT-1 | Natural-language questions answered from the cleaned dataset | Must |
| FR-CHT-2 | LLM translates question → structured query plan (JSON DSL) → deterministic pandas executor. LLM never free-writes numbers | Must |
| FR-CHT-3 | Answers include supporting table/chart when applicable | Must |
| FR-CHT-4 | Conversation history persisted per project | Must |
| FR-CHT-5 | "I can't answer that from this data" fallback with reason | Must |
| FR-CHT-6 | Suggested starter questions generated from schema | Should |

### 4.8 Forecasting (FCT)

| ID | Requirement | Priority |
|---|---|---|
| FR-FCT-1 | Available only when a datetime column + numeric metric with ≥ 2× seasonal-period observations exist; otherwise explain why | Must |
| FR-FCT-2 | Auto-aggregate to a sensible frequency (daily/weekly/monthly) | Must |
| FR-FCT-3 | Model selection: seasonal-naive baseline vs Holt-Winters vs SARIMA, chosen by backtest MAPE on holdout | Must |
| FR-FCT-4 | Output: point forecast + 80/95% intervals, plotted with history | Must |
| FR-FCT-5 | Display backtest accuracy honestly ("±12% typical error") | Should |
| FR-FCT-6 | AI narrative for the forecast | Should |

### 4.9 Reports (RPT)

| ID | Requirement | Priority |
|---|---|---|
| FR-RPT-1 | PDF export: cover, executive summary, KPIs, charts, insights, recommendations, cleaning appendix | Must |
| FR-RPT-2 | Charts rendered as static images (matplotlib Agg; Kaleido rejected during M5 — see §7) | Must |
| FR-RPT-3 | PowerPoint export (python-pptx) | Could (v1.1) |
| FR-RPT-4 | Report generation is async-feeling (progress indicator) | Should |

### 4.10 Project History (PRJ)

| ID | Requirement | Priority |
|---|---|---|
| FR-PRJ-1 | List user's projects (name, created date, rows, health score, status) | Must |
| FR-PRJ-2 | Reopen a project: dashboard, insights, chat restored | Must |
| FR-PRJ-3 | Download cleaned dataset as CSV | Must |
| FR-PRJ-4 | Rename and delete projects (delete = confirm dialog, removes files + rows) | Must |
| FR-PRJ-5 | Per-user storage quota (default 500 MB) with usage indicator | Should |

---

## 5. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| **Performance** | Profiling of a 100 MB / 1M-row CSV | < 30 s |
| | Dashboard render after project open | < 3 s |
| | Chat answer latency | < 10 s p90 |
| | Charts downsample above 50k points (LTTB / aggregation) | Always |
| **Scalability** | Stateless app tier; dataset files on object storage; DB holds metadata only | Design-level |
| | Concurrent users on a single 2-CPU/4GB node | 25+ |
| **Reliability** | LLM outage degrades features, never breaks upload/profile/dashboard | Must |
| | No data loss: raw file immutable once stored | Must |
| **Security** | See [Section 16](#16-security-considerations) | Must |
| **Privacy** | Only schema + aggregates sent to LLM by default; raw-row sampling to LLM is opt-in and capped | Must |
| **Usability** | All empty/loading/error states designed; no raw tracebacks in UI | Must |
| **Maintainability** | Type-hinted Python, ruff + mypy clean, ≥ 80% coverage on core/services | Must |
| **Portability** | Runs locally with SQLite + local disk, zero cloud dependencies (LLM optional) | Must |
| **Observability** | Structured JSON logs, request IDs, LLM token/cost accounting | Must |
| **Cost** | LLM spend per project capped (config, default $0.25) | Should |

---

## 6. Complete Feature Breakdown

Feature → module mapping (modules defined in [Section 8](#8-folder-structure)):

| # | Feature | Sub-features | Owning module(s) |
|---|---|---|---|
| 1 | Authentication | register, login, logout, session, lockout | `services/auth`, `ui/pages/auth` |
| 2 | Upload & Ingestion | validation, encoding/delimiter sniff, sheet picker, Parquet conversion, sampling | `services/ingestion` |
| 3 | Profiling | summary, column typing, stats, correlations, outliers, health score | `core/profiling` |
| 4 | Cleaning | suggestion engine, rule executor, log, before/after | `core/cleaning`, `services/pipeline` |
| 5 | Dashboarding | chart rules engine, KPI computation, filters, Plotly builders | `core/dashboard`, `ui/components/charts` |
| 6 | AI Insights | fact extraction, prompt assembly, narrative generation, caching | `core/insights`, `llm/` |
| 7 | Chat with Data | intent → query-plan DSL, safe executor, answer composer, history | `core/chat`, `llm/` |
| 8 | Forecasting | frequency detection, model zoo, backtesting, intervals | `core/forecasting` |
| 9 | Reports | layout templates, chart snapshotting, PDF assembly | `services/reports` |
| 10 | Projects | CRUD, artifact storage, quota | `services/projects`, `repositories/` |
| 11 | Platform | config, logging, errors, storage abstraction | `utils/`, `config/`, `storage/` |

---

## 7. Technology Stack Decisions

Every deviation from the suggested stack is justified here, per the brief.

| Concern | Choice | Rationale / alternatives considered |
|---|---|---|
| Language | **Python 3.12** | As suggested. Entire data/AI ecosystem lives here. |
| UI | **Streamlit (multipage) + custom theming** | Kept as suggested — it is the right call for a solo-built v1: fastest path to a polished data app, native Plotly/pandas integration. The known trade-off (limited UI control, rerun model) is mitigated by strict service-layer separation so a **FastAPI + Next.js** frontend can replace it in v2 without touching business logic. Building React now would double the timeline for marginal portfolio gain. Trade-off logged in [Section 24](#24-risks-and-trade-offs). |
| Dataframes | **Pandas 2.x (PyArrow-backed)** | As suggested. Polars considered (faster) but pandas keeps the widest library compatibility (sklearn, statsmodels, Plotly). Revisit if >1M-row files become common. |
| Charts | **Plotly** (interactive UI) + **matplotlib Agg** (static PDF images) | Plotly as suggested for the UI. **Kaleido rejected during implementation:** its bundled headless Chromium hung intermittently on the dev host (OneDrive-synced paths) — an unacceptable reliability risk for server-side rendering. Matplotlib is pure Python and deterministic. |
| ML / stats | **scikit-learn + statsmodels** | statsmodels added: Holt-Winters/SARIMA are the correct forecasting tools; sklearn alone lacks them. Prophet rejected (heavy dependency, marginal gain). |
| Metadata DB | **PostgreSQL (prod) / SQLite (dev)** via **SQLAlchemy 2.0 + Alembic** | As suggested, with SQLite fallback so the repo runs with zero setup. Alembic added for migrations — non-negotiable for a real product. |
| Dataset storage | **Parquet files on a storage abstraction** (local disk dev, S3-compatible prod) | **Deviation:** datasets do NOT go into Postgres. Storing millions of rows relationally is slow and bloats the DB; Parquet is columnar, compressed, and pandas-native. DB stores metadata + file pointers only. |
| LLM | **OpenAI API (`gpt-4o-mini` default) behind an internal `LLMProvider` interface** | As suggested, but wrapped: one adapter module owns all API calls, so switching/adding providers (Anthropic, local) is a one-file change, and the whole app degrades gracefully without a key. |
| Auth | **Custom: bcrypt (passlib) + itsdangerous-signed session tokens** | `streamlit-authenticator` rejected: YAML-file credentials, no DB integration, weak session semantics. Custom is ~200 lines and demonstrates security literacy. |
| PDF | **ReportLab + Kaleido images** | WeasyPrint rejected: native GTK dependencies are painful on Windows/containers. ReportLab is pure-Python and precise. |
| Validation/config | **Pydantic v2 + pydantic-settings** | Typed request/response DTOs and env-var config with validation. |
| Migrations | **Alembic** | Schema evolution from day one. |
| Lint/format/type | **ruff, mypy** | Modern, fast, standard. |
| Tests | **pytest + pytest-cov + hypothesis** (property tests for cleaning rules) | See [Section 19](#19-testing-strategy). |
| Container | **Docker + docker-compose** (app + Postgres) | One-command run. |
| Deployment | **Render** (first), Docker image portable to Azure/AWS | Free tier, Postgres add-on, zero-ops. |
| CI | **GitHub Actions** | Lint → type-check → test → build image. |

---

## 8. Folder Structure

```
dataverse-ai/
├── app.py                          # Streamlit entrypoint (thin: routing + session bootstrap)
├── pyproject.toml                  # deps, ruff/mypy/pytest config (single source)
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── .env.example                    # every env var documented, no secrets
├── .github/
│   └── workflows/ci.yml
├── ARCHITECTURE.md                 # this document
├── README.md                       # screenshots, quickstart, badge row
│
├── src/dataverse/
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py             # pydantic-settings: env vars, limits, feature flags
│   │   └── constants.py
│   │
│   ├── models/                     # SQLAlchemy ORM models (DB schema, Section 9)
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── dataset_version.py
│   │   ├── cleaning_log.py
│   │   ├── insight.py
│   │   ├── chat.py
│   │   ├── forecast.py
│   │   └── report.py
│   │
│   ├── schemas/                    # Pydantic DTOs crossing layer boundaries
│   │   ├── profiling.py            # ColumnProfile, DatasetProfile, HealthScore
│   │   ├── cleaning.py             # CleaningSuggestion, CleaningPlan, CleaningResult
│   │   ├── dashboard.py            # ChartSpec, KpiSpec, DashboardSpec
│   │   ├── chat.py                 # QueryPlan DSL, ChatAnswer
│   │   ├── insights.py             # FactPack, InsightSet
│   │   └── forecast.py             # ForecastRequest, ForecastResult
│   │
│   ├── repositories/               # DB access only; no business logic
│   │   ├── base.py                 # session management, generic CRUD
│   │   ├── user_repo.py
│   │   ├── project_repo.py
│   │   ├── chat_repo.py
│   │   └── artifact_repo.py
│   │
│   ├── storage/                    # file storage abstraction
│   │   ├── base.py                 # StorageBackend protocol: put/get/delete/url
│   │   ├── local.py                # dev: ./data/ on disk
│   │   └── s3.py                   # prod: S3-compatible
│   │
│   ├── core/                       # pure business logic — NO Streamlit, NO DB imports
│   │   ├── profiling/
│   │   │   ├── profiler.py         # orchestrates column typing, stats, health score
│   │   │   ├── type_inference.py
│   │   │   ├── outliers.py
│   │   │   └── correlations.py
│   │   ├── cleaning/
│   │   │   ├── suggester.py        # profile → List[CleaningSuggestion]
│   │   │   ├── rules/              # one class per rule (Strategy pattern)
│   │   │   │   ├── base.py         # CleaningRule ABC: preview() / apply()
│   │   │   │   ├── deduplicate.py
│   │   │   │   ├── impute.py
│   │   │   │   ├── coerce_types.py
│   │   │   │   └── outlier_handler.py
│   │   │   └── executor.py         # applies accepted plan, emits log entries
│   │   ├── dashboard/
│   │   │   ├── chart_rules.py      # semantics → ChartSpec list (deterministic)
│   │   │   └── kpi_engine.py
│   │   ├── insights/
│   │   │   ├── fact_extractor.py   # computes FactPack (all numbers, deterministic)
│   │   │   └── narrator.py         # FactPack + LLM → prose; template fallback
│   │   ├── chat/
│   │   │   ├── planner.py          # question + schema + LLM → QueryPlan (JSON DSL)
│   │   │   ├── executor.py         # QueryPlan → pandas ops (whitelisted, sandboxed)
│   │   │   └── composer.py         # result + LLM → natural-language answer + chart
│   │   └── forecasting/
│   │       ├── preparer.py         # frequency detection, aggregation, gap filling
│   │       ├── models.py           # baseline / Holt-Winters / SARIMA wrappers
│   │       └── selector.py         # backtest + pick best by MAPE
│   │
│   ├── llm/
│   │   ├── provider.py             # LLMProvider protocol
│   │   ├── openai_provider.py      # the ONLY file importing the openai SDK
│   │   ├── null_provider.py        # degraded mode: returns templates
│   │   ├── prompts/                # versioned prompt templates (jinja2, .j2 files)
│   │   └── budget.py               # token/cost accounting + per-project cap
│   │
│   ├── services/                   # orchestration: core + repos + storage + llm
│   │   ├── auth_service.py
│   │   ├── ingestion_service.py    # validate → parse → Parquet → raw version row
│   │   ├── pipeline_service.py     # profile → suggest → clean → cleaned version
│   │   ├── project_service.py
│   │   ├── insight_service.py      # caching wrapper over core.insights
│   │   ├── chat_service.py
│   │   ├── forecast_service.py
│   │   └── report_service.py       # ReportLab assembly
│   │
│   ├── ui/                         # ALL Streamlit code lives here and only here
│   │   ├── theme.py                # design tokens, CSS injection
│   │   ├── state.py                # typed accessors over st.session_state
│   │   ├── guards.py               # @require_auth, project-ownership checks
│   │   ├── components/
│   │   │   ├── charts.py           # ChartSpec → Plotly figure (single renderer)
│   │   │   ├── kpi_cards.py
│   │   │   ├── health_badge.py
│   │   │   ├── cleaning_review.py
│   │   │   ├── chat_panel.py
│   │   │   └── empty_states.py
│   │   └── pages_impl/             # page bodies (pages/ folder holds thin stubs)
│   │       ├── login.py
│   │       ├── projects.py
│   │       ├── upload.py
│   │       ├── data_health.py
│   │       ├── dashboard.py
│   │       ├── insights.py
│   │       ├── chat.py
│   │       ├── forecast.py
│   │       └── reports.py
│   │
│   └── utils/
│       ├── logging.py              # structlog setup, request-id context
│       ├── errors.py               # exception hierarchy (Section 17)
│       ├── security.py             # hashing, token signing, sanitization
│       └── dataframe.py            # downsampling, memory helpers
│
├── migrations/                     # Alembic versions
├── sample_data/                    # bundled demo datasets (sales, marketing, HR)
├── scripts/
│   ├── seed.py                     # demo user + sample project
│   └── create_admin.py
└── tests/
    ├── unit/                       #   mirrors core/ and services/
    ├── integration/                # DB + storage + pipeline end-to-end
    ├── fixtures/                   # crafted messy CSVs/Excels (the "torture suite")
    └── conftest.py
```

**Layering law (enforced by import-linter in CI):**
`ui → services → (core | repositories | storage | llm) → schemas/models/utils`.
`core/` never imports Streamlit, SQLAlchemy, or the OpenAI SDK. This is what makes the v2 FastAPI migration and unit testing cheap.

---

## 9. Database Schema

PostgreSQL (SQLite-compatible types). All PKs are UUIDs; all tables have `created_at` / `updated_at`.

```sql
users
├── id                UUID PK
├── email             VARCHAR(255) UNIQUE NOT NULL
├── password_hash     VARCHAR(255) NOT NULL          -- bcrypt
├── display_name      VARCHAR(100)
├── is_active         BOOLEAN DEFAULT TRUE
├── failed_logins     SMALLINT DEFAULT 0
├── locked_until      TIMESTAMPTZ NULL
└── last_login_at     TIMESTAMPTZ NULL

sessions
├── id                UUID PK                        -- session token id (signed client-side)
├── user_id           UUID FK → users ON DELETE CASCADE
├── expires_at        TIMESTAMPTZ NOT NULL
└── revoked           BOOLEAN DEFAULT FALSE

projects
├── id                UUID PK
├── user_id           UUID FK → users ON DELETE CASCADE
├── name              VARCHAR(120) NOT NULL
├── status            VARCHAR(20)  -- uploaded|profiled|cleaned|ready|failed
├── source_filename   VARCHAR(255)
├── health_score      SMALLINT NULL
├── row_count         INTEGER
├── column_count      SMALLINT
└── deleted_at        TIMESTAMPTZ NULL               -- soft delete; purge job hard-deletes

dataset_versions                                     -- raw and cleaned are both versions
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── kind              VARCHAR(10)  -- 'raw' | 'cleaned'
├── storage_key       VARCHAR(500) NOT NULL          -- Parquet path in storage backend
├── row_count         INTEGER
├── size_bytes        BIGINT
├── profile_json      JSONB        -- full DatasetProfile (schemas/profiling.py)
└── UNIQUE (project_id, kind)

cleaning_logs
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── rule_name         VARCHAR(50)                    -- 'deduplicate', 'impute', ...
├── params_json       JSONB                          -- column, strategy, threshold...
├── rows_affected     INTEGER
├── accepted          BOOLEAN                        -- user decision recorded
└── applied_at        TIMESTAMPTZ

insights
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── dataset_version_id UUID FK → dataset_versions
├── kind              VARCHAR(30)  -- executive_summary|trend|anomaly|recommendation
├── content           TEXT
├── facts_json        JSONB        -- the FactPack numbers backing this insight
└── model_used        VARCHAR(50)

chat_messages
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── role              VARCHAR(10)  -- 'user' | 'assistant'
├── content           TEXT
├── query_plan_json   JSONB NULL   -- the executed DSL (auditability)
└── chart_spec_json   JSONB NULL

forecasts
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── metric_column     VARCHAR(120)
├── frequency         VARCHAR(10)  -- D|W|M
├── horizon           SMALLINT
├── model_name        VARCHAR(40)
├── backtest_mape     NUMERIC(6,3)
└── result_json       JSONB        -- points + intervals

reports
├── id                UUID PK
├── project_id        UUID FK → projects ON DELETE CASCADE
├── format            VARCHAR(10)  -- 'pdf' | 'pptx'
├── storage_key       VARCHAR(500)
└── size_bytes        BIGINT

llm_usage                                            -- cost accounting
├── id                UUID PK
├── user_id           UUID FK → users
├── project_id        UUID FK → projects NULL
├── feature           VARCHAR(30)  -- insights|chat|forecast_narrative
├── model             VARCHAR(50)
├── prompt_tokens     INTEGER
├── completion_tokens INTEGER
└── cost_usd          NUMERIC(10,6)
```

**Indexes:** `projects(user_id, deleted_at)`, `chat_messages(project_id, created_at)`, `sessions(user_id)`, `llm_usage(user_id, created_at)`, `insights(project_id, dataset_version_id)`.

**Design notes:**
- Dataframes never enter the DB — `storage_key` points at Parquet artifacts. DB stays small and fast.
- `profile_json` denormalized as JSONB: profiles are read-whole, never queried relationally.
- Soft delete on projects gives an undo window; a purge job hard-deletes rows + storage artifacts after 7 days.

---

## 10. API Design (Service Layer Contracts)

v1 is a Streamlit monolith, so the "API" is the **service layer** — typed Python contracts that the UI calls. These signatures are written REST-shaped on purpose: in v2 they mount 1:1 onto FastAPI routes (shown right column) without changing internals.

| Service method | Contract | Future REST mapping |
|---|---|---|
| `auth.register(email, password) -> UserDTO` | raises `EmailTakenError`, `WeakPasswordError` | `POST /api/v1/auth/register` |
| `auth.login(email, password) -> SessionToken` | raises `InvalidCredentialsError`, `AccountLockedError` | `POST /api/v1/auth/login` |
| `auth.logout(token) -> None` | | `POST /api/v1/auth/logout` |
| `projects.list(user_id) -> list[ProjectSummary]` | | `GET /api/v1/projects` |
| `projects.get(user_id, project_id) -> ProjectDetail` | raises `NotFoundError` (also when not owner — no existence leak) | `GET /api/v1/projects/{id}` |
| `projects.delete(user_id, project_id) -> None` | soft delete | `DELETE /api/v1/projects/{id}` |
| `ingestion.upload(user_id, file, sheet=None) -> ProjectDetail` | validates, parses, stores raw Parquet | `POST /api/v1/projects` (multipart) |
| `pipeline.profile(project_id) -> DatasetProfile` | | `POST /api/v1/projects/{id}/profile` |
| `pipeline.suggest_cleaning(project_id) -> list[CleaningSuggestion]` | | `GET /api/v1/projects/{id}/cleaning/suggestions` |
| `pipeline.apply_cleaning(project_id, plan: CleaningPlan) -> CleaningResult` | plan = accepted suggestion IDs + overrides | `POST /api/v1/projects/{id}/cleaning/apply` |
| `dashboard.build(project_id, filters) -> DashboardSpec` | pure spec; UI renders it | `GET /api/v1/projects/{id}/dashboard` |
| `insights.generate(project_id, force=False) -> InsightSet` | cached by dataset version | `POST /api/v1/projects/{id}/insights` |
| `chat.ask(project_id, question) -> ChatAnswer` | answer + optional ChartSpec + QueryPlan audit | `POST /api/v1/projects/{id}/chat` |
| `forecast.run(project_id, req: ForecastRequest) -> ForecastResult` | raises `ForecastNotApplicableError(reason)` | `POST /api/v1/projects/{id}/forecast` |
| `reports.generate(project_id, fmt) -> ReportHandle` | | `POST /api/v1/projects/{id}/reports` |
| `projects.download_cleaned(project_id) -> bytes` | streams CSV | `GET /api/v1/projects/{id}/export.csv` |

### The Chat Query-Plan DSL (core safety contract)

The LLM never executes code and never sees full raw data. It emits a constrained JSON plan validated by Pydantic, executed by a whitelisted pandas interpreter:

```json
{
  "operation": "aggregate",
  "metrics":   [{"column": "revenue", "agg": "sum"}],
  "group_by":  ["region"],
  "filters":   [{"column": "date", "op": "between",
                 "value": ["2026-01-01", "2026-03-31"]}],
  "sort":      {"by": "revenue_sum", "dir": "desc"},
  "limit":     10,
  "chart_hint": "bar"
}
```

Allowed operations: `aggregate`, `filter_rows`, `top_n`, `compare_periods`, `trend`, `describe`, `correlate`. Column names are validated against the actual schema; anything else → clarification request to the user. No `eval`, no generated code execution.

---

## 11. System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                           USER (browser)                           │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ HTTPS
┌─────────────────────────────▼──────────────────────────────────────┐
│                    STREAMLIT APP (stateless tier)                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ UI layer: pages, components, theme, session guards           │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│  ┌───────────────────────────▼──────────────────────────────────┐  │
│  │ SERVICE layer: auth · ingestion · pipeline · project ·       │  │
│  │                insight · chat · forecast · report            │  │
│  └───┬───────────────┬───────────────┬────────────────┬─────────┘  │
│  ┌───▼─────────┐ ┌───▼──────────┐ ┌──▼───────────┐ ┌──▼─────────┐  │
│  │ CORE        │ │ REPOSITORIES │ │ STORAGE      │ │ LLM        │  │
│  │ profiling   │ │ (SQLAlchemy) │ │ abstraction  │ │ provider   │  │
│  │ cleaning    │ │              │ │              │ │ + budget   │  │
│  │ dashboard   │ │              │ │              │ │            │  │
│  │ insights    │ │              │ │              │ │            │  │
│  │ chat        │ │              │ │              │ │            │  │
│  │ forecasting │ │              │ │              │ │            │  │
│  └─────────────┘ └───┬──────────┘ └──┬───────────┘ └──┬─────────┘  │
└──────────────────────┼───────────────┼────────────────┼────────────┘
                       │               │                │
              ┌────────▼──────┐ ┌──────▼────────┐ ┌─────▼──────────┐
              │ PostgreSQL    │ │ Object store  │ │ OpenAI API     │
              │ (metadata)    │ │ Parquet/PDF   │ │ (optional —    │
              │               │ │ local FS/S3   │ │  degrades off) │
              └───────────────┘ └───────────────┘ └────────────────┘
```

**Key properties**

- **Stateless app tier:** all durable state in Postgres + object storage; session identity in a signed token. Horizontal scaling = add replicas behind a load balancer.
- **Dataframe lifecycle:** raw upload → Parquet (immutable) → cleaned Parquet (immutable). Loaded into memory per request with an LRU cache keyed by `storage_key`; large frames auto-downsample for display while stats run on full data.
- **LLM as a leaf dependency:** nothing upstream depends on it succeeding. Every LLM feature has a deterministic fallback path.
- **Heavy work in-process for v1** (profiling ≤ 30 s) with progress UI; the service seam allows moving `pipeline`/`report` to a Celery/RQ worker in v2 without interface changes.

---

## 12. Data Flow Diagrams

### DFD-1: Upload → Ready (the core pipeline)

```
 [file]                                                      DB writes
   │                                                            │
   ▼                                                            ▼
┌──────────┐  bytes  ┌───────────┐ DataFrame ┌───────────┐  profile_json
│ Validate │────────►│ Parse     │──────────►│ Profile   │────────────┐
│ ext/size │         │ sniff enc │           │ types,    │            │
│ MIME     │         │ delimiter │           │ stats,    │            ▼
└────┬─────┘         │ sheets    │           │ outliers  │      ┌───────────┐
     │ reject         └─────┬─────┘           └─────┬─────┘      │ Suggest   │
     ▼                      │ raw.parquet           │            │ cleaning  │
 [friendly               [storage]                  │            └─────┬─────┘
  error]                                            │                  │ user
                                                    │                  ▼ reviews
┌───────────┐ cleaned.parquet ┌───────────┐   ┌───────────────────────────┐
│ Dashboard │◄────────────────│ Execute   │◄──│ CleaningPlan (accepted    │
│ + Insights│    [storage]    │ cleaning  │   │ rules + user overrides)   │
│ + Chat    │                 │ + log     │   └───────────────────────────┘
└───────────┘                 └───────────┘
```

### DFD-2: Chat question (grounded answering)

```
 question ──► planner ──────────► LLM (schema + question, NO raw data)
                 ▲                   │
                 │ clarify           ▼
 user ◄──────────┘            QueryPlan JSON ──► Pydantic validation
                                                     │ invalid → retry once,
                                                     ▼           then clarify
                                          whitelisted pandas executor
                                          (cleaned.parquet, in memory)
                                                     │ result table (small)
                                                     ▼
                              composer ──► LLM (facts + question → prose)
                                                     │
                                                     ▼
                       answer + chart + audit trail ──► UI + chat_messages
```

### DFD-3: Insights (numbers never come from the LLM)

```
 cleaned.parquet ─► fact_extractor ─► FactPack (JSON: trends, deltas,
                    (pure pandas)      top segments, anomalies, shares)
                                          │
                                          ▼
                          narrator ─► LLM: "write executive prose using
                                      ONLY these facts, cite figures verbatim"
                                          │            │ LLM down
                                          ▼            ▼
                                     InsightSet   template renderer
                                          │            │
                                          └────► cache by dataset_version ─► UI
```

---

## 13. Module Dependency Diagram

Arrows mean "imports from". Enforced with import-linter in CI.

```
                    ┌─────────────┐
                    │   ui/       │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  services/  │
                    └┬────┬───┬──┬┘
          ┌──────────┘    │   │  └──────────────┐
          ▼               ▼   ▼                 ▼
   ┌────────────┐ ┌────────────────┐ ┌────────┐ ┌────────┐
   │   core/    │ │ repositories/  │ │storage/│ │  llm/  │
   └──────┬─────┘ └───────┬────────┘ └───┬────┘ └───┬────┘
          │               │              │          │
          ▼               ▼              │          │
   ┌────────────┐  ┌────────────┐        │          │
   │  schemas/  │  │  models/   │        │          │
   └──────┬─────┘  └──────┬─────┘        │          │
          └───────────┬───┴──────────────┴──────────┘
                      ▼
             ┌─────────────────┐
             │ utils/ config/  │   (imported by everyone; imports nothing internal)
             └─────────────────┘
```

Forbidden edges (CI-failing): `core → ui`, `core → repositories`, `core → llm`*, `repositories → services`, anything → `app.py`.
\* `core/insights` and `core/chat` receive an `LLMProvider` instance by **dependency injection** — they depend on the protocol in `llm/provider.py`, never on the OpenAI SDK.

---

## 14. UI Page Hierarchy

```
DataVerse AI
├── /login                     (public)
├── /register                  (public)
└── (authenticated shell: sidebar = logo, project switcher, nav, user menu)
    ├── /projects              Home — project cards + "New project"
    ├── /upload                Dropzone → sheet picker → parse progress
    └── /project/{id}/
        ├── overview           Health score, dataset summary, pipeline status
        ├── data-health        Profiling detail + cleaning review + before/after
        ├── dashboard          KPI row, filters, auto-generated chart grid
        ├── insights           Executive summary, insight cards, recommendations
        ├── chat               Conversational panel + suggested questions
        ├── forecast           Metric/horizon picker, forecast chart, accuracy
        └── reports            Generate + download PDF, past reports list
```

Navigation rules: project sub-pages are gated by pipeline status (e.g., Dashboard tab shows a "Finish cleaning first" state until status ≥ `cleaned`). Every page has a designed empty state.

---

## 15. Wireframes

### Projects home

```
┌────────────────────────────────────────────────────────────────────┐
│ ◆ DataVerse AI          Projects                     aryan ▾  ⏻   │
├──────────┬─────────────────────────────────────────────────────────┤
│ Projects │  Your projects                          [＋ New project]│
│ Upload   │                                                         │
│          │  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │
│          │  │ Q2 Sales       │ │ Marketing 2026 │ │ HR Attrition │ │
│          │  │ ●92 Health     │ │ ●74 Health     │ │ ●88 Health   │ │
│          │  │ 48,120 rows    │ │ 12,400 rows    │ │ 1,470 rows   │ │
│          │  │ Jul 12, 2026   │ │ Jun 28, 2026   │ │ Jun 02, 2026 │ │
│          │  │ [Open] [⋯]     │ │ [Open] [⋯]     │ │ [Open] [⋯]   │ │
│          │  └────────────────┘ └────────────────┘ └──────────────┘ │
│          │                                                         │
│          │  Storage: ▓▓▓▓░░░░░░ 182 MB / 500 MB                    │
└──────────┴─────────────────────────────────────────────────────────┘
```

### Data Health & Cleaning review

```
┌────────────────────────────────────────────────────────────────────┐
│ Q2 Sales ▸ Data Health                    Health score:  ◐ 74/100  │
├────────────────────────────────────────────────────────────────────┤
│ 48,120 rows · 14 columns · 3 issue types found                     │
│                                                                    │
│ Suggested fixes                            [Accept all] [Apply ✓]  │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ [✓] Remove 340 duplicate rows                        (0.7%)    │ │
│ │ [✓] revenue: fill 5,774 missing with median $412     [median ▾]│ │
│ │ [✓] order_date: convert text → datetime (98% parse)            │ │
│ │ [ ] quantity: cap 5 outliers at 99th pct   ⚠ review — may be   │ │
│ │       real spikes                          [keep ▾]            │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ Before ─────────────── After          Columns                      │
│ rows      48,120 → 47,780             name        type    missing  │
│ missing    12.0% → 0.0%               revenue     float   0% ✓     │
│ dup rows     340 → 0                  order_date  date    0% ✓     │
│ health        74 → 92                 region      categ.  0% ✓     │
└────────────────────────────────────────────────────────────────────┘
```

### Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│ Q2 Sales ▸ Dashboard      [Date: Apr–Jun ▾] [Region: All ▾]  [⟳]   │
├────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│ │ Revenue  │ │ Orders   │ │ Avg Order│ │ Growth   │                │
│ │ $2.41M   │ │ 47,780   │ │ $50.44   │ │ ▲ +8.2%  │                │
│ │ ▲ +8.2%  │ │ ▲ +3.1%  │ │ ▲ +4.9%  │ │ vs Q1    │                │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘                │
│ ┌───────────────────────────────┐ ┌──────────────────────────────┐ │
│ │ Revenue over time        ⤢    │ │ Revenue by region       ⤢    │ │
│ │   ╭─╮        ╭──╮  ╭─         │ │ West   ▓▓▓▓▓▓▓▓▓ $890K      │ │
│ │ ──╯ ╰─╮  ╭──╯  ╰──╯           │ │ East   ▓▓▓▓▓▓▓ $712K        │ │
│ │       ╰──╯                    │ │ North  ▓▓▓▓▓ $488K          │ │
│ └───────────────────────────────┘ │ South  ▓▓▓ $320K ⚠          │ │
│ ┌───────────────────────────────┐ └──────────────────────────────┘ │
│ │ Top products │ Distribution │ Correlation heatmap │ ...          │
└────────────────────────────────────────────────────────────────────┘
```

### Chat with Data

```
┌────────────────────────────────────────────────────────────────────┐
│ Q2 Sales ▸ Chat                                                    │
├────────────────────────────────────────────────────────────────────┤
│  Suggested: [Top products by profit] [Monthly trend] [Q1 vs Q2]    │
│                                                                    │
│  You:  Which region underperformed this quarter?                   │
│                                                                    │
│  ◆ DataVerse: South had the lowest revenue at $320K — 13% of the   │
│    total and 21% below its Q1 figure. Every other region grew.     │
│    ┌──────────────────────────────┐                                │
│    │ Q1 vs Q2 revenue by region ▁▃│  [View query ▾] (audit trail)  │
│    └──────────────────────────────┘                                │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Ask anything about your data…               [➤] │              │
│  └──────────────────────────────────────────────────┘              │
└────────────────────────────────────────────────────────────────────┘
```

---

## 16. Security Considerations

| Area | Control |
|---|---|
| **Passwords** | bcrypt (cost 12) via passlib; strength policy at registration; never logged. |
| **Sessions** | Server-side session rows + `itsdangerous`-signed token; 60-min idle expiry; logout revokes; token never in URLs. |
| **Brute force** | Per-account lockout (5 fails / 15 min) + per-IP throttle. Login errors are uniform ("invalid credentials") — no user enumeration. |
| **Authorization** | Every service method takes `user_id` and verifies ownership at the repository level (`WHERE user_id = :uid`). Non-owned resources return `NotFoundError`, not `Forbidden` — no existence leak. IDs are UUIDs (non-guessable). |
| **File upload** | Extension + MIME sniff + actual parse must all succeed; size cap pre-parse; files stored under server-generated UUID keys (user filename kept only as display metadata — no path traversal); parsing wrapped in memory/time guards. Excel parsed with `openpyxl` (no macro execution). |
| **Injection** | SQL: SQLAlchemy bound parameters only, no string SQL. Pandas: no `eval`/`query` with user strings — chat runs through the whitelisted DSL executor ([Section 10](#10-api-design-service-layer-contracts)). |
| **LLM-specific** | Prompt-injection containment: dataset cell values are untrusted; LLM output is only ever (a) validated JSON plans or (b) display text — never executed. Data minimization: schema + aggregate facts sent by default, never full datasets. Cost cap per project. |
| **Secrets** | Env vars only via pydantic-settings; `.env` git-ignored; `.env.example` documents every variable; secret scanning (gitleaks) in CI. |
| **Transport** | HTTPS enforced by platform (Render terminates TLS); HSTS. |
| **Data privacy** | Per-user isolation everywhere; project delete purges storage artifacts; soft-delete window then hard purge. |
| **Dependencies** | `pip-audit` in CI; Dependabot; pinned versions via lockfile. |
| **Headers/XSS** | No `unsafe_allow_html` with user-derived content; user text rendered as text, never markdown-injected into HTML. |

---

## 17. Error Handling Strategy

**Exception hierarchy** (`utils/errors.py`):

```
DataVerseError(Exception)                # base: message, user_message, error_code, context
├── ValidationError                      # bad input (file type, size, weak password)
├── AuthError
│   ├── InvalidCredentialsError
│   └── AccountLockedError
├── NotFoundError                        # also masks unauthorized access
├── IngestionError
│   ├── UnsupportedFormatError
│   ├── FileTooLargeError
│   └── ParseError                       # includes best-effort diagnosis (encoding? delimiter?)
├── PipelineError
│   ├── ProfilingError
│   └── CleaningError
├── ChatError
│   ├── PlanValidationError              # LLM produced invalid plan after retry
│   └── UnanswerableError                # question outside data's scope (expected, not a bug)
├── ForecastNotApplicableError           # carries human-readable reason
├── LLMError
│   ├── LLMUnavailableError              # triggers degraded mode
│   └── BudgetExceededError
└── StorageError / QuotaExceededError
```

**Rules:**

1. Every `DataVerseError` carries a technical `message` (logs) and a `user_message` (UI) — users never see stack traces or library errors.
2. The UI layer has one top-level handler per page: `DataVerseError` → styled alert with `user_message` + suggested action; unexpected `Exception` → generic "Something went wrong" + logged with request ID shown to the user for support reference.
3. Services translate third-party exceptions at the boundary (e.g., `openai.APIError` → `LLMUnavailableError`) so upper layers never import vendor exception types.
4. **Expected failures are product states, not errors:** unanswerable chat questions, forecast-not-applicable, empty filter results — each renders a designed explanatory state.
5. Retries: LLM calls — 2 retries with exponential backoff on transient errors, then degrade; DB — connection retry on startup; no blind retries on user-input errors.
6. Pipeline steps are transactional: a failed cleaning run writes no partial `cleaned` version and leaves the project reopenable at its previous status.

---

## 18. Logging Strategy

- **Library:** `structlog` → JSON lines in prod, pretty console in dev.
- **Context binding:** every request/interaction gets a `request_id`; `user_id` and `project_id` bound once and appear on all nested log lines.
- **Levels:** `DEBUG` dev-only diagnostics · `INFO` lifecycle events (`upload_completed`, `cleaning_applied`, `chat_answered`) with metrics (rows, duration_ms, tokens) · `WARNING` degraded paths (LLM fallback, plan retry) · `ERROR` unexpected failures with stack traces.
- **Event taxonomy (examples):**
  `auth.login_succeeded / login_failed / lockout_triggered`
  `ingest.upload_received / validation_rejected / parquet_stored`
  `pipeline.profile_completed {duration_ms, rows}`
  `cleaning.rule_applied {rule, rows_affected, accepted}`
  `llm.call {feature, model, prompt_tokens, completion_tokens, cost_usd, latency_ms}`
  `chat.plan_generated / plan_invalid / executed {duration_ms}`
- **Never logged:** passwords, session tokens, raw dataset contents, full LLM prompts containing data samples (prompt *templates* + token counts only).
- **Retention/rotation:** stdout in containers (platform collects); 14-day retention default.
- **Cost observability:** `llm.call` events aggregate into the `llm_usage` table → per-user/per-feature spend is queryable, powering the budget cap.

---

## 19. Testing Strategy

**Pyramid:** many unit tests on `core/` (pure functions — cheap and exhaustive), moderate integration tests on `services/` + DB + storage, a thin end-to-end smoke layer.

| Layer | Scope | Tools | Coverage target |
|---|---|---|---|
| Unit | `core/*`: type inference, each cleaning rule, chart rules, fact extractor, DSL executor, forecast selection | pytest, hypothesis | ≥ 90% |
| Unit | `services/*` with mocked repos/storage/LLM | pytest, unittest.mock | ≥ 80% |
| Integration | Full pipeline against SQLite + local storage: upload fixture → profile → clean → dashboard spec → export | pytest fixtures | Critical paths |
| Contract | Every prompt template: golden-file tests that LLM *inputs* are stable; DSL: every valid/invalid plan shape | pytest | 100% of DSL ops |
| E2E smoke | App boots, register → upload sample → dashboard renders (Streamlit `AppTest`) | streamlit.testing | Happy path |
| Security | Ownership checks (user A cannot access user B's project), upload rejection matrix, lockout | pytest | 100% of guards |

**The torture-file suite** (`tests/fixtures/`) — crafted files that encode the product's hard-won edge cases, run against the entire pipeline:

- empty file · header-only · single row · single column
- mixed encodings (UTF-8 BOM, Latin-1, UTF-16) · `;` and tab delimiters · quoted commas
- dates in 6 formats incl. Excel serial numbers · currency strings (`$1,234.56`, `€1.234,56`)
- 100% missing column · all-duplicate file · 1M-row performance fixture
- column names with spaces/unicode/duplicates · numeric columns that are actually IDs
- Excel: multi-sheet, merged cells, formula cells, hidden sheets

**LLM testing:** deterministic by default — unit/integration tests use `NullProvider` and recorded fixtures; a small opt-in live suite (`pytest -m live_llm`) validates real plan generation quality, run manually/nightly, never in PR CI.

**CI gates (GitHub Actions, on every PR):** ruff → mypy → import-linter (layer law) → pytest (unit+integration, coverage gate) → gitleaks → Docker build.

---

## 20. Deployment Strategy

**Environments**

| Env | Infra | DB | Storage | LLM |
|---|---|---|---|---|
| Local dev | `docker compose up` or bare `streamlit run` | SQLite (default) or compose Postgres | `./data/` | NullProvider unless key set |
| Staging | Render (free tier), auto-deploy from `develop` | Render Postgres | Render disk (v1) | gpt-4o-mini, low budget cap |
| Production | Render (starter), deploy from `main` via release tag | Render Postgres (backups on) | S3-compatible bucket | gpt-4o-mini |

**Pipeline:** merge to `main` → CI green → Docker image built + tagged (git SHA) → Render deploys → `/healthz` check (app up, DB reachable, migrations current) → automatic rollback to previous image on failure. Alembic migrations run as a pre-deploy step (`alembic upgrade head`); all migrations must be backward-compatible one release back (rollback safety).

**Configuration:** 12-factor — all config via env vars (`DATABASE_URL`, `STORAGE_BACKEND`, `STORAGE_PATH`/`S3_*`, `OPENAI_API_KEY`, `SECRET_KEY`, `MAX_UPLOAD_MB`, `LLM_BUDGET_USD`, `LOG_LEVEL`). Feature flags (`ENABLE_FORECASTING`, `ENABLE_CHAT`) allow shipping incomplete features dark.

**Portability:** the deliverable is a standard Docker image + Postgres + S3-compatible storage — moves to Azure App Service or AWS ECS/App Runner without code changes. Render chosen first for zero-ops and free tier (this is also a portfolio project — reviewers must be able to click a live link).

---

## 21. Git Branching Strategy

**GitHub Flow with a release branch** — lightweight, PR-centric, appropriate for 1–3 contributors:

```
main ────────●────────●──────────●──►   protected; every commit deployable; tagged releases (v0.3.0)
              \      /          /
develop ───────●────●────●─────●────►   integration branch; auto-deploys to staging
                \       /
feature/* ───────●──●──●                 short-lived; PR into develop
hotfix/*  ── branched from main, PR to main, back-merged to develop
```

- Branch naming: `feature/chat-query-dsl`, `fix/excel-serial-dates`, `chore/ci-cache`.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`) → auto-generated changelog.
- PRs require: CI green, self-review checklist, description with screenshots for UI changes. Squash-merge to keep history linear.
- `main` and `develop` are push-protected; releases are annotated tags on `main` following SemVer.

---

## 22. Development Roadmap & Milestones

Six milestones, each ending in a demoable state. Estimates assume one focused developer.

| Milestone | Scope (FR refs) | Duration | Demo at the end |
|---|---|---|---|
| **M0 — Foundations** | Repo, pyproject, layer skeleton, config, logging, errors, CI, Docker, Alembic baseline, theme shell | 1 wk | App boots with styled empty shell; CI green |
| **M1 — Auth & Projects** | AUTH-1..5, PRJ-1..4, DB models, repositories, storage abstraction | 1 wk | Register → login → empty projects page → logout |
| **M2 — Ingestion & Profiling** | UPL-1..7, PRF-1..7, torture-file suite | 2 wks | Upload any messy file → full Data Health report |
| **M3 — Cleaning & Dashboards** | CLN-1..8, DSH-1..9 | 2 wks | Review/apply cleaning → interactive auto-dashboard → download cleaned CSV. **App is genuinely useful with zero LLM.** |
| **M4 — AI: Insights & Chat** | INS-1..6, CHT-1..6, LLM provider + budget + degraded mode | 2 wks | Executive summary + grounded Q&A with audit trail |
| **M5 — Forecasting & Reports** | FCT-1..6, RPT-1..2, 4 | 1.5 wks | Forecast with intervals + exported PDF report |
| **M6 — Hardening & Launch** | Perf pass (1M-row fixture), security review, empty-state polish, sample datasets, README with screenshots + live demo link, seed script | 1.5 wks | Public deployment; recruiter-ready |

**Total: ~11 weeks.** Sequencing rationale: M3 before M4 means the product stands on deterministic value before AI is layered on — de-risking the LLM dependency and matching the degraded-mode design.

---

## 23. Future Enhancements

**v1.x (natural extensions):** PowerPoint export (RPT-3) · password reset email (AUTH-6) · scheduled email reports · dashboard layout editing (drag/resize/pin) · saved chat answers pinned to dashboard · multi-file projects with join detection · dark mode.

**v2 (architectural steps):** FastAPI backend + Next.js frontend (service layer already REST-shaped — [Section 10](#10-api-design-service-layer-contracts)) · background workers (Celery/RQ) for profiling and reports · live connectors (Postgres, Google Sheets, Shopify, Stripe) · organizations/teams with roles and shared projects · public read-only dashboard links · embeddings-based semantic column understanding · anomaly alerting ("notify me if weekly revenue drops >10%") · multi-LLM routing (Anthropic/local via the provider interface).

**v3 (product bets):** dbt-style transformation pipelines for repeat uploads · industry template packs (e-commerce, SaaS metrics, HR) · white-label/embedded analytics SDK · usage-based billing (Stripe) · SOC 2-oriented audit logging.

---

## 24. Risks and Trade-offs

| # | Risk / trade-off | Impact | Mitigation |
|---|---|---|---|
| 1 | **Streamlit UI ceiling** — limited layout control, full-script rerun model can feel sluggish; may undercut the "premium SaaS" bar | Medium | Custom theming + `st.fragment` for partial reruns + aggressive `st.cache_data`; strict layer separation keeps the v2 React path cheap. Accepted consciously: shipping polished in 11 weeks beats half-finished React in 20. |
| 2 | **LLM hallucination of numbers** would destroy user trust instantly | High | Core design decision: LLM never computes — facts extracted deterministically, chat runs through validated DSL, plans stored for audit. This is the load-bearing architecture choice of the product. |
| 3 | **LLM cost & availability** (runaway spend, outages, key leakage) | Medium | Budget table + per-project cap; NullProvider degraded mode; features M0–M3 fully LLM-free; key only via env. |
| 4 | **Memory blow-ups on large files** — pandas can need 5–10× file size in RAM; a 100 MB CSV can OOM a 4 GB node | High | Hard upload cap; PyArrow-backed dtypes; chunked CSV parse for size estimation before full load; display downsampling; documented limit with helpful messaging. True big-file support deferred to v2 workers + Polars/DuckDB. |
| 5 | **Auto-cleaning damages data** (imputing skews stats, "outliers" were real events) | High | Conservative defaults (outliers: keep), per-rule opt-in, raw file immutable, full log, before/after view, re-clean from raw anytime. |
| 6 | **Semantic type misdetection** (ZIP codes as numeric, IDs as metrics) cascades into nonsense KPIs | Medium | Heuristics (uniqueness ratio, name patterns like `*_id`, cardinality) + user-overridable column types in the Data Health page. |
| 7 | **Forecasting on unsuitable data** produces confidently wrong charts | Medium | Strict eligibility gate (FR-FCT-1), seasonal-naive baseline that fancy models must beat on backtest, error ranges displayed honestly. |
| 8 | **Synchronous heavy work** blocks the UI thread and other users on one node | Medium | v1: progress indicators + 30 s profiling budget + caching; seam already designed for v2 job queue. Accepted for v1 scale (tens of users). |
| 9 | **Prompt injection via dataset content** (a cell containing "ignore previous instructions…") | Medium | LLM output is never executed — only validated-JSON plans or display text; data sent to LLM is aggregates/schema by default. |
| 10 | **Scope creep** — 10 features × polish is a lot for one developer | High | MoSCoW priorities, milestone gates, feature flags to ship dark, and this document as the contract. |
| 11 | **Single-developer bus factor / review quality** | Low | CI as reviewer-of-first-resort (types, lint, layer law, coverage gate), self-review checklist on PRs, this doc as onboarding for any collaborator. |

---

## Approval

This document is the complete design for DataVerse AI v1.
**No application code has been written.** Upon approval, implementation begins at **M0 — Foundations** per the roadmap in [Section 22](#22-development-roadmap--milestones).

*Requested feedback: (1) approve the Streamlit-first decision or redirect to FastAPI+React now; (2) confirm the 100 MB upload cap and 500 MB quota defaults; (3) approve the milestone ordering.*
