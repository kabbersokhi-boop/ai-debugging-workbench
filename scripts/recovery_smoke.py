"""Crash only this project's API, then prove recovery and retained evidence.

Run after scripts/e2e against the default local Compose stack. Do not use against
a shared or hosted environment. No volumes or application records are deleted.
"""

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

import docker


def compose(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout or ""


def main() -> None:
    started = datetime.now(UTC).isoformat()
    # Resolve before starting the run: Compose startup can outlast a fast reproduction.
    api_id = compose("ps", "-q", "api", capture=True).strip()
    if not api_id or "\n" in api_id:
        raise RuntimeError(
            "Recovery smoke requires exactly one API in this Compose project"
        )
    evidence = Path(os.environ.get("RECOVERY_EVIDENCE_DIR", "artifacts/acceptance"))
    reference = json.loads((evidence / "verified-run.json").read_text())
    with httpx.Client(
        base_url=os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010"), timeout=8
    ) as client:
        previous = client.get(f"/api/runs/{reference['id']}").json()
        run = client.post("/api/runs", json={"bug_id": "cart-quantity"}).json()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            current = client.get(f"/api/runs/{run['id']}").json()
            if any(e["title"] == "Fresh browser ready" for e in current["events"]):
                assert current["status"] == "running", current
                break
            time.sleep(0.03)
        else:
            raise RuntimeError("Browser never reached the interruption checkpoint")
        docker_client = docker.from_env()
        try:
            docker_client.containers.get(api_id).kill(signal="SIGKILL")
        finally:
            docker_client.close()
        compose("up", "-d", "--no-deps", "api")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if client.get("/api/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        else:
            raise RuntimeError("API did not recover")
        recovered = client.get(f"/api/runs/{run['id']}").json()
        assert recovered["status"] == "interrupted", recovered
        assert recovered["result"] is None
        assert client.get(f"/api/runs/{reference['id']}").json() == previous
        fresh = client.post("/api/runs", json={"bug_id": "cart-quantity"}).json()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            fresh = client.get(f"/api/runs/{fresh['id']}").json()
            if fresh["status"] not in ("queued", "running"):
                break
            time.sleep(0.2)
        assert fresh["status"] == "reproduced", fresh
        logs = compose("logs", "--since", started, "runner", capture=True)
        assert "Task exception was never retrieved" not in logs, logs
        assert "Traceback" not in logs, logs
        result = {
            "checkpoint_before_crash": current["status"],
            "recovered_run": recovered,
            "completed_history_unchanged": True,
            "fresh_run_after_recovery": fresh["id"],
            "fresh_run_status": fresh["status"],
            "runner_cleanup_errors": False,
        }
        (evidence / "recovery-check.json").write_text(json.dumps(result, indent=2))
        print(
            json.dumps(
                {key: value for key, value in result.items() if key != "recovered_run"}
            )
        )


if __name__ == "__main__":
    main()
