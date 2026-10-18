"""Fixed local campaign, scoring and reproduction. Never exposes producer tools through HTTP."""

import argparse
import asyncio
import json
from pathlib import Path

from workbench.evaluator.catalog import identity
from workbench.evaluator.experiment import (
    assert_frozen,
    comparison,
    read_trial,
    trial_binding,
    validate_trial,
)
from workbench.evaluator.experiment_catalog import (
    ROOT,
    build_candidate,
    candidate,
    exclusive_json,
    freeze,
    task,
)
from workbench.evaluator.experiment_runner import evaluate
from workbench.evaluator.experiment_store import insert
from workbench.evaluator.producer import generate


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "score", "import", "summary", "reproduce"))
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frozen = freeze()
    assert_frozen(frozen)
    if args.command == "generate":
        if not args.live:
            parser.error("Model requests require --live and existing coordinator credentials")
        # Exclusive campaign claim prevents accidental restarts or overlapping campaigns.
        exclusive_json(ROOT / "campaign-claim.json", {"freeze_hash": frozen["hash"]})
        for coordinate in frozen["body"]["order"]:
            config = frozen["body"]["configurations"][coordinate["configuration_id"]]
            record = await generate(
                task(coordinate["task_id"]),
                config,
                coordinate,
                frozen,
                ROOT / "trials" / coordinate["id"],
            )
            print(coordinate["order"], coordinate["id"], record["generation_status"], flush=True)
        return
    if args.command == "reproduce":
        value = candidate(args.candidate_id)
        result = await asyncio.to_thread(evaluate, task(value["task_id"]), value)
        text = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(text)
        print(text)
        raise SystemExit(0 if result["status"] == "passed" else 1)
    records = [read_trial(c["id"]) for c in frozen["body"]["order"]]
    if any(r is None for r in records):
        raise ValueError("All scheduled generations must terminate before any independent scoring")
    for record in records:
        assert record is not None
        validate_trial(record, frozen)
        folder = ROOT / "trials" / record["generation"]["id"]
        if args.command == "score" and record.get("candidate"):
            if (folder / "evaluation.json").exists():
                # read_trial + validate_trial above already checked the existing immutable wrapper.
                continue
            value = build_candidate(task(record["candidate"]["task_id"]), record["candidate"])
            # Publish only an approved fixed candidate ID for inference-free reproduction.
            candidate_path = ROOT / "candidates" / (value["id"] + ".json")
            if candidate_path.exists():
                if json.loads(candidate_path.read_text()) != record["candidate"]:
                    raise ValueError("Conflicting published candidate")
            else:
                exclusive_json(candidate_path, record["candidate"])
            binding = trial_binding(record, frozen)
            claim_path = folder / "scoring-claim.json"
            if claim_path.exists():
                if json.loads(claim_path.read_text()) != binding:
                    raise ValueError("Conflicting scoring claim")
                result = {
                    "candidate_hash": value["candidate_hash"],
                    "status": "infrastructure_error",
                    "reason": "InterruptedScoring: no execution retried",
                }
            else:
                exclusive_json(claim_path, binding)
                try:
                    result = await asyncio.to_thread(evaluate, task(value["task_id"]), value)
                except Exception as error:
                    result = {
                        "candidate_hash": value["candidate_hash"],
                        "status": "infrastructure_error",
                        "reason": type(error).__name__,
                    }
            result["trial_binding_hash"] = identity(binding)
            scoring = {
                "trial_binding": binding,
                "trial_binding_hash": identity(binding),
                "result_hash": identity(result),
                "result": result,
            }
            record["result"], record["scoring"] = result, scoring
            exclusive_json(folder / "evaluation.json", scoring)
            validate_trial(record, frozen)
            print(value["id"], result["status"], flush=True)
        if args.command == "import":
            if record.get("candidate") and not record.get("result"):
                raise ValueError("Score final candidates before import")
            await insert(record, frozen)
    if args.command == "summary":
        result = comparison(records, frozen, require_complete=True)
        text = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(text)
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
