"""Local-only G1 routes. Intake and patch review never execute project code."""

import asyncio
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select

from workbench.config import settings
from workbench.db import (
    RepositoryAudit,
    RepositoryCandidate,
    RepositoryPlan,
    RepositorySource,
    sessions,
)
from workbench.evaluator.catalog import identity
from workbench.patch_audit.routes import local_only
from workbench.repository_audit.admission import admit, check_plan
from workbench.repository_audit.contracts import Confirm, Import, Intake, Plan
from workbench.repository_audit.intake import Rejected, fetch, summary
from workbench.repository_audit.service import load, material, store, view

router = APIRouter(prefix="/api/repository-audits", dependencies=[Depends(local_only)])
FETCH_LOCK = asyncio.Lock()


@router.post("/sources", status_code=201)
async def source(payload: Intake):
    if FETCH_LOCK.locked():
        raise HTTPException(429, "Repository intake is occupied")
    async with FETCH_LOCK:
        try:
            record = await fetch(payload)
            await store(RepositorySource, record)
            return summary(record)
        except Rejected as error:
            raise HTTPException(422, {"status": error.status, "reason": str(error)}) from None


@router.get("/sources/{snapshot_id}")
async def source_review(snapshot_id: str):
    return summary(await load(RepositorySource, snapshot_id))


@router.post("/candidates", status_code=201)
async def candidate(payload: Import):
    try:
        snapshot = await load(RepositorySource, payload.snapshot_id)
        record = await asyncio.to_thread(admit, snapshot, payload)
        return await store(RepositoryCandidate, record, snapshot_id=snapshot["id"])
    except (ValueError, TimeoutError) as error:
        raise HTTPException(422, {"status": "patch_rejected", "reason": str(error)}) from None


@router.get("/candidates/{candidate_id}/patch")
async def patch(candidate_id: str):
    _, candidate = await material(candidate_id)
    return PlainTextResponse(
        candidate["patch"],
        headers={"Content-Disposition": f'attachment; filename="{candidate_id}.patch"'},
    )


@router.get("/runtimes")
async def runtime_options():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.evaluator_url}/repository-runtimes")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Local execution broker is unavailable") from None


@router.post("/plans", status_code=201)
async def plan(payload: Plan):
    snapshot = await load(RepositorySource, payload.snapshot_id)
    # Candidate software identity may have multiple user-declared import records.
    async with sessions() as session:
        records = (
            await session.scalars(
                select(RepositoryCandidate).where(RepositoryCandidate.snapshot_id == snapshot["id"])
            )
        ).all()
    candidate = next(
        (r.record for r in records if r.record["candidate_hash"] == payload.candidate_hash), None
    )
    if candidate is None:
        raise HTTPException(409, "Import the candidate before preparing its execution plan")
    try:
        check_plan(snapshot, candidate, payload.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    value = payload.model_dump()
    record = {"id": identity(value), "plan": value}
    await store(RepositoryPlan, record)
    return {**record, "approval": "not_approved"}


@router.post("/runs", status_code=202)
async def start(payload: Confirm, request: Request):
    try:
        return await request.app.state.repository_audits.create(
            payload.candidate_id, payload.plan_id
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.get("/runs")
async def history():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(RepositoryAudit).order_by(RepositoryAudit.created_at.desc()).limit(100)
            )
        ).all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "repository": r.evidence["snapshot"]["repository"],
            "candidate_id": r.candidate_id,
        }
        for r in rows
    ]


@router.get("/runs/{audit_id}")
async def saved(audit_id: UUID):
    async with sessions() as session:
        row = await session.get(RepositoryAudit, audit_id)
        if row is None:
            raise HTTPException(404, "Repository audit not found")
        return await asyncio.to_thread(view, row)


@router.get("/runs/{audit_id}/evidence")
async def evidence(audit_id: UUID):
    return JSONResponse(
        await saved(audit_id),
        headers={"Content-Disposition": f'attachment; filename="repository-audit-{audit_id}.json"'},
    )


@router.post("/runs/{audit_id}/cancel")
async def cancel(audit_id: UUID, request: Request):
    return await request.app.state.repository_audits.cancel(audit_id)
