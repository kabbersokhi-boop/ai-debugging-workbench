"""Private Docker coordinator. Only catalog IDs are accepted; never commands or URLs."""

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from workbench.evaluator.catalog import candidate, task
from workbench.evaluator.runner import cleanup_all, evaluate

ROOT = Path(os.environ.get("EVALUATOR_ARTIFACT_DIR", "/tmp/workbench-evaluations"))
ACTIVE: dict[UUID, threading.Event] = {}
PENDING_CANCEL: set[UUID] = set()
LOCK = asyncio.Lock()
IDLE = asyncio.Event()
IDLE.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(ROOT.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(cleanup_all)
    yield
    for event in ACTIVE.values():
        event.set()
    await IDLE.wait()


app = FastAPI(lifespan=lifespan)


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    candidate_hash: str


@app.get("/health")
async def health():
    return {"status": "ready"}


@app.post("/evaluations/{evaluation_id}")
async def run(evaluation_id: UUID, payload: Request):
    async with LOCK:
        if ACTIVE:
            raise HTTPException(429, "Evaluator capacity is occupied")
        try:
            value = candidate(payload.candidate_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        if payload.candidate_hash != value["candidate_hash"]:
            raise HTTPException(409, "Candidate hash mismatch")
        path = ROOT / f"{evaluation_id}.json"
        if path.exists():
            raise HTTPException(409, "Evaluation evidence already exists")
        event = ACTIVE[evaluation_id] = threading.Event()
        if evaluation_id in PENDING_CANCEL:
            event.set()
            PENDING_CANCEL.discard(evaluation_id)
        IDLE.clear()
    try:
        try:
            result = await asyncio.to_thread(evaluate, task(value["task_id"]), value, event)
        except Exception as error:
            result = {"status": "infrastructure_error", "reason": type(error).__name__}
        result["candidate_hash"] = value["candidate_hash"]
        # Atomic publication of terminal evidence; never overwrite earlier runs.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result))
        temporary.replace(path)
        return result
    finally:
        ACTIVE.pop(evaluation_id, None)
        if not ACTIVE:
            IDLE.set()


@app.post("/evaluations/{evaluation_id}/cancel")
async def cancel(evaluation_id: UUID):
    if event := ACTIVE.get(evaluation_id):
        event.set()
    elif len(PENDING_CANCEL) < 128:
        PENDING_CANCEL.add(evaluation_id)
    return {"status": "cancellation_requested"}


@app.get("/evaluations/{evaluation_id}")
async def get(evaluation_id: UUID):
    path = ROOT / f"{evaluation_id}.json"
    if not path.is_file():
        raise HTTPException(404, "No terminal evidence")
    return json.loads(path.read_text())
