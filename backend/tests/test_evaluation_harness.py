"""Exercise scoring/retention plumbing on a development case with an OFFLINE provider."""

import importlib.util
import json

import pytest
from test_repair_integration import OfflineRepair

from workbench.config import ROOT
from workbench.rag.snapshot import scenario
from workbench.repair.verifier import VERIFIER_VERSION

pytestmark = pytest.mark.integration


async def test_offline_one_shot_harness_executes_sealed_final_checks(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "repair_evaluation_test", ROOT / "scripts/evaluate_repairs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    broker_url, image = module.docker_identity()
    config = tmp_path / "offline-experiment.json"
    config.write_text(
        json.dumps(
            {
                "per_condition": {"one-shot-whole": {"decisions": 1, "patches": 1, "requests": 2}},
                "candidate_runtime_image_id": image,
                "verifier_version": VERIFIER_VERSION,
            }
        )
    )
    monkeypatch.setattr(module, "CONFIG", config)
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "results")

    class OfflineOneShot(OfflineRepair):
        def __init__(self, config, transport):
            super().__init__()
            self.number = 1  # Complete context: deterministic fixture proposes immediately.
            self.config = config
            self.requests = 0

    monkeypatch.setattr(module, "NvidiaProvider", OfflineOneShot)
    result = await module.execute_case(scenario("cart-quantity"), "one-shot-whole", {}, broker_url)
    assert result["resolved"], result
    assert result["model_calls"] == 1
    assert result["issue_passed"] and result["regression_passed"] and result["final_passed"]
    saved = tmp_path / "results/cart-quantity--one-shot-whole"
    final = json.loads((saved / "final-checks.json").read_text())
    assert len(final["checks"]) == 12
    assert final["visibility"] == "evaluation_only_after_final_candidate"
    assert "final-input" not in json.dumps(result["state"]["model_records"])
    assert result == await module.execute_case(
        scenario("cart-quantity"), "one-shot-whole", {}, broker_url
    )
