"""PostgreSQL persistence, validation on reopen and cancellation/restart reconciliation."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from workbench.config import settings
from workbench.db import (
    RepositoryAudit,
    RepositoryCandidate,
    RepositoryPlan,
    RepositorySource,
    RepositoryVerificationPlan,
    sessions,
)
from workbench.evaluator.catalog import identity
from workbench.repository_audit import independent
from workbench.repository_audit.admission import check_plan, rebuild
from workbench.repository_audit.execution import engine_id, validate


async def store(model, record, **columns):
    async with sessions.begin() as session:
        await session.execute(
            insert(model)
            .values(id=record["id"], record=record, **columns)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        row = await session.get(model, record["id"])
        if row is None or row.record != record:
            raise ValueError("Immutable repository record collision")
    return record


async def load(model, key):
    async with sessions() as session:
        row = await session.get(model, key)
        if row is None:
            raise HTTPException(404, "Saved repository audit material not found")
        return row.record


async def material(candidate_id, plan_id=None) -> Any:
    candidate = await load(RepositoryCandidate, candidate_id)
    snapshot = await load(RepositorySource, candidate["snapshot_id"])
    await asyncio.to_thread(rebuild, snapshot, candidate)
    if plan_id:
        plan = await load(RepositoryPlan, plan_id)
        if identity(plan["plan"]) != plan_id:
            raise ValueError("Stored plan identity mismatch")
        check_plan(snapshot, candidate, plan["plan"])
        return snapshot, candidate, plan["plan"]
    return snapshot, candidate


def validate_result(result, audit_id, evidence):
    if evidence.get("verification"):
        independent.validate(result, audit_id, evidence)
    else:
        validate(
            result,
            audit_id,
            evidence["snapshot"],
            evidence["candidate"],
            evidence["plan"],
            evidence["engine_id"],
        )


def validate_saved(evidence, audit_id):
    snapshot, candidate, plan = (evidence[k] for k in ("snapshot", "candidate", "plan"))
    rebuild(snapshot, candidate)
    check_plan(snapshot, candidate, plan)
    approval = evidence["approval"]
    if (
        approval.get("local_owner") is not True
        or approval.get("candidate_id") != candidate["id"]
        or approval.get("plan_id") != identity(plan)
        or not approval.get("approved_at")
    ):
        raise ValueError("Missing exact candidate/plan approval evidence")
    if evidence.get("verification"):
        independent.check(evidence, historical=True)
    if evidence.get("result") is not None:
        if identity(evidence["result"]) != evidence.get("result_hash"):
            raise ValueError("Saved result hash mismatch")
        validate_result(evidence["result"], audit_id, evidence)


def view(row):
    evidence, status = row.evidence, row.status
    try:
        validate_saved(evidence, row.id)
        if status in (
            "completed",
            "ordinary_failed",
            "checks_passed",
            "assertions_failed",
            "validation_passed",
            "validation_failed",
            "check_execution_failed",
            "verifier_preparation_failed",
            "tests_passed",
            "tests_failed",
            "environment_preparation_failed",
        ) and not evidence.get("result"):
            raise ValueError("Missing terminal execution evidence")
        if row.candidate_id != evidence["candidate"]["id"] or row.plan_id != identity(
            evidence["plan"]
        ):
            raise ValueError("Saved row belongs to another candidate or plan")
        if (
            evidence.get("result")
            and status not in ("cancelled", "running")
            and evidence["result"]["status"] != status
        ):
            raise ValueError("Saved outcome mismatch")
    except (ValueError, KeyError, TypeError):
        status = "invalid_evidence"
        evidence = {
            **evidence,
            "reason": "Saved evidence failed validation; no passing result is available.",
        }
        if "result" in evidence:
            evidence["unvalidated_result"] = evidence.pop("result")
    return {
        "id": str(row.id),
        "candidate_id": row.candidate_id,
        "plan_id": row.plan_id,
        "status": status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "execution_mode": "fresh_local",
        "evidence": evidence,
    }


class RepositoryAuditManager:
    def __init__(self):
        self.jobs = {}

    async def create(
        self,
        candidate_id,
        plan_id,
        verification_id=None,
        validation_run_id=None,
        stage="execution",
        approve_independent_plan=False,
    ):
        snapshot, candidate, plan = await material(candidate_id, plan_id)
        extra = {}
        if verification_id is not None:
            verification = await load(RepositoryVerificationPlan, verification_id)
            extra = {
                "verification": verification,
                "stage": stage,
                "ordinary_engine_id": engine_id(),
                "engine_id": independent.engine_id(),
            }
            if stage == "execution":
                if not validation_run_id:
                    raise ValueError("Run and inspect verifier controls before approving execution")
                async with sessions() as session:
                    validated = await session.get(RepositoryAudit, UUID(validation_run_id))
                if validated is None or view(validated)["status"] != "validation_passed":
                    raise ValueError("No valid completed independent validation exists")
                extra["validation"] = {
                    "audit_id": str(validated.id),
                    "result": validated.evidence["result"],
                }
        elif stage != "execution" or validation_run_id or approve_independent_plan:
            raise ValueError("Independent execution requires an explicit verification plan")
        now = datetime.now(UTC)
        row = RepositoryAudit(
            id=uuid4(),
            candidate_id=candidate_id,
            plan_id=plan_id,
            status="running",
            created_at=now,
            updated_at=now,
            evidence={
                "snapshot": snapshot,
                "candidate": candidate,
                "plan": plan,
                "engine_id": engine_id(),
                "approval": {
                    "local_owner": True,
                    "plan_id": plan_id,
                    "candidate_id": candidate_id,
                    "approved_at": now.isoformat(),
                    **(
                        {
                            "verification_id": verification_id,
                            "stage": stage,
                            "approve_independent_plan": approve_independent_plan,
                        }
                        if verification_id
                        else {}
                    ),
                },
                **extra,
            },
        )
        if verification_id:
            independent.check(row.evidence)
        async with sessions.begin() as session:
            session.add(row)
        self.jobs[row.id] = asyncio.create_task(self.run(row.id, row.evidence))
        return view(row)

    async def stop(self, audit_id):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{settings.evaluator_url}/evaluations/{audit_id}/cancel")
        except httpx.HTTPError:
            pass

    async def terminal(self, audit_id):
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.evaluator_url}/evaluations/{audit_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def finish(self, audit_id, result=None, failure=None, unvalidated=None):
        async with sessions.begin() as session:
            row = await session.get(RepositoryAudit, audit_id, with_for_update=True)
            assert row
            if row.status != "running":
                return
            evidence = row.evidence
            if result is not None:
                validate_result(result, audit_id, evidence)
                row.status = result["status"]
                row.evidence = {**evidence, "result": result, "result_hash": identity(result)}
            else:
                row.status = failure or "infrastructure_error"
                row.evidence = {
                    **evidence,
                    "reason": "No validated terminal broker evidence; no test result inferred.",
                }
                if unvalidated is not None:
                    row.evidence = {**row.evidence, "unvalidated_result": unvalidated}
            if evidence.get("cancel_requested"):
                row.status = "cancelled"
            row.updated_at = datetime.now(UTC)

    async def run(self, audit_id, evidence):
        result = None
        try:
            async with httpx.AsyncClient(timeout=420) as client:
                response = await client.post(
                    f"{settings.evaluator_url}/repository-audits/{audit_id}", json=evidence
                )
                response.raise_for_status()
                result = response.json()
                await self.finish(audit_id, result)
        except Exception:
            await self.stop(audit_id)
            try:
                result = await self.wait_terminal(audit_id)
                await self.finish(audit_id, result, "infrastructure_error")
            except (ValueError, KeyError, TypeError):
                await self.finish(audit_id, failure="invalid_evidence", unvalidated=result)
            except Exception:
                await self.finish(audit_id, failure="infrastructure_error", unvalidated=result)
        finally:
            self.jobs.pop(audit_id, None)

    async def wait_terminal(self, audit_id):
        async with asyncio.timeout(12):
            while True:
                result = await self.terminal(audit_id)
                if result is not None:
                    return result
                await asyncio.sleep(0.3)

    async def cancel(self, audit_id):
        async with sessions.begin() as session:
            row = await session.get(RepositoryAudit, audit_id, with_for_update=True)
            if row is None:
                raise HTTPException(404, "Audit not found")
            if row.status != "running":
                return view(row)
            row.evidence = {**row.evidence, "cancel_requested": True}
        await self.stop(audit_id)
        return {"status": "cancellation_requested"}

    async def recover(self):
        async with sessions() as session:
            rows = (
                await session.scalars(
                    select(RepositoryAudit).where(RepositoryAudit.status == "running")
                )
            ).all()
        for row in rows:
            await self.stop(row.id)
            try:
                result = await self.wait_terminal(row.id)
                await self.finish(row.id, result)
            except (ValueError, KeyError, TypeError):
                await self.finish(row.id, failure="invalid_evidence")
            except Exception:
                await self.finish(row.id, failure="interrupted")

    async def close(self):
        for key in list(self.jobs):
            await self.stop(key)
        await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)
