FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS release
COPY docker/release-requirements.txt /tmp/release-requirements.txt
RUN pip install --no-cache-dir -r /tmp/release-requirements.txt
WORKDIR /release
COPY backend/src/workbench/release.py ./release.py
COPY recordings/ ./recordings/
COPY --from=web /web/dist ./frontend/dist/
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RELEASE_ROOT=/release
CMD ["uvicorn", "release:app", "--host", "0.0.0.0", "--port", "8020", "--workers", "1", "--no-access-log", "--limit-concurrency", "32", "--timeout-keep-alive", "5"]
