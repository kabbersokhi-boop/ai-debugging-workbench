import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workbench.config import ProviderSettings, settings
from workbench.db import Investigation, Run, sessions
from workbench.rag.diagnosis import diagnose, model_input
from workbench.rag.provider import NvidiaProvider, Provider, ProviderError
from workbench.rag.retrieval import RepositoryRetriever
from workbench.rag.snapshot import load_snapshot, scenario

ACTIVE = frozenset({"queued", "indexing", "retrieving", "diagnosing"})


def view(row: Investigation) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in Investigation.__table__.columns}


class InvestigationManager:
    def __init__(
        self,
        factory: Callable[[], Provider] | None = None,
        store: async_sessionmaker[AsyncSession] = sessions,
    ):
        self.factory = factory or (lambda: NvidiaProvider(ProviderSettings()))
        self.store = store
        self.tasks: dict[UUID, asyncio.Task[None]] = {}
        self.lock = asyncio.Lock()

    async def get(self, investigation_id: UUID) -> dict[str, Any]:
        async with self.store() as session:
            row = await session.get(Investigation, investigation_id)
            if row is None:
                raise HTTPException(404, "Investigation not found")
            return view(row)

    async def history(self, run_id: UUID) -> list[dict[str, Any]]:
        async with self.store() as session:
            rows = (
                await session.scalars(
                    select(Investigation)
                    .where(Investigation.run_id == run_id)
                    .order_by(Investigation.created_at.desc())
                    .limit(10)
                )
            ).all()
            return [view(row) for row in rows]

    async def create(self, run_id: UUID, report: str | None) -> dict[str, Any]:
        async with self.lock, self.store.begin() as session:
            run = await session.get(Run, run_id)
            if run is None:
                raise HTTPException(404, "Reproduction not found")
            case = scenario(run.bug_id)
            snapshot = load_snapshot(case["snapshot_id"])
            if not run.result or run.status not in ("reproduced", "not_reproduced"):
                raise HTTPException(409, "Complete browser reproduction before starting diagnosis.")
            if run.result["fixture_sha256"] != snapshot.fixture_sha256:
                raise HTTPException(
                    409,
                    "This reproduction predates the approved source snapshot. Reproduce "
                    "again to investigate the matching source.",
                )
            prior = await session.scalar(
                select(Investigation).where(
                    Investigation.run_id == run_id, Investigation.status.in_(ACTIVE)
                )
            )
            if prior:
                return view(prior)
            if len(self.tasks) >= 2:
                raise HTTPException(
                    429, "Two investigations are already active. Please wait or cancel one."
                )
            investigation_id = uuid4()
            row = Investigation(
                id=investigation_id,
                run_id=run_id,
                status="queued",
                report=report or case["report"],
                snapshot_id=snapshot.id,
                events=[],
                provider_calls=[],
            )
            session.add(row)
            await session.flush()
        task = asyncio.create_task(
            self.execute(investigation_id), name=f"diagnose-{investigation_id}"
        )
        self.tasks[investigation_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(investigation_id, None))
        return await self.get(investigation_id)

    async def update(
        self, investigation_id: UUID, status: str, title: str, detail: str, **values: Any
    ) -> None:
        async with self.store.begin() as session:
            row = await session.scalar(
                select(Investigation).where(Investigation.id == investigation_id).with_for_update()
            )
            if row is None or row.status not in ACTIVE:
                return
            row.status = status
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
            for name, value in values.items():
                setattr(row, name, value)

    async def execute(self, investigation_id: UUID) -> None:
        provider: Provider | None = None
        try:
            async with asyncio.timeout(settings.diagnosis_timeout_seconds):
                provider = self.factory()
                saved = await self.get(investigation_id)
                async with self.store() as session:
                    run = await session.get(Run, saved["run_id"])
                    if run is None or run.result is None:
                        raise ValueError("Reproduction evidence is missing")
                    evidence = {
                        "reproduction_status": run.status,
                        "baseline": run.result["baseline"],
                        "observed": run.result["observed"],
                        "checks": run.result["checks"],
                        "fixture_sha256": run.result["fixture_sha256"],
                    }
                snapshot = load_snapshot(saved["snapshot_id"])
                if (
                    saved["snapshot_id"] != snapshot.id
                    or evidence["fixture_sha256"] != snapshot.fixture_sha256
                ):
                    raise ValueError("Reproduction and snapshot identities differ")
                await self.update(
                    investigation_id,
                    "indexing",
                    "Source snapshot matched",
                    f"Loading four approved source files from commit "
                    f"{snapshot.source_commit[:12]}.",
                )
                retriever = RepositoryRetriever(provider, self.store)
                index_id = await retriever.index(snapshot)
                await self.update(
                    investigation_id,
                    "retrieving",
                    "Repository index ready",
                    "Querying PostgreSQL full-text and pgvector retrieval, then NVIDIA reranking.",
                    provider_calls=provider.calls,
                )
                query = (
                    saved["report"]
                    + "\nBrowser observations: "
                    + json.dumps(
                        {"status": run.status, "observed": evidence["observed"]}, sort_keys=True
                    )
                )
                trace = await retriever.retrieve(
                    snapshot, index_id, query, budget=settings.context_token_budget
                )
                inputs = model_input(saved["report"], evidence, trace.supplied_context, snapshot.id)
                await self.update(
                    investigation_id,
                    "diagnosing",
                    "Context supplied to NVIDIA",
                    f"{len(trace.supplied_context)} complete chunks selected from "
                    f"{len(trace.candidates)} candidates. Citation ranges will be "
                    f"checked.",
                    retrieval=trace.model_dump(),
                    model_input=inputs,
                    provider_calls=provider.calls,
                )

                async def retain(raw: str) -> None:
                    await self.update(
                        investigation_id,
                        "diagnosing",
                        "Model response retained",
                        "Bounded, sanitized output saved before schema and citation validation.",
                        raw_response=raw,
                    )

                output, raw = await diagnose(
                    provider,
                    inputs,
                    trace.supplied_context,
                    snapshot.id,
                    snapshot.source_commit,
                    retain,
                )
                status = (
                    "completed" if output["outcome"] == "diagnosis" else "insufficient_evidence"
                )
                await self.update(
                    investigation_id,
                    status,
                    "Diagnosis proposed" if status == "completed" else "Insufficient evidence",
                    "Structured output and citation boundaries checked. No patch or "
                    "repair verification was performed.",
                    diagnosis=output,
                    raw_response=raw,
                    provider_calls=provider.calls,
                )
        except asyncio.CancelledError:
            await self.update(
                investigation_id,
                "cancelled",
                "Investigation cancelled",
                "Provider work was stopped; partial retrieval evidence is retained.",
                provider_calls=provider.calls if provider else [],
            )
            raise
        except ProviderError as error:
            status = (
                "invalid_output"
                if error.code
                in ("invalid_model_output", "invalid_citation", "invalid_provider_output")
                else "provider_error"
            )
            await self.update(
                investigation_id,
                status,
                "Diagnosis unavailable",
                str(error),
                error=str(error),
                error_code=error.code,
                raw_response=error.raw_response,
                provider_calls=provider.calls if provider else [],
            )
        except TimeoutError:
            await self.update(
                investigation_id,
                "error",
                "Investigation timed out",
                "The overall investigation budget was reached.",
                error="Investigation timed out",
                error_code="timeout",
                provider_calls=provider.calls if provider else [],
            )
        except Exception:
            await self.update(
                investigation_id,
                "error",
                "Investigation failed",
                "Repository indexing, retrieval, or evidence validation failed. No "
                "diagnosis was accepted.",
                error="Indexing or retrieval failed",
                error_code="execution_error",
                provider_calls=provider.calls if provider else [],
            )
        finally:
            if provider:
                await provider.close()

    async def cancel(self, investigation_id: UUID) -> dict[str, Any]:
        saved = await self.get(investigation_id)
        if saved["status"] not in ACTIVE:
            return saved
        task = self.tasks.get(investigation_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.update(
            investigation_id,
            "cancelled",
            "Investigation cancelled",
            "Cancelled before the diagnosis completed.",
        )
        return await self.get(investigation_id)

    async def recover(self) -> None:
        async with self.store.begin() as session:
            rows = (
                await session.scalars(select(Investigation).where(Investigation.status.in_(ACTIVE)))
            ).all()
            for row in rows:
                row.status = "interrupted"
                row.updated_at = datetime.now(UTC)
                row.error = (
                    "The API restarted before diagnosis completed. Start a new investigation."
                )
                row.error_code = "interrupted"
                row.events = [
                    *row.events,
                    {
                        "sequence": len(row.events) + 1,
                        "title": "Investigation interrupted",
                        "detail": row.error,
                        "created_at": row.updated_at.isoformat(),
                    },
                ]

    async def close(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
