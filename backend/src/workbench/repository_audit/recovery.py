"""Bounded coordinator recovery diagnostics; never log submitted material."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

LOGGER = logging.getLogger("uvicorn.error.repository_recovery")
POLL_SECONDS = 12.0
CANCEL_SECONDS = 10.0
PERSIST_SECONDS = 5.0
POLL_INTERVAL = 0.3


def cancellation_checkpoint() -> None:
    # A native cancellation can be consumed by a concurrent AnyIO scope cancellation.
    # Do not let a swallowed shutdown signal turn into more polling or a DB verdict.
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError


@dataclass
class RecoveryTrace:
    audit_id: str
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    started: float = field(default_factory=time.monotonic)
    polls: int = 0
    missing: int = 0
    transport_errors: int = 0
    last_error: str | None = None

    def event(self, stage: str, **fields) -> None:
        task = asyncio.current_task()
        LOGGER.info(
            json.dumps(
                {
                    "event": "repository_audit_recovery",
                    "audit_id": self.audit_id,
                    "attempt_id": self.attempt_id,
                    "stage": stage,
                    "started_monotonic": self.started,
                    "elapsed_seconds": round(time.monotonic() - self.started, 6),
                    "poll_attempts": self.polls,
                    "http_404_count": self.missing,
                    "transport_errors": self.transport_errors,
                    "last_error_class": self.last_error,
                    "cancellation_count": task.cancelling() if task else 0,
                    "candidate_execution_requested": False,
                    **fields,
                },
                sort_keys=True,
            )
        )
