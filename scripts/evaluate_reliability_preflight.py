"""One-time independent evidence for every explicit development submission; never formal metrics.

No model calls. The source, candidate and verifier are those of the retained development freeze.
A reproduction writes a separate runtime record and does not replace the original observation.
"""

import argparse
from pathlib import Path

from workbench.evaluator import reliability as v2
from workbench.evaluator.catalog import identity
from workbench.evaluator.experiment import trial_binding
from workbench.evaluator.experiment_catalog import build_candidate, exclusive_json, task
from workbench.evaluator.experiment_runner import evaluate, validate_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    frozen = v2.load_freeze(True)
    v2.assert_frozen(frozen)
    records = v2.records(
        True
    )  # Requires all four generations to terminate and validate.
    folder = (
        Path("artifacts/evaluator-m02-reliability/reproductions")
        if args.reproduce
        else v2.DEV / "independent"
    )
    folder.mkdir(parents=True, exist_ok=True)
    for record in records:
        c = record.get("candidate")
        if c is None:
            continue
        binding = trial_binding(record, frozen)
        exclusive_json(folder / (c["id"] + "-claim.json"), binding)
        spec = task(c["task_id"])
        candidate = build_candidate(spec, c)
        result = evaluate(spec, candidate)
        validate_result(
            spec,
            candidate,
            result,
            None if args.reproduce else frozen["body"]["image_id"],
        )
        wrapper = {
            "kind": "development observation; excluded from formal comparison denominators",
            "trial_binding": binding,
            "trial_binding_hash": identity(binding),
            "result_hash": identity(result),
            "result": result,
        }
        exclusive_json(folder / (c["id"] + ".json"), wrapper)
        (folder / (c["id"] + ".patch")).write_text(candidate["patch"])
        print(
            c["id"],
            result["status"],
            result["ordinary"]["outcome"],
            result["independent"]["outcome"],
        )


if __name__ == "__main__":
    main()
