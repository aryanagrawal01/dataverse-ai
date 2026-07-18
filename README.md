# ◆ DataVerse AI

**AI-powered Business Intelligence: upload a spreadsheet — get automated cleaning, interactive dashboards, AI insights, forecasts, and a chat interface to your data. No SQL. No Python.**

> From spreadsheet to boardroom insight in under two minutes.

## Features

- 📤 **Smart ingestion** — CSV/Excel, drag-and-drop, encoding & delimiter detection, multi-sheet support
- 🩺 **Data Health Report** — profiling, missing values, duplicates, type issues, outliers, 0–100 health score
- 🧹 **Transparent auto-cleaning** — per-rule review, before/after comparison, full audit log, raw data always preserved
- 📊 **Auto-generated dashboards** — KPI cards, trends, breakdowns, distributions, correlation heatmaps (interactive Plotly)
- 🤖 **Grounded AI insights** — executive summaries and recommendations; every number computed deterministically, never hallucinated
- 💬 **Chat with your data** — natural-language questions answered via a validated query plan with a full audit trail
- 📈 **Honest forecasting** — backtested model selection with confidence intervals and error ranges
- 📄 **PDF reports** — executive summary, KPIs, charts, insights, cleaning appendix

## Quickstart (local, zero setup)

```bash
git clone <repo-url> && cd dataverse-ai
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
streamlit run app.py
```

Runs on SQLite + local disk by default. Add `OPENAI_API_KEY` to a `.env` file to enable AI features — everything else works without it.

## Quickstart (Docker)

```bash
docker compose up --build
# → http://localhost:8501  (app + Postgres)
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) — full design document: layered architecture, database schema, query-plan DSL, security model, testing strategy, and roadmap.

```
ui → services → (core | repositories | storage | llm) → schemas/models → utils/config
```

The layer law is enforced in CI with import-linter. `core/` is pure business logic: no Streamlit, no SQLAlchemy, no vendor SDKs.

## Development

```bash
ruff check src tests        # lint
mypy                        # type-check
lint-imports                # architecture layer law
pytest                      # tests (LLM tests are mocked by default)
```

## License

MIT
