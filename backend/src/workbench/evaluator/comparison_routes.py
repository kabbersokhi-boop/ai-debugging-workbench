"""Read-only comparison of the fixed, retained local experiment. No inference endpoints."""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from workbench.evaluator import catalog, experiment_store
from workbench.evaluator.experiment import assert_frozen
from workbench.evaluator.experiment_catalog import ROOT, candidate, freeze, task
from workbench.evaluator.experiment_runner import validate_result

router = APIRouter(prefix="/comparisons/m02-v1")


def controls():
    frozen = freeze()
    values = []
    for relative, expected in frozen["body"]["control_evidence"].items():
        path = ROOT / relative  # Paths come exclusively from the immutable local freeze.
        if catalog.digest(path.read_bytes()) != expected:
            raise ValueError("Frozen control evidence integrity failure")
        candidate_id = path.stem
        # M1 catalog remains unchanged; route explicitly across the two fixed catalogs.
        try:
            value = catalog.candidate(candidate_id)
        except ValueError:
            value = candidate(candidate_id)
        result = json.loads(path.read_text())
        validate_result(task(value["task_id"]), value, result, frozen["body"]["image_id"])
        values.append(
            {
                "id": candidate_id,
                "task_id": value["task_id"],
                "kind": "control",
                "ordinary": result["ordinary"]["outcome"],
                "independent": result["independent"]["outcome"],
                "candidate": catalog.public_candidate(value),
                "result": result,
            }
        )
    return values


@router.get("")
async def summary():
    try:
        frozen = freeze()
        assert_frozen(frozen)
        result = await experiment_store.summary()
        result["procedure"] = frozen
        result["tasks"] = [
            {k: v for k, v in task(t).items() if k != "files"} for t in frozen["body"]["tasks"]
        ]
        result["controls"] = [
            {k: v for k, v in c.items() if k not in ("candidate", "result")} for c in controls()
        ]
        return result
    except ValueError as error:
        raise HTTPException(409, "Comparison evidence failed validation: " + str(error)) from None


@router.get("/trials/{trial_id}")
async def trial(trial_id: str):
    if trial_id not in {c["id"] for c in freeze()["body"]["order"]}:
        raise HTTPException(404, "Unknown frozen trial")
    try:
        return await experiment_store.detail(trial_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.get("/trials/{trial_id}/evidence")
async def evidence(trial_id: str):
    return JSONResponse(
        await trial(trial_id),
        headers={"Content-Disposition": f'attachment; filename="{trial_id}.json"'},
    )


@router.get("/controls/{candidate_id}")
async def control(candidate_id: str):
    try:
        value = next((v for v in controls() if v["id"] == candidate_id), None)
        if value is None:
            raise HTTPException(404, "Unknown frozen control")
        return {**value, "task": {k: v for k, v in task(value["task_id"]).items() if k != "files"}}
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
