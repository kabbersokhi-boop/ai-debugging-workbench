"""Actual saved broker evidence + PostgreSQL coordinator restart reconciliation."""

import asyncio
import json
import os
from uuid import UUID

import httpx
import pytest

from workbench.config import ROOT
from workbench.db import Evaluation, sessions

pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_evaluator_recovery_reconciles_terminal_broker_evidence():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        response = await client.post(
            "/api/evaluator/runs", json={"candidate_id": "more-bucket-reference"}
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        async with asyncio.timeout(75):
            while True:
                before = (await client.get(f"/api/evaluator/runs/{run_id}")).json()
                if before["status"] != "running":
                    break
                await asyncio.sleep(0.2)
        assert before["status"] == "passed"
        # Simulate the coordinator dying after broker publication but before DB terminal commit.
        async with sessions.begin() as session:
            row = await session.get(Evaluation, UUID(run_id))
            assert row is not None
            row.status = "running"
            row.evidence = {k: v for k, v in row.evidence.items() if k != "result"}
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
        assert process.returncode == 0, output.decode()
        async with asyncio.timeout(45):
            while True:
                try:
                    response = await client.get(f"/api/evaluator/runs/{run_id}")
                    if response.status_code == 200:
                        after = response.json()
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.3)
        assert after["status"] == before["status"]
        assert after["evidence"] == before["evidence"]
        folder = ROOT / "artifacts/evaluator"
        await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            (folder / "recovery.json").write_text,
            json.dumps(
                {
                    "evaluation_id": run_id,
                    "status": after["status"],
                    "exact_evidence_restored": after["evidence"] == before["evidence"],
                    "candidate_hash": after["candidate_hash"],
                },
                indent=2,
            )
            + "\n",
        )
