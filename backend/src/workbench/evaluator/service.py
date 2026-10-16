"""Persist task, producer, patch and execution evidence without rerunning generation."""

import asyncio
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from workbench.config import settings
from workbench.db import Evaluation, sessions
from workbench.evaluator import behavior
from workbench.evaluator.catalog import candidate, identity, public_candidate, task
from workbench.evaluator.runner import POLICY, verifier_id


def view(row: Evaluation):
    return {
        "id": str(row.id),
        "task_id": row.task_id,
        "candidate_id": row.candidate_id,
        "candidate_hash": row.candidate_hash,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "evidence": row.evidence,
    }


class EvaluationManager:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.jobs: dict[UUID, asyncio.Task] = {}

    async def recover(self):
        async with sessions.begin() as session:
            rows = (
                await session.scalars(select(Evaluation).where(Evaluation.status == "running"))
            ).all()
            for row in rows:
                # Reconcile terminal broker evidence before calling a run interrupted.
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.get(
                            f"{settings.evaluator_url}/evaluations/{row.id}"
                        )
                        if response.status_code == 200:
                            result = response.json()
                            validate_binding(row.evidence, result, row.candidate_hash)
                            row.status = result["status"]
                            row.evidence = {**row.evidence, "result": result}
                            continue
                        await client.post(f"{settings.evaluator_url}/evaluations/{row.id}/cancel")
                except Exception:
                    pass
                row.status = "interrupted"
                row.evidence = {**row.evidence, "reason": "Coordinator restarted; no pass inferred"}
                row.updated_at = datetime.now(UTC)

    async def create(self, candidate_id: str):
        async with self.lock:
            return await self.admit(candidate_id)

    async def admit(self, candidate_id: str):
        if self.jobs:
            raise HTTPException(429, "An evaluation is already running")
        try:
            value = candidate(candidate_id)
            spec = task(value["task_id"])
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        row = Evaluation(
            id=uuid4(),
            task_id=value["task_id"],
            candidate_id=candidate_id,
            candidate_hash=value["candidate_hash"],
            status="running",
            evidence={
                "task": {k: v for k, v in spec.items() if k != "files"},
                "candidate": public_candidate(value),
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        async with sessions.begin() as session:
            session.add(row)
        self.jobs[row.id] = asyncio.create_task(self.run(row.id, value))
        return view(row)

    async def run(self, evaluation_id, value):
        try:
            async with httpx.AsyncClient(timeout=100) as client:
                response = await client.post(
                    f"{settings.evaluator_url}/evaluations/{evaluation_id}",
                    json={"candidate_id": value["id"], "candidate_hash": value["candidate_hash"]},
                )
                response.raise_for_status()
                result = response.json()
            async with sessions.begin() as session:
                row = await session.get(Evaluation, evaluation_id)
                assert row
                validate_binding(row.evidence, result, row.candidate_hash)
                row.status = result["status"]
                row.updated_at = datetime.now(UTC)
                row.evidence = {**row.evidence, "result": result}
        except Exception as error:
            # A lost broker response must not leave code running without a coordinator.
            await self.stop(evaluation_id)
            async with sessions.begin() as session:
                row = await session.get(Evaluation, evaluation_id)
                assert row
                row.status = "infrastructure_error"
                row.updated_at = datetime.now(UTC)
                row.evidence = {**row.evidence, "reason": type(error).__name__}
        finally:
            self.jobs.pop(evaluation_id, None)

    async def stop(self, evaluation_id):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{settings.evaluator_url}/evaluations/{evaluation_id}/cancel")
        except httpx.HTTPError:
            pass

    async def close(self):
        for key in list(self.jobs):
            await self.stop(key)
        await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)


def validate_binding(evidence, result, candidate_hash):
    if result.get("candidate_hash") != candidate_hash:
        raise ValueError("Result candidate identity mismatch")
    if result.get("status") == "infrastructure_error" and not result.get("binding"):
        return
    binding = result["binding"]
    if identity(binding) != result["binding_hash"]:
        raise ValueError("Result binding integrity mismatch")
    required = {
        "verifier_hash": verifier_id(evidence["task"]["id"]),
        "policy_hash": identity(POLICY),
        "candidate_hash": candidate_hash,
        "spec_hash": evidence["task"]["spec_hash"],
        "base_commit": evidence["task"]["base_commit"],
        "task_id": evidence["task"]["id"],
        "patch_hash": evidence["candidate"]["patch_hash"],
        "executed_file_hashes": evidence["candidate"]["source_hashes"],
    }
    if any(binding.get(k) != v for k, v in required.items()):
        raise ValueError("Result belongs to a different evaluation input")
    image_id = binding.get("image_id", "")
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise ValueError("Missing execution environment identity")
    for phase in ("ordinary", "independent"):
        execution = result.get(phase)
        if execution and execution.get("image_id") != image_id:
            raise ValueError("Phase executed in a different environment")
        if execution and execution.get("executed_file_hashes"):
            expected_files = evidence["candidate"]["source_hashes"]
            if phase == "independent":
                expected_files = {
                    k: v for k, v in expected_files.items() if not k.startswith("tests/")
                }
            if execution["executed_file_hashes"] != expected_files:
                raise ValueError("Phase source identity mismatch")
    if result["status"] == "passed":
        if not result.get("ordinary") or not result.get("independent"):
            raise ValueError("Missing check evidence")
        if any(
            not result[phase].get("executed_file_hashes") or not result[phase].get("container_id")
            for phase in ("ordinary", "independent")
        ):
            raise ValueError("Missing executed source or container evidence")
        if result["ordinary"].get("outcome") != "passed":
            raise ValueError("Ordinary result did not pass")
        checks = result["independent"].get("checks", [])
        recomputed = behavior.compare(evidence["task"]["id"], result["independent"]["stdout"])
        if checks != recomputed or any(
            result[phase].get("exit_code") != 0 or result[phase].get("status") != "finished"
            for phase in ("ordinary", "independent")
        ):
            raise ValueError("Recorded pass differs from actual execution evidence")
        if not checks or any(c["status"] != "passed" for c in checks):
            raise ValueError("Independent evidence did not pass")
