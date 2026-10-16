from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from workbench.config import settings
from workbench.db import Evaluation, sessions
from workbench.evaluator.catalog import CATALOG, TASK_IDS, candidate, public_candidate, task
from workbench.evaluator.service import view


def local_only():
    if settings.guest_access:
        raise HTTPException(403, "Agent evaluation is available only in the approved local mode")


router = APIRouter(prefix="/api/evaluator", dependencies=[Depends(local_only)])


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str


@router.get("/tasks")
async def tasks():
    return [{k: v for k, v in task(i).items() if k != "files"} for i in TASK_IDS]


@router.get("/candidates")
async def candidates():
    values = [candidate(p.stem) for p in sorted((CATALOG / "candidates").glob("*.json"))]
    return [
        {
            k: v
            for k, v in c.items()
            if k not in ("files", "original", "modified", "patch", "generation")
        }
        for c in values
    ]


@router.get("/candidates/{candidate_id}")
async def detail(candidate_id: str):
    try:
        return public_candidate(candidate(candidate_id))
    except ValueError as error:
        raise HTTPException(404, str(error)) from None


@router.get("/runs")
async def history():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(Evaluation).order_by(Evaluation.created_at.desc()).limit(100)
            )
        ).all()
        return [{k: v for k, v in view(row).items() if k != "evidence"} for row in rows]


@router.post("/runs", status_code=202)
async def start(payload: Create, request: Request):
    return await request.app.state.evaluations.create(payload.candidate_id)


async def saved(evaluation_id: UUID):
    async with sessions() as session:
        row = await session.get(Evaluation, evaluation_id)
        if row is None:
            raise HTTPException(404, "Evaluation not found")
        return view(row)


@router.get("/runs/{evaluation_id}")
async def get(evaluation_id: UUID):
    return await saved(evaluation_id)


@router.get("/runs/{evaluation_id}/evidence")
async def evidence(evaluation_id: UUID):
    return JSONResponse(
        await saved(evaluation_id),
        headers={"Content-Disposition": f'attachment; filename="evaluation-{evaluation_id}.json"'},
    )


@router.post("/runs/{evaluation_id}/cancel")
async def cancel(evaluation_id: UUID, request: Request):
    await saved(evaluation_id)
    await request.app.state.evaluations.stop(evaluation_id)
    return {"status": "cancellation_requested"}
