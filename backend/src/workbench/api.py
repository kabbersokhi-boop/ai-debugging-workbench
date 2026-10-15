from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from workbench.config import settings
from workbench.contracts import BUG, Bug, CreateRun, RunSummary, RunView
from workbench.db import Run, engine, sessions
from workbench.service import RunManager, get_run


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Explicitly enforce one API coordinator; avoid silently corrupting restart recovery.
    async with engine.connect() as coordinator:
        acquired = await coordinator.scalar(text("SELECT pg_try_advisory_lock(71402501)"))
        await coordinator.commit()
        if not acquired:
            raise RuntimeError("Only one API coordinator is supported. Start with --workers 1.")
        try:
            async with httpx.AsyncClient(base_url=settings.runner_url, timeout=None) as client:
                manager = RunManager(client)
                app.state.manager = manager
                await manager.recover()
                try:
                    yield
                finally:
                    await manager.close()
        finally:
            await coordinator.execute(text("SELECT pg_advisory_unlock(71402501)"))
            await coordinator.commit()
    await engine.dispose()


app = FastAPI(title="AI debugging workbench", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
async def health(request: Request) -> dict[str, str]:
    try:
        async with sessions() as session:
            await session.execute(text("SELECT 1"))
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{settings.runner_url}/health")
            response.raise_for_status()
    except Exception as error:
        raise HTTPException(503, "Database or browser runner is unavailable") from error
    return {"status": "ok", "database": "postgresql", "runner": "ready", "mode": "live-browser"}


@app.get("/api/bugs")
async def bugs() -> list[Bug]:
    return [BUG]


@app.get("/api/runs")
async def history() -> list[RunSummary]:
    async with sessions() as session:
        runs = (await session.scalars(select(Run).order_by(Run.created_at.desc()).limit(30))).all()
        return [RunSummary.model_validate(run) for run in runs]


@app.post("/api/runs", status_code=202)
async def create_run(
    payload: CreateRun,
    request: Request,
    idempotency_key: Annotated[str | None, Header(min_length=8, max_length=100)] = None,
) -> RunView:
    manager: RunManager = request.app.state.manager
    return await manager.create(payload.bug_id, idempotency_key)


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: UUID) -> RunView:
    return await get_run(run_id)


@app.post("/api/runs/{run_id}/cancel")
async def cancel(run_id: UUID, request: Request) -> RunView:
    manager: RunManager = request.app.state.manager
    return await manager.cancel(run_id)


@app.get("/api/runs/{run_id}/artifacts/{name}")
async def artifact(run_id: UUID, name: str) -> FileResponse:
    view = await get_run(run_id)
    allowed = {"before.png": "image/png", "after.png": "image/png"}
    if view.result:
        allowed.update({item.name: item.media_type for item in view.result.artifacts})
    if name not in allowed:
        raise HTTPException(404, "Evidence artifact not found")
    path = settings.artifact_dir / str(run_id) / name
    if not path.is_file():
        raise HTTPException(404, "Evidence artifact is not available")
    return FileResponse(
        path,
        media_type=allowed[name],
        filename=name,
        content_disposition_type="inline" if name.endswith(".png") else "attachment",
    )


@app.get("/api/storefront")
async def storefront() -> RedirectResponse:
    return RedirectResponse("/retail/")


# The same immutable fixture can be explored manually without exposing the runner API.
app.mount("/retail", StaticFiles(directory=settings.fixture_dir, html=True), name="retail")
if settings.frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
