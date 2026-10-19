"""Real API cancellation, broker terminal recovery and missing-result reconciliation for G2."""

import asyncio
import json
import os
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_independent_verification import fixture_verification
from test_repository_audit import fixture_source, patch_for
from test_repository_audit_integration import actual_plan

from workbench.config import ROOT, settings
from workbench.db import RepositoryAudit, RepositorySource

pytestmark = pytest.mark.integration
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_g2_exact_approval_cancellation_restart_and_missing_terminal():
    source = fixture_source()
    db = create_async_engine(settings.database_url)
    factory = async_sessionmaker(db, expire_on_commit=False)
    try:
        async with factory.begin() as session:
            if await session.get(RepositorySource, source["id"]) is None:
                session.add(RepositorySource(id=source["id"], record=source))
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:

            async def post(route, body):
                response = await client.post("/api/repository-audits/" + route, json=body)
                response.raise_for_status()
                return response.json()

            async def terminal(aid):
                async with asyncio.timeout(90):
                    while True:
                        response = await client.get("/api/repository-audits/runs/" + aid)
                        response.raise_for_status()
                        saved = response.json()
                        if saved["status"] != "running":
                            return saved
                        await asyncio.sleep(0.2)

            candidate = await post(
                "candidates",
                {
                    "snapshot_id": source["id"],
                    "patch": patch_for(source),
                    "approved_paths": ["library.py"],
                },
            )
            ordinary = await post("plans", actual_plan(source, candidate))
            fixture = fixture_verification(
                source=source, candidate=candidate, ordinary=ordinary["plan"]
            )
            req = {k: v for k, v in fixture["verification"]["requirements"][0].items() if k != "id"}
            await post("requirements", req)
            verification = await post("verification-plans", fixture["verification"]["plan"])
            payload = {
                "candidate_id": candidate["id"],
                "plan_id": ordinary["id"],
                "verification_id": verification["id"],
                "approve_independent_plan": True,
                "approve_exact_plan": True,
                "confirm_local_execution": True,
            }
            assert (
                await client.post("/api/repository-audits/runs", json=payload)
            ).status_code == 409
            assert (
                await client.post(
                    "/api/repository-audits/runs",
                    json={**payload, "stage": "validation", "approve_independent_plan": False},
                )
            ).status_code == 409
            validation = await post("runs", {**payload, "stage": "validation"})
            validation = await terminal(validation["id"])
            assert validation["status"] == "validation_passed", validation
            payload["validation_run_id"] = validation["id"]
            cancelled = await post("runs", payload)
            assert (
                await client.post("/api/repository-audits/runs/" + cancelled["id"] + "/cancel")
            ).status_code == 200
            cancelled = await terminal(cancelled["id"])
            assert cancelled["status"] == "cancelled", cancelled
            completed = await post("runs", payload)
            completed = await terminal(completed["id"])
            assert completed["status"] == "completed", completed
            missing_id = uuid4()
            async with factory.begin() as session:
                row = await session.get(RepositoryAudit, UUID(completed["id"]))
                assert row
                evidence = {
                    k: v for k, v in row.evidence.items() if k not in ("result", "result_hash")
                }
                row.status, row.evidence = "running", evidence
                session.add(
                    RepositoryAudit(
                        id=missing_id,
                        candidate_id=row.candidate_id,
                        plan_id=row.plan_id,
                        status="running",
                        evidence=evidence,
                    )
                )
            process = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "restart",
                "api",
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await process.communicate()
            assert process.returncode == 0, output
            async with asyncio.timeout(90):
                while True:
                    try:
                        response = await client.get(
                            "/api/repository-audits/runs/" + completed["id"]
                        )
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.4)
            restored = response.json()
            assert restored["status"] == "completed"
            assert restored["evidence"] == completed["evidence"]
            downloaded = (
                await client.get("/api/repository-audits/runs/" + completed["id"] + "/evidence")
            ).json()
            assert downloaded == restored
            missing = (await client.get("/api/repository-audits/runs/" + str(missing_id))).json()
            assert missing["status"] == "interrupted" and "result" not in missing["evidence"]
            folder = ROOT / "artifacts/repository-audit-g2"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "recovery.json").write_text(
                json.dumps(
                    {"cancelled": cancelled, "restored": restored, "missing_terminal": missing},
                    indent=2,
                )
            )
    finally:
        await db.dispose()
