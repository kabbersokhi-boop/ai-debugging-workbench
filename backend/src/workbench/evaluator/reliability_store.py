"""Validated v2 snapshots in existing append-only PostgreSQL history; v1 store is unchanged."""

from collections import Counter
from datetime import UTC, datetime
from uuid import uuid5

from sqlalchemy import select

from workbench.db import ComparisonTrial, Evaluation, sessions
from workbench.evaluator import experiment as v1
from workbench.evaluator import reliability as v2
from workbench.evaluator.catalog import identity, public_candidate
from workbench.evaluator.experiment_catalog import build_candidate, task
from workbench.evaluator.experiment_store import NAMESPACE


def comparison(records, frozen, require_complete=True):
    v2.assert_frozen(frozen)
    seen = set()
    containers = []
    for r in records:
        v2.validate(r, frozen)
        trial_id = r["generation"]["id"]
        if trial_id in seen:
            raise ValueError("Duplicate trial")
        seen.add(trial_id)
        if r.get("result"):
            containers += [
                r["result"][p]["container_id"]
                for p in ("ordinary", "independent")
                if r["result"].get(p)
            ]
    if len(set(containers)) != len(containers):
        raise ValueError("Reused execution environment")
    complete = seen == {c["id"] for c in frozen["body"]["order"]} and all(
        v1.outcome(r) != "awaiting_evaluation" for r in records
    )
    if require_complete and not complete:
        raise ValueError("Final summary requires all attempts and submitted scores")
    groups = []
    for cid, config in frozen["body"]["configurations"].items():
        values = [r for r in records if r["generation"]["coordinate"]["configuration_id"] == cid]
        counts = Counter(v1.outcome(r) for r in values)
        responses = [e["payload"] for r in values for e in r["events"] if e["kind"] == "response"]
        usage = [r.get("usage", {}) for r in responses]
        requests = sum(r["generation"]["requests"] for r in values)
        groups.append(
            {
                "id": cid,
                "configuration": config,
                "attempted": len(values),
                "scheduled": sum(c["configuration_id"] == cid for c in frozen["body"]["order"]),
                "completed": sum(
                    counts[k]
                    for k in ("both_passed", "ordinary_failed", "additional_independent_failure")
                ),
                "outcomes": {k: counts[k] for k in v1.OUTCOMES},
                "awaiting_evaluation": counts["awaiting_evaluation"],
                "incremental_numerator": counts["additional_independent_failure"],
                "incremental_denominator": counts["both_passed"]
                + counts["additional_independent_failure"],
                "requests": requests,
                "reported_total_tokens": sum(
                    u.get("total_tokens", 0) for u in usage if isinstance(u, dict)
                ),
                "usage_missing_requests": requests
                - sum(
                    isinstance(u, dict) and isinstance(u.get("total_tokens"), int) for u in usage
                ),
                "monetary_cost": None,
                "generation_wall_ms": sum(r["generation"]["generation_wall_ms"] for r in values),
                "ordinary_tool_ms": sum(r["generation"]["ordinary_tool_ms"] for r in values),
                "evaluation_ms": sum(
                    (r.get("result", {}).get(p) or {}).get("duration_ms", 0)
                    for r in values
                    if r.get("result")
                    for p in ("ordinary", "independent")
                ),
            }
        )
    return {
        "experiment_id": "m02-v2",
        "freeze_hash": frozen["hash"],
        "complete": complete,
        "attempted": len(records),
        "scheduled": len(frozen["body"]["order"]),
        "groups": groups,
        "trials": [
            {
                "id": r["generation"]["id"],
                "coordinate": r["generation"]["coordinate"],
                "outcome": v1.outcome(r),
                "generation_status": r["generation"]["generation_status"],
                "candidate_hash": (r.get("candidate") or {}).get("candidate_hash"),
                "evaluation_id": r.get("evaluation_id"),
            }
            for r in records
        ],
        "controls_in_denominator": False,
        "generation_mode": "controlled generation plus common verification",
        "historical_m1": (
            "M1 and m02-v1 are separate historical conditions. No v1 outcome is changed or pooled."
        ),
        "limitations": frozen["body"]["limitations"],
    }


async def insert(record, frozen):
    v2.assert_frozen(frozen)
    v2.validate(record, frozen)
    g, c, result = record["generation"], record.get("candidate"), record.get("result")
    if c and not result:
        raise ValueError("Score submitted candidates before import")
    evaluation_id = uuid5(NAMESPACE, frozen["hash"] + g["id"]) if result else None
    snapshot = {**record, "evaluation_id": str(evaluation_id) if evaluation_id else None}
    async with sessions.begin() as session:
        existing = await session.get(ComparisonTrial, g["id"])
        if existing:
            if existing.record_hash != identity(snapshot):
                raise ValueError("Conflicting immutable trial")
            return
        if result:
            full = build_candidate(task(c["task_id"]), c)
            session.add(
                Evaluation(
                    id=evaluation_id,
                    task_id=c["task_id"],
                    candidate_id=c["id"],
                    candidate_hash=c["candidate_hash"],
                    status=result["status"],
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    evidence={
                        "task": {k: v for k, v in task(c["task_id"]).items() if k != "files"},
                        "candidate": public_candidate(full),
                        "result": result,
                        "comparison_trial_id": g["id"],
                        "freeze_hash": frozen["hash"],
                    },
                )
            )
            await session.flush()
        session.add(
            ComparisonTrial(
                id=g["id"],
                experiment_id="m02-v2",
                task_id=g["coordinate"]["task_id"],
                configuration_id=g["coordinate"]["configuration_id"],
                trial_index=g["coordinate"]["trial"],
                record_hash=identity(snapshot),
                evidence=snapshot,
                evaluation_id=evaluation_id,
            )
        )


async def records():
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(ComparisonTrial).where(ComparisonTrial.experiment_id == "m02-v2")
            )
        ).all()
        values = []
        for row in rows:
            if (
                identity(row.evidence) != row.record_hash
                or row.evidence["generation"]["id"] != row.id
            ):
                raise ValueError("Stored trial integrity failure")
            v2.validate(row.evidence, v2.load_freeze())
            values.append(row.evidence)
        return values


async def detail(trial_id):
    values = await records()
    value = next((v for v in values if v["generation"]["id"] == trial_id), None)
    if value is None:
        raise ValueError("Unknown or unimported frozen trial")
    return v1.trial_public(value)
