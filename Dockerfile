FROM python:3.13.9-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY scripts/deployment ./scripts/deployment
COPY alembic.ini POLICY_V1.yaml release-manifest.yaml ./
RUN uv sync --frozen --no-dev

FROM python:3.13.9-slim-bookworm AS runtime

ARG GIT_SHA=unknown
ARG RELEASE_VERSION=release-v1
LABEL org.opencontainers.image.title="stock-agent-system" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${RELEASE_VERSION}"

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=development \
    BROKER_MODE=FAKE \
    LIVE_TRADING_ENABLED=false

RUN groupadd --system --gid 10001 stockagent \
    && useradd --system --uid 10001 --gid stockagent --home-dir /app stockagent

WORKDIR /app
COPY --from=builder --chown=stockagent:stockagent /app /app

USER 10001:10001
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn stock_agent.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
