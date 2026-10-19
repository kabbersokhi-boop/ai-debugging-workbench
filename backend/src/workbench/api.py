import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from workbench import release as recordings_api
from workbench.access import authorize, check_origin, guest
from workbench.config import settings
from workbench.contracts import BUG, Bug, CreateRun, RunSummary, RunView
from workbench.db import Run, SourceSnapshot, engine, sessions
from workbench.evaluator.routes import router as evaluator_router
from workbench.evaluator.service import EvaluationManager
from workbench.patch_audit.routes import router as patch_audit_router
from workbench.patch_audit.service import AuditManager
from workbench.rag.contracts import InvestigationRequest
from workbench.rag.service import InvestigationManager
from workbench.rag.snapshot import scenario_manifest
from workbench.repair.contracts import RemoteAction
from workbench.repair.service import RepairManager
from workbench.repository_audit.routes import router as repository_audit_router
from workbench.repository_audit.service import RepositoryAuditManager
from workbench.runner import scenario_resource
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
                evaluations = EvaluationManager()
                app.state.evaluations = evaluations
                await evaluations.recover()
                audits = AuditManager()
                app.state.patch_audits = audits
                await audits.recover()
                repository_audits = RepositoryAuditManager()
                app.state.repository_audits = repository_audits
                await repository_audits.recover()
                try:
                    yield
                finally:
                    await repository_audits.close()
                    await audits.close()
                    await evaluations.close()
                    await repairs.close()
                    await investigations.close()
                    await manager.close()
        finally:
            await coordinator.execute(text("SELECT pg_advisory_unlock(71402501)"))
            await coordinator.commit()
    await engine.dispose()


app = FastAPI(title="AI debugging workbench", version="0.1.0", lifespan=lifespan)
app.state.evaluation_admission = asyncio.Lock()


async def coordinated_call(request, call_next):
    if request.method == "POST" and request.url.path in (
        "/api/evaluator/runs",
        "/api/patch-audits/runs",
        "/api/repository-audits/runs",
    ):
        async with request.app.state.evaluation_admission:
            for name in ("evaluations", "patch_audits", "repository_audits"):
                manager = getattr(request.app.state, name, None)
                if manager is not None and manager.jobs:
                    return JSONResponse({"detail": "The local evaluator is occupied"}, 429)
            return await call_next(request)
    return await call_next(request)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    if (
        request.url.path.startswith(("/api/patch-audits", "/api/repository-audits"))
        and request.method == "POST"
    ):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 450000:
                return JSONResponse({"detail": "Patch Audit request exceeds size limit"}, 413)
        request._body = bytes(body)
    owner = None
    try:
        if settings.guest_access and request.url.path.startswith("/api/"):
            check_origin(request)
            owner, created = await guest(request)
            request.state.owner_id = owner
            await authorize(request.url.path, owner)
        else:
            created = False
        response = await coordinated_call(request, call_next)
        if created and owner is not None:
            response.set_cookie(
                "workbench_guest",
                str(owner),
                max_age=86400,
                httponly=True,
                secure=settings.secure_cookies,
                samesite="strict",
            )
    except HTTPException as error:
        response = JSONResponse({"detail": error.detail}, status_code=error.status_code)
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
    return [
        BUG
        if c["id"] == BUG.id
        else Bug(
            id=c["id"],
            title=c["title"],
            summary=c["report"],
            report=c["report"],
            severity="High",
            steps=[
                "Open the approved scenario with a fresh cart.",
                "Follow the report; compare visible quantities and prices.",
            ],
            expected=(
                "Quantity stays between 1 and 9; prices include every unit; "
                "shipping is $8 below $100 and free otherwise."
            ),
            repository="fixtures/retail",
        )
        for c in scenario_manifest()["cases"]
        if c["split"] == "development"
    ]


@app.get("/api/runs")
async def history(request: Request) -> list[RunSummary]:
    async with sessions() as session:
        query = select(Run).order_by(Run.created_at.desc()).limit(30)
        if settings.guest_access:
            query = query.where(Run.owner_id == request.state.owner_id)
        runs = (await session.scalars(query)).all()
        return [RunSummary.model_validate(run) for run in runs]


@app.post("/api/runs", status_code=202)
async def create_run(
    payload: CreateRun,
    request: Request,
    idempotency_key: Annotated[str | None, Header(min_length=8, max_length=100)] = None,
) -> RunView:
    manager: RunManager = request.app.state.manager
    from workbench.rag.snapshot import scenario

    try:
        case = scenario(payload.bug_id)
    except ValueError:
        raise HTTPException(422, "Unknown supported scenario") from None
    if case["split"] != "development":
        raise HTTPException(422, "Only demonstration scenarios can be run through the product")
    if settings.guest_access and idempotency_key:
        import hashlib

        idempotency_key = hashlib.sha256(
            f"{request.state.owner_id}:{idempotency_key}".encode()
        ).hexdigest()
    result = await manager.create(payload.bug_id, idempotency_key)
    if settings.guest_access:
        async with sessions.begin() as session:
            row = await session.get(Run, result.id)
            assert row is not None
            if row.owner_id not in (None, request.state.owner_id):
                raise HTTPException(409, "Idempotency ownership mismatch")
            row.owner_id = request.state.owner_id
    return result


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
    return {**result, "url": f"/repairs/{repair_id}/attempts/{attempt}/remote"}


@app.post("/api/repairs/{repair_id}/attempts/{attempt}/remote")
async def remote_preview(repair_id: UUID, attempt: int, action: RemoteAction, request: Request):
    candidate = await saved_attempt(repair_id, attempt, request)
    async with httpx.AsyncClient(timeout=16) as client:
        response = await client.post(
            f"{settings.repair_broker_url}/candidates/{repair_id}/{attempt}/remote",
            json=action.model_dump(),
        )
    if response.status_code != 200:
        raise HTTPException(
            503, "Remote browser is unavailable or reached its limits. Retry or reset after expiry."
        )
    result = response.json()
    if result["candidate_hash"] != candidate["candidate"]["candidate_hash"]:
        raise HTTPException(409, "Remote frame identity mismatch")
    return result


@app.get("/api/repairs/{repair_id}/attempts/{attempt}/screenshot")
async def candidate_screenshot(repair_id: UUID, attempt: int, request: Request):
    candidate = await saved_attempt(repair_id, attempt, request)
    verification = candidate.get("verification")
    if not verification:
        raise HTTPException(404, "No trusted candidate capture exists")
    version = verification.get("artifact_id", verification["verifier_version"])
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.repair_broker_url}/candidates/{repair_id}/{attempt}/artifacts/after-{version}.png"
        )
        if response.status_code != 200 or len(response.content) > 2000000:
            raise HTTPException(404, "Candidate screenshot unavailable")
    return Response(response.content, media_type="image/png")


@app.get("/scenarios/{scenario_id}/retail/{name:path}")
async def scenario_file(scenario_id: str, name: str):
    return scenario_resource(scenario_id, name)


app.add_api_route("/api/recorded-audits", recordings_api.recorded_audits)
app.add_api_route("/api/recorded-audits/{audit_id}", recordings_api.recorded_audit)
app.add_api_route(
    "/api/recorded-audits/{audit_id}/evidence", recordings_api.recorded_audit_evidence
)
app.add_api_route("/api/recorded-audits/{audit_id}/patch", recordings_api.recorded_audit_patch)
app.add_api_route("/api/recordings", recordings_api.recordings)
app.add_api_route("/api/recordings/{recording_id}", recordings_api.recording)
app.add_api_route("/api/recorded-assets/{name}", recordings_api.asset)
app.add_api_route("/recorded/", recordings_api.explorer)


@app.get("/api/mode")
async def mode():
    return {"mode": "private_live", "live_available": True, "recorded_url": "/recorded/"}


app.include_router(evaluator_router)
app.include_router(patch_audit_router)
app.include_router(repository_audit_router)


# The same immutable fixture can be explored manually without exposing the runner API.
app.mount("/retail", StaticFiles(directory=settings.fixture_dir, html=True), name="retail")
if settings.frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
