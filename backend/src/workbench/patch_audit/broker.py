"""Private admitted-patch endpoint on the existing single-capacity Docker broker."""

import asyncio
import json
import threading
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from workbench.evaluator import broker
from workbench.evaluator.experiment_catalog import task
from workbench.patch_audit.admission import rebuild
from workbench.patch_audit.execution import evaluate

app = broker.app


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: dict[str, Any]


@app.post("/audits/{audit_id}")
async def audit(audit_id: UUID, payload: AuditRequest):
    try:
        value = await asyncio.to_thread(rebuild, payload.candidate)
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, "Candidate admission failed") from error
    async with broker.LOCK:
        if broker.ACTIVE:
            raise HTTPException(429, "Evaluator capacity is occupied")
        path = broker.ROOT / f"{audit_id}.json"
        claim = broker.ROOT / f"{audit_id}.audit-claim"
        try:
            with claim.open("x") as file:
                file.write(value["record_hash"])
        except FileExistsError:
            raise HTTPException(
                409, "Audit execution ID already claimed; create a new audit"
            ) from None
        if path.exists():
            raise HTTPException(409, "Execution evidence already exists")
        event = broker.ACTIVE[audit_id] = threading.Event()
        if audit_id in broker.PENDING_CANCEL:
            event.set()
            broker.PENDING_CANCEL.discard(audit_id)
        broker.IDLE.clear()
    try:
        try:
            result = await asyncio.to_thread(evaluate, task(value["task_id"]), value, event)
        except Exception as error:
            result = {
                "status": "infrastructure_error",
                "reason": type(error).__name__,
                "candidate_hash": value["candidate_hash"],
            }
        envelope = {
            "audit_id": str(audit_id),
            "candidate_id": value["id"],
            "record_hash": value["record_hash"],
            "result": result,
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(envelope))
        temporary.replace(path)
        return envelope
    finally:
        broker.ACTIVE.pop(audit_id, None)
        if not broker.ACTIVE:
            broker.IDLE.set()
