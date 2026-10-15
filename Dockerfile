FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS runtime
RUN pip install --no-cache-dir uv==0.11.16
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --python 3.12 --no-install-project
COPY backend/src/ ./src/
COPY backend/migrations/ ./migrations/
COPY backend/alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev --python 3.12
COPY fixtures/ /app/fixtures/
COPY --from=web /web/dist /app/frontend/dist
RUN mkdir -p /app/artifacts && chown pwuser:pwuser /app/artifacts
USER pwuser
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD [".venv/bin/uvicorn", "workbench.api:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]
