# ◆ DataVerse AI

**AI-powered Business Intelligence: upload a spreadsheet — get automated cleaning, interactive dashboards, grounded AI insights, backtested forecasts, a conversational interface to your data, and boardroom-ready PDF reports. No SQL. No Python.**

> From spreadsheet to boardroom insight in under two minutes.

![Python 3.12](https://img.shields.io/badge/python-3.12-blue) ![Tests](https://img.shields.io/badge/tests-185%20passing-brightgreen) ![mypy](https://img.shields.io/badge/mypy-clean-brightgreen) ![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)

## What it does

| | |
|---|---|
| 📤 **Smart ingestion** | CSV/Excel, drag-and-drop, encoding + delimiter sniffing, multi-sheet workbooks, duplicate-column repair |
| 🩺 **Data Health Report** | Semantic type inference (currency/dates/booleans hiding in text, ID detection), missing values, duplicates, outliers (IQR + z-score + IsolationForest), correlations, and a 0–100 health score |
| 🧹 **Transparent cleaning** | Per-fix review with strategy pickers, before/after comparison, immutable audit log — the raw file is never touched |
| 📊 **Instant dashboards** | KPI cards with period-over-period deltas, trend/breakdown/distribution charts, correlation heatmap, date + category filters — all derived from the data's shape |
| 🤖 **Grounded AI insights** | Executive summaries and recommendations where every number is computed deterministically; the LLM only writes the prose |
| 💬 **Chat with your data** | Questions become validated JSON query plans executed by a whitelisted interpreter — no generated code, full audit trail on every answer |
| 📈 **Honest forecasting** | Models compete on a backtest (seasonal-naive vs Holt-Winters); the winner ships with 80/95% intervals and its real error rate |
| 📄 **PDF reports** | Cover, executive summary, KPIs, charts, insights, and the cleaning appendix |

**Works without an API key.** Profiling, cleaning, dashboards, forecasting, and reports are fully deterministic; AI narrative features degrade gracefully to rule-based text. Add `OPENAI_API_KEY` to enable chat and AI-written insights (per-project cost caps included).

## Quickstart (local, zero setup)

```bash
git clone <repo-url> && cd dataverse-ai
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed.py        # optional: demo user with a processed project
streamlit run app.py          # → http://localhost:8501
```

Demo login after seeding: `demo@dataverse.ai` / `demo-pass-1` — or register and click **"✨ Try a sample dataset."**

## Quickstart (Docker)

```bash
docker compose up --build
# → http://localhost:8501  (app + Postgres)
```

## Architecture

Full design document: [ARCHITECTURE.md](ARCHITECTURE.md) — requirements, database schema, the chat query-plan DSL, security model, testing strategy, roadmap, and every deviation made during implementation (with reasons).

```
ui → services → (core | repositories | storage | llm) → schemas/models → utils → config
```

- The layer law is **enforced in CI** with import-linter; `core/` contains pure business logic — no Streamlit, no SQLAlchemy, no vendor SDKs.
- Datasets live as immutable Parquet artifacts behind a storage abstraction; PostgreSQL (SQLite in dev) holds only metadata.
- The LLM sits behind a provider protocol with usage tracking, per-project budgets, and a null provider for degraded mode. It never computes a number and its output is never executed.

## Quality gates (all run in CI)

```bash
ruff check src tests && ruff format --check src tests   # lint + format
mypy                                                    # strict-ish typing
lint-imports                                            # architecture layer law
pytest                                                  # 185 tests, LLM mocked
pytest -m slow                                          # performance guardrails
```

The ingestion pipeline is exercised by a **torture-file suite**: mixed encodings (UTF-8 BOM, Latin-1, UTF-16), exotic delimiters, quoted commas, currency strings, six date formats, duplicate/blank column names, all-duplicate files, numeric-looking ID columns, multi-sheet Excel, and more.

## License

MIT
