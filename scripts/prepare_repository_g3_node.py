"""Prepare new exact application plans before freezing the Node addendum. Never executes."""

import asyncio
import json
from pathlib import Path

import httpx


async def run():
    root = Path("evaluation/repository-examples/g3-node-compatibility")
    cases = json.loads((root / "cases.json").read_text())["cases"]
    (root / "plans").mkdir(exist_ok=True)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18050", timeout=60) as client:
        async def request(route, value):
            response = await client.post("/api/repository-audits/" + route, json=value)
            response.raise_for_status()
            return response.json()

        runtimes = (await client.get("/api/repository-audits/runtimes")).json()
        image = next(r["image_id"] for r in runtimes if r["runtime"] == "node22_compat" and r["available"])
        for case in cases:
            for kind in ("reference", "alternative"):
                path = root / "plans" / (case["key"] + "-" + kind + ".json")
                if path.exists():
                    print(path, "already prepared; unchanged", flush=True)
                    continue
                source = await request("sources", {"repository": case["repository"], "base_commit": case["base_commit"]})
                candidate = await request("candidates", {
                    "snapshot_id": source["id"], "approved_paths": [case["module"]],
                    "patch": (root / case["alternative_patch" if kind == "alternative" else "patch"]).read_text(),
                    "author_label": "Codex-authored alternative control" if kind == "alternative" else "G3 original upstream developer submission",
                    "source_reference": "Authored alternate, not a genuine candidate" if kind == "alternative" else case["provenance"]["reference"],
                })
                ordinary = await request("plans", {"snapshot_id": source["id"], "candidate_hash": candidate["candidate_hash"], "runtime": "node22_compat", "image_id": image, **case["ordinary"]})
                requirement = await request("requirements", {"snapshot_id": source["id"], **case["requirement"]})
                verification = await request("verification-plans", {
                    "snapshot_id": source["id"], "candidate_id": candidate["id"],
                    "candidate_hash": candidate["candidate_hash"], "ordinary_plan_id": ordinary["id"],
                    "runtime": "node22_compat", "image_id": image, "module": case["module"], "export": case["export"],
                    "assertions": [{k: v for k, v in a.items() if k != "rationale"} | {"requirement_id": requirement["id"]} for a in case["assertions"]],
                })
                material = {"source": source, "candidate": candidate, "ordinary": ordinary,
                            "verification": verification, "requirement": requirement,
                            "execution_payload": {"candidate_id": candidate["id"], "plan_id": ordinary["id"], "verification_id": verification["id"]},
                            "approval": "Prepared only; no execution approval inherited from G3"}
                with path.open("x") as stream:
                    json.dump(material, stream, indent=2)
                    stream.write("\n")
                print(path, ordinary["id"], verification["id"], flush=True)


if __name__ == "__main__":
    asyncio.run(run())
