#!/usr/bin/env bash
# Separate database/evidence volumes. Owner stack must be idle before evaluator tests.
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p artifacts/demo-production
export COMPOSE_PROJECT_NAME=patch-demo-verify
export WORKBENCH_DB_PORT=55529 WORKBENCH_API_PORT=18110 WORKBENCH_PREVIEW_PORT=18113
export DATABASE_URL=postgresql+asyncpg://workbench:workbench@127.0.0.1:55529/workbench
export E2E_BASE_URL=http://127.0.0.1:18110 E2E_PREVIEW_URL=http://127.0.0.1:18113
export E2E_EVIDENCE_DIR="$PWD/artifacts/demo-production/product-checks"
export LIVE_NVIDIA_E2E=0 LIVE_NVIDIA_REPAIR=0 LIVE_NVIDIA_M4=0 M4_SAVED_REOPEN=0
trap 'docker compose down > artifacts/demo-production/verify-down.log 2>&1' EXIT
docker compose up --build -d --wait api
uv run --project backend python -m workbench.evaluator.experiment_cli import
./scripts/e2e
E2E_BASE_URL=https://ai-debugging-workbench-recorded.vercel.app ./scripts/e2e -k recorded_explorer_first
