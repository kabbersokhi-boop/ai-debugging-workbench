"""Separate immutable imports and durable fresh audit executions in existing PostgreSQL."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from workbench.config import settings
from workbench.db import PatchAudit, PatchCandidate, sessions
from workbench.evaluator.catalog import identity
from workbench.evaluator.experiment_catalog import task
from workbench.patch_audit.admission import rebuild
from workbench.patch_audit.execution import validate, verifier_id


def public_task(spec):
    return {k: v for k, v in spec.items() if k != "files"}


def validate_envelope(audit_id, candidate, envelope, expected_verifier=None):
    if (
        envelope.get("audit_id") != str(audit_id)
        or envelope.get("candidate_id") != candidate["id"]
        or envelope.get("record_hash") != candidate["record_hash"]
    ):
        raise ValueError("Audit execution identity mismatch")
    validate(task(candidate["task_id"]), rebuild(candidate), envelope["result"], expected_verifier)


def view(row):
    evidence = row.evidence
    status = row.status
    try:
        value = evidence["candidate"]
        rebuild(value)
        if (
            row.candidate_id != value["id"]
            or row.candidate_hash != value["candidate_hash"]
            or evidence["task"] != public_task(task(value["task_id"]))
        ):
            raise ValueError("Saved audit input mismatch")
        if "envelope" in evidence:
            if evidence.get("envelope_hash") != identity(evidence["envelope"]):
                raise ValueError("Saved result integrity failure")
            validate_envelope(
                row.id, value, evidence["envelope"], evidence.get("execution_verifier")
            )
            if status != evidence["envelope"]["result"]["status"] and not (
                status == "cancelled" and evidence.get("cancel_requested")
            ):
                raise ValueError("Saved audit status mismatch")
        elif status in ("passed", "failed", "timeout", "invalid_candidate"):
            raise ValueError("Missing execution evidence")
    except (ValueError, KeyError, TypeError, AttributeError):
        status = "invalid_evidence"
        evidence = {
            **evidence,
            "reason": "Stored evidence failed validation; no passing conclusion is available.",
        }
        if "envelope" in evidence:
            evidence = {**evidence, "unvalidated_envelope": evidence["envelope"]}
        evidence = {k: v for k, v in evidence.items() if k != "envelope"}
    return {
        "id": str(row.id),
        "candidate_id": row.candidate_id,
        "candidate_hash": row.candidate_hash,
        "status": status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "execution_mode": "fresh_local",
        "provenance_category": evidence.get("candidate", {})
        .get("provenance", {})
        .get("category", "unknown"),
        "candidate_label": evidence.get("candidate", {}).get("provenance", {}).get("producer_label")
        or "Imported patch",
        "evidence": evidence,
    }


async def store_candidate(value):
    rebuild(value)
    async with sessions.begin() as session:
        await session.execute(
            insert(PatchCandidate)
            .values(
                id=value["id"],
                task_id=value["task_id"],
                candidate_hash=value["candidate_hash"],
                record=value,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        row = await session.get(PatchCandidate, value["id"])
        if row is None or row.record != value:
            raise ValueError("Immutable candidate collision")
    return value


async def saved_candidate(candidate_id):
    async with sessions() as session:
        row = await session.get(PatchCandidate, candidate_id)
        if row is None:
            raise HTTPException(404, "Saved candidate not found")
        try:
            rebuild(row.record)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(409, "Stored candidate evidence is invalid") from None
        return row.record


class AuditManager:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.jobs = {}

    async def create(self, candidate_id, candidate_hash, record_hash):
        async with self.lock:
            if self.jobs:
                raise HTTPException(429, "A patch audit is already running")
            value = await saved_candidate(candidate_id)
            if value["candidate_hash"] != candidate_hash or value["record_hash"] != record_hash:
                raise HTTPException(409, "Confirmation belongs to a different candidate")
            now = datetime.now(UTC)
            row = PatchAudit(
                id=uuid4(),
                candidate_id=value["id"],
                candidate_hash=value["candidate_hash"],
                status="running",
                evidence={
                    "task": public_task(task(value["task_id"])),
                    "candidate": value,
                    "execution_verifier": verifier_id(value["task_id"]),
                },
                created_at=now,
                updated_at=now,
            )
            async with sessions.begin() as session:
                session.add(row)
            self.jobs[row.id] = asyncio.create_task(self.run(row.id, value))
            return view(row)

    async def terminal(self, audit_id):
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.evaluator_url}/evaluations/{audit_id}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    async def wait_terminal(self, audit_id):
        try:
            async with asyncio.timeout(8):
                while True:
                    envelope = await self.terminal(audit_id)
                    if envelope is not None:
                        return envelope
                    await asyncio.sleep(0.2)
        except TimeoutError:
            return None

    async def finish(self, audit_id, value, envelope):
        async with sessions.begin() as session:
            row = await session.get(PatchAudit, audit_id, with_for_update=True)
            assert row
            if row.status != "running":
                return
            validate_envelope(audit_id, value, envelope, row.evidence.get("execution_verifier"))
            row.status = (
                "cancelled"
                if row.evidence.get("cancel_requested")
                else envelope["result"]["status"]
            )
            row.evidence = {
                **row.evidence,
                "envelope": envelope,
                "envelope_hash": identity(envelope),
            }
            row.updated_at = datetime.now(UTC)

    async def failure(self, audit_id, status, reason, unvalidated=None):
        async with sessions.begin() as session:
            row = await session.get(PatchAudit, audit_id, with_for_update=True)
            assert row
            if row.status != "running":
                return
            row.status = "cancelled" if row.evidence.get("cancel_requested") else status
            row.evidence = {**row.evidence, "reason": reason}
            if unvalidated is not None:
                row.evidence = {**row.evidence, "unvalidated_envelope": unvalidated}
            row.updated_at = datetime.now(UTC)

    async def run(self, audit_id, value):
        envelope = None
        try:
            async with httpx.AsyncClient(timeout=95) as client:
                r = await client.post(
                    f"{settings.evaluator_url}/audits/{audit_id}", json={"candidate": value}
                )
                r.raise_for_status()
                envelope = r.json()
            await self.finish(audit_id, value, envelope)
        except (ValueError, KeyError, TypeError):
            await self.stop(audit_id)
            await self.failure(
                audit_id,
                "invalid_evidence",
                "Broker evidence failed validation; no pass inferred",
                envelope,
            )
        except Exception as error:
            await self.stop(audit_id)
            try:
                envelope = await self.wait_terminal(audit_id)
                if envelope:
                    await self.finish(audit_id, value, envelope)
                else:
                    await self.failure(audit_id, "infrastructure_error", type(error).__name__)
            except Exception:
                await self.failure(audit_id, "infrastructure_error", type(error).__name__)
        finally:
            self.jobs.pop(audit_id, None)

    async def stop(self, audit_id):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{settings.evaluator_url}/evaluations/{audit_id}/cancel")
        except httpx.HTTPError:
            pass

    async def cancel(self, audit_id):
        async with sessions.begin() as session:
            row = await session.get(PatchAudit, audit_id, with_for_update=True)
            if row is None:
                raise HTTPException(404, "Audit not found")
            if row.status != "running":
                return view(row)
            row.evidence = {**row.evidence, "cancel_requested": True}
            row.updated_at = datetime.now(UTC)
        await self.stop(audit_id)
        return {"status": "cancellation_requested"}

    async def recover(self):
        async with sessions() as session:
            rows = (
                await session.scalars(select(PatchAudit).where(PatchAudit.status == "running"))
            ).all()
        for row in rows:
            envelope = None
            try:
                envelope = await self.wait_terminal(row.id)
                if envelope:
                    await self.finish(row.id, row.evidence["candidate"], envelope)
                    continue
            except (ValueError, KeyError, TypeError):
                await self.failure(
                    row.id, "invalid_evidence", "Restart found invalid broker evidence", envelope
                )
                continue
            except Exception:
                pass
            await self.stop(row.id)
            await self.failure(
                row.id,
                "interrupted",
                "Coordinator restarted without validated terminal evidence; no checks inferred",
            )

    async def close(self):
        for key in list(self.jobs):
            await self.stop(key)
        await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)
