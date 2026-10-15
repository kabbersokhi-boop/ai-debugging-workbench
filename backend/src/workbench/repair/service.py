"""Repair coordinator: one shared budget, native checkpoints, explicit terminal evidence."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workbench.config import ProviderSettings, settings
from workbench.db import Investigation, Repair, Run, sessions
from workbench.rag.provider import NvidiaProvider, Provider, ProviderError
from workbench.rag.snapshot import load_snapshot, snapshot_scenario
from workbench.repair.graph import RepairGraph, RepairState
from workbench.repair.mcp_client import connect_tools

ACTIVE = frozenset(
    {"queued", "inspecting", "proposing", "validating", "candidate_created", "verifying"}
)


def view(row: Repair) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in Repair.__table__.columns}


def make_provider() -> NvidiaProvider:
    config = ProviderSettings(
        provider_max_requests=settings.repair_max_requests, model_output_token_limit=2000
    )
    provider = NvidiaProvider(config)
    provider.output_budget_remaining = settings.repair_output_budget
    return provider


class RepairManager:
    def __init__(
        self,
        factory: Callable[[], Provider] = make_provider,
        store: async_sessionmaker[AsyncSession] = sessions,
        broker_url: str | None = None,
    ):
        self.factory = factory
        self.store = store
        self.broker_url = broker_url or settings.repair_broker_url
        self.tasks: dict[UUID, asyncio.Task] = {}
        self.lock = asyncio.Lock()

    async def get(self, repair_id: UUID) -> dict[str, Any]:
        async with self.store() as session:
            row = await session.get(Repair, repair_id)
            if row is None:
                raise HTTPException(404, "Repair not found")
            return view(row)

    async def history(self, investigation_id: UUID) -> list[dict[str, Any]]:
        async with self.store() as session:
            rows = (
                await session.scalars(
                    select(Repair)
                    .where(Repair.investigation_id == investigation_id)
                    .order_by(Repair.created_at.desc())
                    .limit(10)
                )
            ).all()
            return [view(row) for row in rows]

    async def create(self, investigation_id: UUID) -> dict[str, Any]:
        async with self.lock, self.store.begin() as session:
            investigation = await session.get(Investigation, investigation_id)
            if investigation is None:
                raise HTTPException(404, "Investigation not found")
            snapshot = load_snapshot(investigation.snapshot_id)
            run = await session.get(Run, investigation.run_id)
            if (
                investigation.status != "completed"
                or not investigation.diagnosis
                or not investigation.retrieval
                or investigation.snapshot_id != snapshot.id
                or run is None
                or run.status != "reproduced"
                or not run.result
                or run.result["fixture_sha256"] != snapshot.fixture_sha256
            ):
                raise HTTPException(
                    409,
                    (
                        "Repair needs a completed diagnosis and reproduced defect from the"
                        " approved snapshot"
                    ),
                )
            prior = await session.scalar(
                select(Repair).where(
                    Repair.investigation_id == investigation_id, Repair.status.in_(ACTIVE)
                )
            )
            if prior:
                return view(prior)
            if self.tasks:
                raise HTTPException(429, "One repair is already active. Wait or cancel it.")
            repair_id = uuid4()
            state: RepairState = {
                "repair_id": str(repair_id),
                "run_id": str(run.id),
                "investigation_id": str(investigation_id),
                "snapshot_id": snapshot.id,
                "status": "queued",
                "evidence": {
                    "report": investigation.report,
                    "browser": {
                        "baseline": run.result["baseline"],
                        "observed": run.result["observed"],
                    },
                    "diagnosis": investigation.diagnosis,
                    "context": investigation.retrieval["supplied_context"],
                },
                "source_reads": [],
                "model_records": [],
                "mcp_events": [],
                "attempts": [],
                "attempt_count": 0,
                "decision_count": 0,
                "request_remaining": settings.repair_max_requests,
                "output_budget_remaining": settings.repair_output_budget,
                "deadline": (
                    datetime.now(UTC) + timedelta(seconds=settings.repair_timeout_seconds)
                ).isoformat(),
                "decision": None,
                "candidate_hash": None,
                "verification": None,
                "provider_calls": [],
                "error": None,
                "error_code": None,
                "original_verification": {},
            }
            row = Repair(
                id=repair_id,
                run_id=run.id,
                investigation_id=investigation_id,
                snapshot_id=snapshot.id,
                status="queued",
                state=state,
                events=[],
            )
            session.add(row)
            await session.flush()
        task = asyncio.create_task(self.execute(repair_id), name=f"repair-{repair_id}")
        self.tasks[repair_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(repair_id, None))
        return await self.get(repair_id)

    async def update(
        self, repair_id: UUID, changes: dict[str, Any], title: str, detail: str
    ) -> None:
        async with self.store.begin() as session:
            row = await session.scalar(
                select(Repair).where(Repair.id == repair_id).with_for_update()
            )
            if row is None or row.status not in ACTIVE:
                return
            row.state = {**row.state, **changes}
            row.status = row.state["status"]
            row.error = row.state.get("error")
            row.error_code = row.state.get("error_code")
            row.updated_at = datetime.now(UTC)
            row.events = [
                *row.events,
                {
                    "sequence": len(row.events) + 1,
                    "title": title,
                    "detail": detail,
                    "created_at": row.updated_at.isoformat(),
                },
            ]

    async def broker(self, path: str, request_timeout: float = 65) -> dict:
        async with httpx.AsyncClient(base_url=self.broker_url, timeout=request_timeout) as client:
            response = await client.post(path)
            response.raise_for_status()
            return response.json()

    async def execute(self, repair_id: UUID) -> None:
        provider: Provider | None = None
        tools = None
        try:
            row = await self.get(repair_id)
            state = row["state"]
            seconds = (
                datetime.fromisoformat(state["deadline"]) - datetime.now(UTC)
            ).total_seconds()
            async with asyncio.timeout(max(0, seconds)):
                provider = self.factory()
                await self.update(
                    repair_id,
                    {"status": "inspecting"},
                    "Checking original behavior",
                    (
                        "Running the same independent expectations against the frozen "
                        "defective source."
                    ),
                )
                original = await self.broker(f"/original/verify?snapshot_id={row['snapshot_id']}")
                case = snapshot_scenario(row["snapshot_id"])
                issue = next(c for c in original["checks"] if c["name"] == case["issue_check"])
                baseline_ok = any(c["passed"] for c in original["checks"])
                if case["id"] == "cart-quantity":
                    baseline_ok = any(
                        c["name"] == "add-one-baseline" and c["passed"] for c in original["checks"]
                    )
                if original["status"] != "failed" or issue["passed"] or not baseline_ok:
                    raise ValueError(
                        "Trusted checks did not establish the expected original defect and"
                        " passing baseline"
                    )
                state["original_verification"] = original
                async with connect_tools(repair_id, row["snapshot_id"], self.broker_url) as tools:

                    async def retain(changes, title, detail):
                        await self.update(repair_id, changes, title, detail)

                    connstr = settings.database_url.replace(
                        "postgresql+asyncpg://", "postgresql://"
                    )
                    async with await AsyncConnection[DictRow].connect(
                        connstr,
                        autocommit=True,
                        row_factory=dict_row,
                        options="-c search_path=repair_graph,public",
                    ) as connection:
                        saver = AsyncPostgresSaver(connection)
                        graph = RepairGraph(provider, tools, retain).compile(saver)
                        value = state
                        async for value in graph.astream(
                            state,
                            {"configurable": {"thread_id": str(repair_id)}, "recursion_limit": 24},
                            stream_mode="values",
                        ):
                            # Failed attempts stay active while revision remains possible.
                            progress = dict(value)
                            status = progress["status"]
                            if status in (
                                "patch_rejected",
                                "verification_failed",
                                "verified",
                                "invalid_output",
                                "error",
                            ):
                                progress["status"] = (
                                    "inspecting"
                                    if status in ("patch_rejected", "verification_failed")
                                    else "verifying"
                                )
                            progress["provider_calls"] = provider.calls
                            progress["request_remaining"] = max(
                                0, settings.repair_max_requests - len(provider.calls)
                            )
                            progress["output_budget_remaining"] = getattr(
                                provider, "output_budget_remaining", settings.repair_output_budget
                            )
                            await self.update(
                                repair_id,
                                progress,
                                status.replace("_", " ").capitalize(),
                                f"Checkpoint saved · {
                                    value[('attempt_count')]
                                }/2 candidate attempts.",
                            )
                        await self.update(
                            repair_id,
                            dict(value),
                            "Repair finished",
                            (
                                "Outcome is limited to the named trusted checks and exact "
                                "candidate hash."
                            ),
                        )
        except asyncio.CancelledError:
            await self.update(
                repair_id,
                {
                    "status": "cancelled",
                    "provider_calls": provider.calls if provider else [],
                    "mcp_events": tools.events if tools else [],
                },
                "Repair cancelled",
                "Candidate work stopped; partial evidence remains available.",
            )
            raise
        except TimeoutError:
            await self.update(
                repair_id,
                {
                    "status": "error",
                    "error": "Shared repair wall-clock budget exhausted",
                    "error_code": "timeout",
                    "provider_calls": provider.calls if provider else [],
                    "mcp_events": tools.events if tools else [],
                },
                "Repair timed out",
                "No unobserved verification result is treated as passed.",
            )
        except ProviderError as error:
            await self.update(
                repair_id,
                {
                    "status": "provider_error",
                    "error": str(error),
                    "error_code": error.code,
                    "provider_calls": provider.calls if provider else [],
                    "mcp_events": tools.events if tools else [],
                },
                "Provider work stopped",
                str(error),
            )
        except Exception:
            await self.update(
                repair_id,
                {
                    "status": "error",
                    "error": "MCP, candidate execution or checkpoint operation failed",
                    "error_code": "execution_error",
                    "provider_calls": provider.calls if provider else [],
                    "mcp_events": tools.events if tools else [],
                },
                "Execution error",
                "Inspect retained tool and model evidence. No verification pass is inferred.",
            )
        finally:
            if provider:
                await provider.close()
            try:
                await self.broker(f"/repairs/{repair_id}/cleanup", request_timeout=20)
            except httpx.HTTPError:
                pass  # Broker TTL/restart reconciliation also removes stale environments.

    async def cancel(self, repair_id: UUID) -> dict[str, Any]:
        saved = await self.get(repair_id)
        if saved["status"] in ACTIVE:
            task = self.tasks.get(repair_id)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await self.update(
                repair_id,
                {"status": "cancelled"},
                "Repair cancelled",
                "No candidate was published.",
            )
        return await self.get(repair_id)

    async def recover(self) -> None:
        async with self.store() as session:
            rows = (await session.scalars(select(Repair).where(Repair.status.in_(ACTIVE)))).all()
            ids = [row.id for row in rows]
        for repair_id in ids:
            saved = await self.get(repair_id)
            reconciliation = []
            for attempt in saved["state"].get("attempts", []):
                if attempt.get("candidate"):
                    try:
                        async with httpx.AsyncClient(timeout=5) as client:
                            response = await client.get(
                                f"{self.broker_url}/candidates/{repair_id}/{
                                    attempt[('number')]
                                }/reconcile"
                            )
                            reconciliation.append(
                                response.json()
                                if response.status_code == 200
                                else {"status": "unavailable"}
                            )
                    except httpx.HTTPError:
                        reconciliation.append({"status": "unavailable"})
            try:
                await self.broker(f"/repairs/{repair_id}/cleanup", request_timeout=20)
            except httpx.HTTPError:
                pass
            await self.update(
                repair_id,
                {
                    "status": "interrupted",
                    "reconciliation": reconciliation,
                    ("error"): (
                        "Restart interrupted this repair; automatic resumption is not established"
                    ),
                    "error_code": "interrupted",
                },
                "Restart reconciliation",
                (
                    "Persisted candidates checked and cleanup requested. No success "
                    "inferred; start a new repair."
                ),
            )

    async def close(self) -> None:
        for task in list(self.tasks.values()):
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
