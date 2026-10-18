"""One-time pre-generation freeze. Refuses replacement; no model calls."""

import json, random
from datetime import datetime, UTC
from pathlib import Path
import docker
from workbench.evaluator import catalog
from workbench.evaluator.experiment_catalog import ROOT, TASK_IDS, task, exclusive_json
from workbench.evaluator.experiment_runner import verifier_id, validate_result
from workbench.evaluator.experiment_catalog import candidate
from workbench.evaluator.producer import BUDGET, HARNESS, PROMPT, context


def main():
    folder = Path("backend/src/workbench/evaluator")
    client = docker.from_env()
    image = client.images.get("ai-agent-evaluator:python312-v1").id
    client.close()
    configurations = {}
    for name, model, label, smoke in [
        (
            "nemotron3",
            "nvidia/nemotron-3-super-120b-a12b",
            "Nemotron 3 Super",
            "nemotron3-availability.json",
        ),
        (
            "nemotron35",
            "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "Nemotron 3.5 Super",
            "nemotron35-recheck-availability.json",
        ),
    ]:
        configurations[name] = {
            "id": name,
            "model": model,
            "label": label + " / JSON source tools v2",
            "provider": "NVIDIA hosted API",
            "product": "model/harness configuration; no named coding-agent product",
            "temperature": 0,
            "harness": HARNESS,
            "harness_hash": catalog.digest((folder / "producer.py").read_bytes()),
            "prompt_hash": catalog.digest(PROMPT),
            "tools": [
                "read approved file (120 lines, 12000 chars)",
                "literal search approved files (20 hits)",
                "exact unique production edits",
                "fixed ordinary tests in fresh restricted container",
                "submit",
            ],
            "source_access": "Identical full pinned source and existing ordinary tests via a virtual allowlisted namespace. Same relevant initial excerpts. No host working directory, shell, network, repository history, reference or independent material.",
            "ordinary_access": "Fixed per-task command; same approved Python 3.12.14 / pytest 8.3.5 image; up to four runs and four edit revisions.",
            "budget": BUDGET,
            "credentials": "Existing authorized NVIDIA key; coordinator only.",
            "availability_response_model": json.loads(
                (ROOT / "smoke" / smoke).read_text()
            )["response"]["model"],
            "unavailable_metadata": [
                "Immutable model-weight revision",
                "Training exposure",
                "Provider hardware/load",
                "Monetary cost/price",
                "Provider RNG seed",
            ],
            "automatic_retries": 0,
        }
    rng = random.Random(20261016)
    order = []
    tasks = list(TASK_IDS)
    rng.shuffle(tasks)
    for repeat in range(1, 4):
        for t in tasks:
            configs = list(configurations)
            rng.shuffle(configs)
            for config in configs:
                order.append(
                    {
                        "id": f"m02-v1-{t}-{config}-r{repeat:02}",
                        "task_id": t,
                        "configuration_id": config,
                        "trial": repeat,
                        "order": len(order) + 1,
                    }
                )
    controls = {}
    containers = set()
    for t in TASK_IDS:
        for kind in ["baseline", "negative", "reference", "alternate"]:
            p = ROOT / "validation-final-v2" / (t + "-" + kind + ".json")
            r = json.loads(p.read_text())
            c = (catalog.candidate if t in catalog.TASK_IDS else candidate)(
                t + "-" + kind
            )
            validate_result(task(t), c, r, image)
            assert c["kind"] == "control"
            for phase in ["ordinary", "independent"]:
                container = r[phase]["container_id"]
                assert container not in containers
                containers.add(container)
            assert r["status"] == (
                "passed" if kind in ["reference", "alternate"] else "failed"
            )
            assert r["ordinary"]["outcome"] == "passed"
            assert (
                r["binding"]["verifier_hash"] == verifier_id(t)
                and r["binding"]["image_id"] == image
            )
            controls[str(p.relative_to(ROOT))] = catalog.digest(p.read_bytes())
    body = {
        "id": "m02-v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "accepted_m1_head": "1d49caec6accbb7d640d4e3a90a5978983a42076",
        "harness": HARNESS,
        "prompt_hash": catalog.digest(PROMPT),
        "budget": BUDGET,
        "image_id": image,
        "implementation_files": {
            n: catalog.digest((folder / n).read_bytes())
            for n in [
                "producer.py",
                "experiment_catalog.py",
                "experiment_behavior.py",
                "experiment_runner.py",
                "experiment.py",
                "experiment_cli.py",
                "experiment_store.py",
            ]
        },
        "tasks": {
            t: {
                "spec_hash": task(t)["spec_hash"],
                "verifier_hash": verifier_id(t),
                "context_hash": catalog.identity(context(task(t))),
            }
            for t in TASK_IDS
        },
        "configurations": configurations,
        "order": order,
        "order_seed": 20261016,
        "execution_order": "Sequential, pre-randomized paired configurations by task and repeat. Scoring starts only after all generation trials terminate.",
        "trials_per_task_configuration": 3,
        "controlled_trials": 24,
        "global_ceiling": {
            "requests": 24 * BUDGET["requests"],
            "conservative_token_reservations": 24 * BUDGET["token_upper_bound"],
            "wall_seconds": 24 * BUDGET["wall_seconds"],
        },
        "control_evidence": controls,
        "interruption_policy": "Exclusive trial IDs are never restarted. Completed generations may be read and validated; an interrupted generation keeps its raw prefix and is reported as incomplete, never silently rerun. A campaign cannot produce a final comparative claim without every scheduled coordinate. Completed scores are reused after validation; a scoring claim without a terminal result is classified as interrupted infrastructure, never rerun.",
        "generation_rule": "One exclusive trial claim; no automatic provider retries, reruns, budget replenishment or discarded attempts. Explicit final submission only; incomplete working trees retained in events but never auto-promoted. Test failure in a response requires another turn to inspect feedback before submission.",
        "scoring_rule": "Every submitted final candidate scored once in fresh ordinary and independent environments using identical per-task procedures. No independent feedback during any generation. Authored controls excluded. Frozen M1 calibration adapters remain unchanged.",
        "outcome_rules": {
            "no_usable_candidate": "No final submission; invalid outputs or exhausted budgets retained.",
            "ordinary_failed": "Completed final evaluation with ordinary exit 1, regardless of independent outcome.",
            "additional_independent_failure": "Ordinary passed; completed independent checks failed or candidate observations malformed.",
            "both_passed": "Both completed and passed.",
            "infrastructure_or_provider_failure": "Provider or execution infrastructure failure/timeout; never interpreted as demonstrated code defect.",
        },
        "incremental_detection": "Numerator = genuine ordinary-passing candidates rejected independently; denominator = genuine ordinary-passing candidates with completed independent evaluation. Also show attempted and completed trial denominators separately.",
        "accounting": "Reserve UTF-8 message bytes + max output tokens before every request, including failures. Usage is provider-reported; missing usage and price unknown. Generation wall includes ordinary tools; ordinary-tool time separately itemized, evaluation time separate. No CPU/memory or latency vendor ranking.",
        "limitations": [
            "Small descriptive case study: four public historical tasks, two related model families, three trials per cell; no population/vendor ranking.",
            "Training contamination and immutable weight revisions unknown. M1 is historical single-turn evidence and excluded from this controlled matrix.",
            "Structured JSON tool loop, no arbitrary shell or external retrieval; source/test access identical across configurations.",
            "In-process Python observations are not a complete anti-tampering boundary against malicious candidates. Docker shares the host kernel; local approved execution only.",
            "Ordinary tests are relevant pre-existing upstream subsets. Independent coverage is finite; passing is not proof of general correctness.",
            "Sequential local measurements include provider load and container overhead. Monetary cost is unknown; request and returned token accounting retained.",
            "Zero additional discoveries or ties are valid outcomes and do not justify broad release or execution hosting.",
        ],
    }
    exclusive_json(ROOT / "freeze.json", {"body": body, "hash": catalog.identity(body)})
    print(catalog.identity(body))


if __name__ == "__main__":
    main()
