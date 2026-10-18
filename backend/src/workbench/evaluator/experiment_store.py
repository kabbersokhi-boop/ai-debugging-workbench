"""Insert validated, immutable trial snapshots and existing PostgreSQL evaluation history."""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select

from workbench.db import ComparisonTrial, Evaluation, sessions
from workbench.evaluator.catalog import identity, public_candidate
from workbench.evaluator.experiment import assert_frozen, comparison, trial_public, validate_trial
from workbench.evaluator.experiment_catalog import build_candidate, freeze, task

NAMESPACE = UUID("c5e6e566-a33e-48e6-8853-33e29df052b1")


async def insert(record, frozen):
    assert_frozen(frozen)
    validate_trial(record, frozen)
    generation = record["generation"]
    trial_id = generation["id"]
    coordinate = generation["coordinate"]
    result, c = record.get("result"), record.get("candidate")
    evaluation_id = uuid5(NAMESPACE, frozen["hash"] + trial_id) if result else None
    snapshot = {**record, "evaluation_id": str(evaluation_id) if evaluation_id else None}
    async with sessions.begin() as session:
        existing = await session.get(ComparisonTrial, trial_id)
        if existing:
            if existing.record_hash != identity(snapshot):
                raise ValueError("Stored trial is immutable; conflicting import")
            return
        if result:
            assert c is not None
            spec = task(c["task_id"])
            full = build_candidate(spec, c)
            session.add(
                Evaluation(
                    id=evaluation_id,
                    task_id=spec["id"],
                    candidate_id=c["id"],
                    candidate_hash=full["candidate_hash"],
                    status=result["status"],
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    evidence={
                        "task": {k: v for k, v in spec.items() if k != "files"},
                        "candidate": public_candidate(full),
                        "result": result,
                        "comparison_trial_id": trial_id,
                        "freeze_hash": frozen["hash"],
                    },
                )
            )
            await session.flush()
        session.add(
            ComparisonTrial(
                id=trial_id,
                experiment_id=frozen["body"]["id"],
                task_id=coordinate["task_id"],
                configuration_id=coordinate["configuration_id"],
                trial_index=coordinate["trial"],
                record_hash=identity(snapshot),
                evidence=snapshot,
                evaluation_id=evaluation_id,
            )
        )


async def records():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(ComparisonTrial).where(ComparisonTrial.experiment_id == "m02-v1")
            )
        ).all()
        values = []
        for row in rows:
            if (
                identity(row.evidence) != row.record_hash
                or row.evidence["generation"]["id"] != row.id
            ):
                raise ValueError("Stored trial integrity failure")
            values.append(row.evidence)
        return values


async def summary():
    frozen = freeze()
    assert_frozen(frozen)
    return comparison(await records(), frozen)


async def detail(trial_id):
    frozen = freeze()
    assert_frozen(frozen)
    async with sessions() as session:
        row = await session.get(ComparisonTrial, trial_id)
        if row is None:
            raise ValueError("Trial has not been imported")
        if identity(row.evidence) != row.record_hash:
            raise ValueError("Stored trial integrity failure")
        validate_trial(row.evidence, frozen)
        return trial_public(row.evidence)
