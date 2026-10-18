"""Trusted local owner routes. Import never starts execution."""

import asyncio
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from workbench.config import settings
from workbench.db import PatchAudit, PatchCandidate, sessions
from workbench.evaluator.experiment_catalog import TASK_IDS, task
from workbench.patch_audit.admission import admit
from workbench.patch_audit.curated import examples
from workbench.patch_audit.service import public_task, saved_candidate, store_candidate, view


def local_only(request: Request):
    if settings.guest_access or request.url.hostname not in (
        "127.0.0.1",
        "localhost",
        "::1",
        "testserver",
    ):
        raise HTTPException(
            403, "Patch Audit import and execution require trusted local owner mode"
        )
    origin = request.headers.get("origin")
    if origin and origin not in (settings.allowed_origin, "http://localhost:8010"):
        raise HTTPException(403, "Cross-origin Patch Audit access is not allowed")


router = APIRouter(prefix="/api/patch-audits", dependencies=[Depends(local_only)])


class Import(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(max_length=80)
    patch: str = Field(max_length=65536)
    category: Literal["user_declared", "unknown", "human"] = "unknown"
    producer_label: str = Field(default="", max_length=200)
    producer: str = Field(default="", max_length=200)
    source_reference: str = Field(default="", max_length=500)


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(max_length=70)
    candidate_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    record_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm_local_execution: Literal[True]


@router.get("/tasks")
async def tasks():
    return [
        public_task(task(i))
        for i in ("boltons-addlist", *[x for x in TASK_IDS if x != "boltons-addlist"])
    ]


@router.get("/examples")
async def presets():
    rows = await asyncio.to_thread(examples)
    return [
        {
            "key": k,
            "label": v["label"],
            "task_id": v["candidate"]["task_id"],
            "category": v["candidate"]["provenance"]["category"],
        }
        for k, v in rows.items()
    ]


@router.get("/examples/{key}")
async def preset(key: str):
    rows = await asyncio.to_thread(examples)
    if key not in rows:
        raise HTTPException(404, "Curated example not found")
    return await store_candidate(rows[key]["candidate"])


@router.post("/candidates", status_code=201)
async def import_patch(payload: Import):
    provenance = payload.model_dump(exclude={"task_id", "patch"})
    provenance["limitations"] = (
        "User-declared metadata; authorship and generation conditions are "
        "unverified. Auditing is independent of authorship."
    )
    try:
        value = await asyncio.to_thread(admit, payload.task_id, payload.patch, provenance)
        return await store_candidate(value)
    except (ValueError, TimeoutError) as error:
        raise HTTPException(422, str(error)) from None


@router.get("/candidates")
async def candidates():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(PatchCandidate).order_by(PatchCandidate.created_at.desc()).limit(100)
            )
        ).all()
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "candidate_hash": r.candidate_hash,
            "provenance": r.record["provenance"],
        }
        for r in rows
    ]


@router.get("/candidates/{candidate_id}")
async def candidate(candidate_id: str):
    return await saved_candidate(candidate_id)


@router.get("/candidates/{candidate_id}/patch")
async def patch(candidate_id: str):
    c = await saved_candidate(candidate_id)
    return PlainTextResponse(
        c["patch"], headers={"Content-Disposition": f'attachment; filename="{candidate_id}.patch"'}
    )


@router.post("/runs", status_code=202)
async def start(payload: Confirm, request: Request):
    if request.app.state.evaluations.jobs:
        raise HTTPException(429, "The evaluator is occupied")
    return await request.app.state.patch_audits.create(
        payload.candidate_id, payload.candidate_hash, payload.record_hash
    )


@router.get("/runs")
async def history():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(PatchAudit).order_by(PatchAudit.created_at.desc()).limit(100)
            )
        ).all()
    return [{k: v for k, v in view(row).items() if k != "evidence"} for row in rows]


@router.get("/runs/{audit_id}")
async def saved(audit_id: UUID):
    async with sessions() as session:
        row = await session.get(PatchAudit, audit_id)
        if row is None:
            raise HTTPException(404, "Audit not found")
        return view(row)


@router.get("/runs/{audit_id}/evidence")
async def evidence(audit_id: UUID):
    return JSONResponse(
        await saved(audit_id),
        headers={"Content-Disposition": f'attachment; filename="patch-audit-{audit_id}.json"'},
    )


@router.post("/runs/{audit_id}/cancel")
async def cancel(audit_id: UUID, request: Request):
    return await request.app.state.patch_audits.cancel(audit_id)
