from pathlib import Path

import pytest
from pydantic import ValidationError

from workbench.contracts import TERMINAL, CreateRun, Observation, RunStatus
from workbench.runner import evaluate, fixture_digest


def baseline() -> Observation:
    return Observation(
        quantity=1,
        unit_price_cents=6400,
        line_total_cents=6400,
        subtotal_cents=6400,
        shipping_cents=800,
        total_cents=7200,
    )


def test_defect_has_three_failed_assertions_and_passing_line_amount() -> None:
    observed = baseline().model_copy(update={"quantity": 3, "line_total_cents": 19200})
    checks = evaluate(baseline(), observed)
    assert [c.name for c in checks if not c.passed] == ["Subtotal", "Shipping", "Order total"]
    assert checks[0].passed


def test_correct_behavior_is_not_misclassified_as_a_defect() -> None:
    observed = baseline().model_copy(
        update={
            "quantity": 3,
            "line_total_cents": 19200,
            "subtotal_cents": 19200,
            "shipping_cents": 0,
            "total_cents": 19200,
        }
    )
    assert all(check.passed for check in evaluate(baseline(), observed))


def test_baseline_failure_prevents_attributing_reported_defect() -> None:
    invalid = baseline().model_copy(update={"total_cents": 1})
    with pytest.raises(ValueError, match="Baseline contract failed"):
        evaluate(invalid, baseline())


def test_failed_browser_action_is_not_a_reproduced_defect() -> None:
    with pytest.raises(ValueError, match="did not set quantity"):
        evaluate(baseline(), baseline())


@pytest.mark.parametrize(
    "payload",
    [
        {"bug_id": "unknown"},
        {"bug_id": "cart-quantity", "command": "whoami"},
        {"bug_id": "cart-quantity", "url": "http://169.254.169.254/"},
        {"bug_id": "cart-quantity", "repository": "/etc"},
    ],
)
def test_requests_cannot_expand_execution_authority(payload: dict) -> None:
    with pytest.raises(ValidationError):
        CreateRun.model_validate(payload)


def test_terminal_states_are_explicit_and_never_queued_or_running() -> None:
    assert RunStatus.ERROR in TERMINAL and RunStatus.INTERRUPTED in TERMINAL
    assert RunStatus.RUNNING not in TERMINAL and RunStatus.QUEUED not in TERMINAL


def test_source_digest_changes_with_filename_or_content(tmp_path: Path) -> None:
    source = tmp_path / "cart.js"
    source.write_text("before")
    first = fixture_digest(tmp_path)
    assert first == fixture_digest(tmp_path)
    source.write_text("after")
    second = fixture_digest(tmp_path)
    assert first != second
    source.rename(tmp_path / "renamed.js")
    assert fixture_digest(tmp_path) != second
