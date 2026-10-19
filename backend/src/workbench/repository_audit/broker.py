"""Install private G1 handlers on the existing broker and its single execution capacity."""

import asyncio
import json
import threading
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from workbench.evaluator import broker
from workbench.evaluator.catalog import identity
from workbench.repository_audit.admission import check_plan, rebuild
from workbench.repository_audit.execution import engine_id, evaluate, runtimes


class Approved(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot: dict[str, Any]
    candidate: dict[str, Any]
    plan: dict[str, Any]
    engine_id: str
    approval: dict[str, Any]


def install(app):
    @app.get("/repository-runtimes")
    async def runtime_options():
        return await asyncio.to_thread(runtimes)

    @app.post("/repository-audits/{audit_id}")
    async def execute(audit_id: UUID, payload: Approved):
        try:
            await asyncio.to_thread(rebuild, payload.snapshot, payload.candidate)
            check_plan(payload.snapshot, payload.candidate, payload.plan)
            if (
                payload.engine_id != engine_id()
                or payload.approval.get("local_owner") is not True
                or payload.approval.get("plan_id") != identity(payload.plan)
                or payload.approval.get("candidate_id") != payload.candidate["id"]
            ):
                raise ValueError("Missing exact local-owner execution approval")
        except (ValueError, KeyError, TypeError) as error:
            raise HTTPException(422, "Repository execution admission failed") from error
        async with broker.LOCK:
            if broker.ACTIVE:
                raise HTTPException(429, "Evaluator capacity is occupied")
            path = broker.ROOT / f"{audit_id}.json"
            try:
                with (broker.ROOT / f"{audit_id}.repository-claim").open("x") as claim:
                    claim.write(identity(payload.model_dump()))
            except FileExistsError:
                raise HTTPException(
                    409, "Audit UUID already claimed; create a new execution"
                ) from None
            if path.exists():
                raise HTTPException(409, "Terminal evidence already exists")
            event = broker.ACTIVE[audit_id] = threading.Event()
            if audit_id in broker.PENDING_CANCEL:
                event.set()
                broker.PENDING_CANCEL.discard(audit_id)
            broker.IDLE.clear()
        try:
            result = await asyncio.to_thread(
                evaluate, audit_id, payload.snapshot, payload.candidate, payload.plan, event
            )
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result))
            temporary.replace(path)
            return result
        finally:
            broker.ACTIVE.pop(audit_id, None)
            if not broker.ACTIVE:
                broker.IDLE.set()
