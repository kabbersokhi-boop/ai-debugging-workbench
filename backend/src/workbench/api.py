from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from workbench.config import settings
from workbench.contracts import BUG, Bug, CreateRun, RunSummary, RunView
from workbench.db import Run, SourceSnapshot, engine, sessions
from workbench.rag.contracts import InvestigationRequest
from workbench.rag.service import InvestigationManager
from workbench.repair.service import RepairManager
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
                investigations = InvestigationManager()
                app.state.investigations = investigations
                await investigations.recover()
                repairs = RepairManager()
                app.state.repairs = repairs
                await repairs.recover()
                try:
                    yield
                finally:
                    await repairs.close()
                    await investigations.close()
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


@app.post("/api/runs/{run_id}/investigations", status_code=202)
async def investigate(run_id: UUID, payload: InvestigationRequest, request: Request):
    return await request.app.state.investigations.create(run_id, payload.report)


@app.get("/api/runs/{run_id}/investigations")
async def investigation_history(run_id: UUID, request: Request):
    return await request.app.state.investigations.history(run_id)


@app.get("/api/investigations/{investigation_id}")
async def investigation_detail(investigation_id: UUID, request: Request):
    return await request.app.state.investigations.get(investigation_id)


@app.post("/api/investigations/{investigation_id}/cancel")
async def cancel_investigation(investigation_id: UUID, request: Request):
    return await request.app.state.investigations.cancel(investigation_id)


@app.get("/api/snapshots/{snapshot_id}")
async def snapshot_detail(snapshot_id: str):
    async with sessions() as session:
        row = await session.get(SourceSnapshot, snapshot_id)
        if row is None:
            raise HTTPException(404, "Saved source snapshot not found")
        return row.manifest


@app.post("/api/investigations/{investigation_id}/repairs", status_code=202)
async def start_repair(investigation_id: UUID, request: Request):
    return await request.app.state.repairs.create(investigation_id)


@app.get("/api/investigations/{investigation_id}/repairs")
async def repair_history(investigation_id: UUID, request: Request):
    return await request.app.state.repairs.history(investigation_id)


@app.get("/api/repairs/{repair_id}")
async def repair_detail(repair_id: UUID, request: Request):
    return await request.app.state.repairs.get(repair_id)


@app.post("/api/repairs/{repair_id}/cancel")
async def cancel_repair(repair_id: UUID, request: Request):
    return await request.app.state.repairs.cancel(repair_id)


async def saved_attempt(repair_id: UUID, attempt: int, request: Request):
    row = await request.app.state.repairs.get(repair_id)
    candidate = next((a for a in row["state"]["attempts"] if a["number"] == attempt), None)
    if candidate is None or not candidate.get("candidate"):
        raise HTTPException(404, "Candidate attempt not found")
    return candidate


@app.get("/api/repairs/{repair_id}/attempts/{attempt}/patch")
async def patch_download(repair_id: UUID, attempt: int, request: Request):
    candidate = await saved_attempt(repair_id, attempt, request)
    return Response(
        candidate["candidate"]["diff"],
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="candidate.patch"'},
    )


@app.get("/api/repairs/{repair_id}/evidence")
async def repair_evidence(repair_id: UUID, request: Request):
    import json

    from fastapi.encoders import jsonable_encoder

    row = await request.app.state.repairs.get(repair_id)
    return Response(
        json.dumps(jsonable_encoder(row), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="repair-evidence.json"'},
    )


@app.post("/api/repairs/{repair_id}/attempts/{attempt}/preview")
async def candidate_preview(repair_id: UUID, attempt: int, request: Request):
    candidate = await saved_attempt(repair_id, attempt, request)
    manager = request.app.state.repairs
    try:
        result = await manager.broker(f"/candidates/{repair_id}/{attempt}/preview")
    except httpx.HTTPError:
        raise HTTPException(
            503, "Candidate preview is unavailable. Retry when the executor is ready."
        ) from None
    if result["candidate_hash"] != candidate["candidate"]["candidate_hash"]:
        raise HTTPException(409, "Preview identity does not match the saved candidate")
    return {**result, "url": settings.repair_preview_origin + result["path"]}


@app.get("/api/repairs/{repair_id}/attempts/{attempt}/screenshot")
async def candidate_screenshot(repair_id: UUID, attempt: int, request: Request):
    candidate = await saved_attempt(repair_id, attempt, request)
    verification = candidate.get("verification")
    if not verification:
        raise HTTPException(404, "No trusted candidate capture exists")
    version = verification["verifier_version"]
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.repair_broker_url}/candidates/{repair_id}/{attempt}/artifacts/after-{version}.png"
        )
        if response.status_code != 200 or len(response.content) > 2000000:
            raise HTTPException(404, "Candidate screenshot unavailable")
    return Response(response.content, media_type="image/png")


# The same immutable fixture can be explored manually without exposing the runner API.
app.mount("/retail", StaticFiles(directory=settings.fixture_dir, html=True), name="retail")
if settings.frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
