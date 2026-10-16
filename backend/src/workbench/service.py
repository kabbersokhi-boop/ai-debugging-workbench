import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workbench.config import settings
from workbench.contracts import TERMINAL, Event, ReproductionResult, RunnerEvent, RunStatus, RunView
from workbench.db import Run, RunEvent, sessions
from workbench.rag.snapshot import scenario

logger = logging.getLogger(__name__)


async def append_event(
    session: AsyncSession,
    run_id: UUID,
    kind: str,
    title: str,
    detail: str,
    data: dict | None = None,
) -> None:
    sequence = await session.scalar(
        select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_id)
    )
    session.add(
        RunEvent(
            run_id=run_id,
            sequence=int(sequence or 0) + 1,
            kind=kind,
            title=title,
            detail=detail,
            data=data or {},
        )
    )


async def get_run(run_id: UUID) -> RunView:
    async with sessions() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "Investigation not found")
        events = (
            await session.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)
            )
        ).all()
        return RunView(
            id=run.id,
            bug_id=run.bug_id,
            status=RunStatus(run.status),
            created_at=run.created_at,
            updated_at=run.updated_at,
            error=run.error,
            result=ReproductionResult.model_validate(run.result) if run.result else None,
            events=[Event.model_validate(event) for event in events],
        )


class RunManager:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.tasks: dict[UUID, asyncio.Task[None]] = {}
        self.lock = asyncio.Lock()

    async def recover(self) -> None:
        async with sessions.begin() as session:
            runs = (
                await session.scalars(select(Run).where(Run.status.in_(["queued", "running"])))
            ).all()
            for run in runs:
                run.status = RunStatus.INTERRUPTED
                run.updated_at = datetime.now(UTC)
                reason = "The API restarted before this reproduction completed. Start a new run."
                run.error = reason
                await append_event(session, run.id, "error", "Run interrupted", reason)

    async def create(self, bug_id: str, key: str | None) -> RunView:
        case = scenario(bug_id)
        if case["split"] != "development":
            raise HTTPException(422, "Only supported demonstration scenarios are available")
        async with self.lock, sessions.begin() as session:
            if key:
                previous = await session.scalar(select(Run).where(Run.idempotency_key == key))
                if previous:
                    return await get_run(previous.id)
            if len(self.tasks) >= settings.max_active_runs:
                raise HTTPException(429, "All browser slots are in use. Try again shortly.")
            run_id = uuid4()
            session.add(Run(id=run_id, bug_id=bug_id, status=RunStatus.QUEUED, idempotency_key=key))
            await session.flush()
            await append_event(
                session,
                run_id,
                "step",
                "Investigation queued",
                "Accepted the built-in cart reproduction. "
                "No AI inference is used in this milestone.",
            )
        task = asyncio.create_task(self.execute(run_id), name=f"reproduce-{run_id}")
        self.tasks[run_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(run_id, None))
        return await get_run(run_id)

    async def finish(self, run_id: UUID, status: RunStatus, error: str) -> None:
        async with sessions.begin() as session:
            run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if run and run.status not in TERMINAL:
                run.status = status
                run.updated_at = datetime.now(UTC)
                run.error = error
                await append_event(session, run_id, "error", status.value.capitalize(), error)

    async def execute(self, run_id: UUID) -> None:
        try:
            async with sessions.begin() as session:
                await session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(status=RunStatus.RUNNING, updated_at=datetime.now(UTC))
                )
            async with sessions() as session:
                run = await session.get(Run, run_id)
                if run is None:
                    raise ValueError("Reproduction identity missing")
                scenario_id = run.bug_id
            got_result = False
            async with asyncio.timeout(settings.run_timeout_seconds):
                async with self.client.stream(
                    "POST", f"/reproduce/{run_id}?scenario_id={scenario_id}"
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        message = RunnerEvent.model_validate_json(line)
                        async with sessions.begin() as session:
                            run = await session.scalar(
                                select(Run).where(Run.id == run_id).with_for_update()
                            )
                            if run is None or run.status in TERMINAL:
                                return
                            await append_event(
                                session,
                                run_id,
                                message.kind,
                                message.title,
                                message.detail,
                                message.data,
                            )
                            run.updated_at = datetime.now(UTC)
                            if message.kind == "result":
                                result = ReproductionResult.model_validate(message.data["result"])
                                run.result = result.model_dump()
                                run.status = result.status
                                got_result = True
                            elif message.kind == "error":
                                run.status = RunStatus.ERROR
                                run.error = message.detail
            if not got_result:
                await self.finish(run_id, RunStatus.ERROR, "Runner ended without a valid result.")
        except asyncio.CancelledError:
            await self.finish(
                run_id,
                RunStatus.CANCELLED,
                "Reproduction was cancelled; no complete outcome is available.",
            )
            raise
        except TimeoutError:
            await self.finish(
                run_id,
                RunStatus.ERROR,
                "Reproduction exceeded its time budget. No outcome was declared.",
            )
        except Exception:
            logger.exception("Run failed: %s", run_id)
            await self.finish(
                run_id,
                RunStatus.ERROR,
                "The browser runner was unavailable or returned invalid evidence. "
                "Retry after checking service health.",
            )

    async def cancel(self, run_id: UUID) -> RunView:
        view = await get_run(run_id)
        if view.status in TERMINAL:
            return view
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.finish(run_id, RunStatus.CANCELLED, "Cancelled before execution completed.")
        return await get_run(run_id)

    async def close(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
