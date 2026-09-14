FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.10.12
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --locked --no-dev && useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/call-summary && chown app:app /tmp/call-summary
USER app
CMD ["uvicorn", "call_summary.api:app", "--host", "0.0.0.0", "--port", "8010"]
