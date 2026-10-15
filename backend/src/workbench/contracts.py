from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    ERROR = "error"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


TERMINAL = frozenset(RunStatus) - {RunStatus.QUEUED, RunStatus.RUNNING}


class Bug(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    report: str
    steps: list[str]
    expected: str
    repository: str


BUG = Bug(
    id="cart-quantity",
    title="Cart total ignores item quantity",
    summary="Changing quantity updates the line item, but checkout keeps the original total.",
    severity="High",
    report=(
        "I added the $64 canvas daypack to my cart and changed the quantity from 1 to 3. "
        "The line item shows $192, but the order subtotal still shows $64 and shipping is "
        "still $8. I expected a $192 subtotal and free shipping on orders above $100."
    ),
    steps=[
        "Open the Fieldwork Supply storefront with a fresh cart.",
        "Add one Canvas daypack ($64).",
        "Confirm the baseline: $64 subtotal + $8 shipping = $72.",
        "Increase quantity from 1 to 3.",
        "Compare the line amount and checkout totals against the pricing contract.",
    ],
    expected="3 × $64 = $192 subtotal; shipping $0; order total $192.",
    repository="fixtures/retail",
)


class CreateRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bug_id: Literal["cart-quantity", "shipping-threshold", "decrement-skip", "clamp-zero"]


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    kind: str
    title: str
    detail: str
    created_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    name: str
    label: str
    media_type: str


class Check(BaseModel):
    name: str
    expected_cents: int
    observed_cents: int
    passed: bool


class Observation(BaseModel):
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    subtotal_cents: int
    shipping_cents: int
    total_cents: int


class ReproductionResult(BaseModel):
    status: Literal["reproduced", "not_reproduced"]
    checks: list[Check]
    baseline: Observation
    observed: Observation
    artifacts: list[Artifact]
    fixture_sha256: str
    browser_version: str
    duration_ms: int
    source_snapshot: str | None = None
    behavioral_checks: list[dict[str, Any]] | None = None
    runtime_identity: dict[str, str] | None = None


class RunnerEvent(BaseModel):
    kind: Literal["step", "screenshot", "result", "error"]
    title: str
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


class RunView(BaseModel):
    id: UUID
    bug_id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    error: str | None
    result: ReproductionResult | None
    events: list[Event]


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    bug_id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
