"""Explicitly selected historical examples, verified before local use or recorded export."""

import json
from functools import lru_cache

from workbench.evaluator import catalog, experiment, reliability
from workbench.evaluator.experiment_catalog import build_candidate, candidate, freeze, task
from workbench.evaluator.experiment_runner import validate_result
from workbench.patch_audit.admission import admit

FAIL = "m02-v2-development-boltons-addlist-nemotron3-r02"
PASS = "m02-v1-boltons-addlist-nemotron35-r02"
BUCKET = "m02-v1-more-bucket-nemotron3-r01"


@lru_cache(maxsize=1)
def examples():
    old = freeze()
    experiment.assert_frozen(old)
    dev = reliability.load_freeze(True)
    reliability.assert_frozen(dev)
    journeys = reliability.records(True)
    rows = {}
    for key, title in (
        (FAIL, "Missed standalone copy · genuine development patch"),
        (PASS, "Both implementations repaired · genuine retained patch"),
        (BUCKET, "Bucket validator · genuine retained patch"),
    ):
        is_dev = key == FAIL
        f = dev if is_dev else old
        r = (
            next(r for r in journeys if r["generation"]["id"] == key)
            if is_dev
            else experiment.read_trial(key)
        )
        assert r is not None
        (reliability.validate if is_dev else experiment.validate_trial)(r, f)
        assert r["candidate"] is not None and r["generation"] is not None
        c = build_candidate(task(r["candidate"]["task_id"]), r["candidate"])
        if is_dev:
            path = reliability.DEV / "independent" / (key + ".json")
            wrapper = json.loads(path.read_text())
            if (
                wrapper["trial_binding"] != experiment.trial_binding(r, f)
                or wrapper["trial_binding_hash"] != catalog.identity(wrapper["trial_binding"])
                or wrapper["result_hash"] != catalog.identity(wrapper["result"])
            ):
                raise ValueError("Development observation binding mismatch")
            result = wrapper["result"]
            source_validation = {k: v for k, v in wrapper.items() if k != "result"}
            if (
                max(e["at"] for row in journeys for e in row["events"])
                >= result["ordinary"]["started_at"]
            ):
                raise ValueError("Development scoring did not follow all generation")
        else:
            result = r["result"]
            assert r["scoring"] is not None
            source_validation = {k: v for k, v in r["scoring"].items() if k != "result"}
        assert result is not None
        validate_result(task(c["task_id"]), c, result, f["body"]["image_id"])
        request = next(e["payload"] for e in r["events"] if e["kind"] == "request")
        settings = (
            {k: v for k, v in request["payload"].items() if k != "messages"}
            if is_dev
            else request["parameters"]
        )
        responses = [e["payload"] for e in r["events"] if e["kind"] == "response"]
        provenance = {
            "category": "retained_model",
            "producer_label": title,
            "producer": c["producer"],
            "source_reference": str(
                (reliability.DEV if is_dev else reliability.V1_ROOT).relative_to(
                    catalog.CATALOG.parent
                )
            )
            + "/trials/"
            + key,
            "trial_id": key,
            "procedure": "m02-v2-development" if is_dev else "m02-v1",
            "freeze_hash": f["hash"],
            "events_head": r["generation"]["events_head"],
            "original_candidate_hash": c["candidate_hash"],
            "returned_models": sorted({x.get("model", "unavailable") for x in responses}),
            "request_settings": settings,
            "limitations": (
                "Development on a known historical task; not a held-out accuracy estimate. "
                "One incomplete repair, not five discoveries. Different procedures are not a "
                "vendor comparison."
            )
            if is_dev
            else (
                "Retained controlled generation under m02-v1; not comparable to the later "
                "development procedure as a vendor ranking."
            ),
        }
        if is_dev:
            provenance["metadata_note"] = (
                "Historical top-level temperature=0 differs from actual request "
                "temperature=1. Actual serialized request parameters above are "
                "authoritative; the freeze is unchanged."
            )
        value = admit(c["task_id"], c["patch"], provenance)
        if value["candidate_hash"] != c["candidate_hash"]:
            raise ValueError("Curated patch differs from retained generation")
        rows[key] = {
            "key": key,
            "label": title,
            "candidate": value,
            "recorded_result": result,
            "source_validation": source_validation,
        }
    for task_id in ("more-bucket", "boltons-addlist", "more-seekable", "boltons-indexedset"):
        for suffix in ("negative", "reference", "alternate"):
            key = task_id + "-" + suffix
            try:
                c = catalog.candidate(key) if task_id in catalog.TASK_IDS else candidate(key)
            except ValueError:
                continue
            rows[key] = {
                "key": key,
                "label": c["label"],
                "candidate": admit(
                    task_id,
                    c["patch"],
                    {
                        "category": "control",
                        "producer_label": c["label"],
                        "producer": c["producer"],
                        "source_reference": key,
                        "limitations": (
                            "Deliberately authored evaluator control; excluded from genuine model "
                            "evidence."
                        ),
                    },
                ),
            }
    return rows
