"""Three additional bounded live product runs; shipping is captured by the browser demo.

Each case executes once and retains all terminal outcomes. No automatic retry campaign.
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("Pass --live to make bounded real NVIDIA requests")
    folder = Path("artifacts/milestone-04")
    folder.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8010", timeout=15) as client:

        async def wait(path, statuses):
            async with asyncio.timeout(330):
                while True:
                    response = await client.get(path)
                    response.raise_for_status()
                    row = response.json()
                    if row["status"] not in statuses:
                        return row
                    await asyncio.sleep(0.5)

        for case_id in ("cart-quantity", "decrement-skip", "clamp-zero"):
            output = folder / f"live-{case_id}.json"
            if output.exists():
                print(f"Retained {case_id}; not rerunning", flush=True)
                continue
            record = {"mode": "live_nvidia", "scenario": case_id}
            try:
                response = await client.post("/api/runs", json={"bug_id": case_id})
                response.raise_for_status()
                run_id = response.json()["id"]
                run = await wait(f"/api/runs/{run_id}", {"queued", "running"})
                record["reproduction"] = run
                if run["status"] != "reproduced":
                    continue
                response = await client.post(f"/api/runs/{run_id}/investigations", json={})
                response.raise_for_status()
                investigation = await wait(
                    f"/api/investigations/{response.json()['id']}",
                    {"queued", "indexing", "retrieving", "diagnosing"},
                )
                record["investigation"] = investigation
                if investigation["status"] != "completed":
                    continue
                response = await client.post(f"/api/investigations/{investigation['id']}/repairs")
                response.raise_for_status()
                record["repair"] = await wait(
                    f"/api/repairs/{response.json()['id']}",
                    {
                        "queued",
                        "inspecting",
                        "proposing",
                        "validating",
                        "candidate_created",
                        "verifying",
                    },
                )
            finally:
                output.write_text(json.dumps(record, indent=2) + "\n")
                print(
                    json.dumps(
                        {
                            "case": case_id,
                            "reproduction": record.get("reproduction", {}).get("status"),
                            "diagnosis": record.get("investigation", {}).get("status"),
                            "repair": record.get("repair", {}).get("status"),
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    asyncio.run(main())
