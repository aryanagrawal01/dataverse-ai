FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY migrations ./migrations
COPY app.py ./
COPY sample_data ./sample_data
COPY .streamlit ./.streamlit

RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser /app/data
USER appuser

EXPOSE 8501
ENV PORT=8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 8501)}/_stcore/health')"

# Run migrations, then start the app. $PORT is honored so this image works
# unmodified on platforms that inject their own port (Render, Railway, etc.)
# as well as locally/compose, where it defaults to 8501.
CMD ["sh", "-c", "alembic upgrade head && streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
