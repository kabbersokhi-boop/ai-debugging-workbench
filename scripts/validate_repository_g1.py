"""Opt-in real GitHub validation. Never imported by normal offline CI.

Use the running private local stack. No third-party code executes in this process.
"""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from workbench.repository_audit.execution import validate
from workbench.repository_audit.intake import decode_files


async def run(args):
    root = (await asyncio.to_thread(Path(args.manifest).resolve)).parent
    manifest = json.loads(await asyncio.to_thread(Path(args.manifest).read_text))
    output = await asyncio.to_thread(Path(args.output).resolve)
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:

        async def request(method, route, **kwargs):
            response = await client.request(method, "/api/repository-audits/" + route, **kwargs)
            response.raise_for_status()
            return response.json()

        runtimes = await request("GET", "runtimes")
        sources = {}
        for example in manifest["examples"]:
            if args.example and example["key"] != args.example:
                continue
            key = example["key"]
            repo_base = (example["repository"], example["base_commit"])
            if repo_base not in sources:
                sources[repo_base] = await request(
                    "POST",
                    "sources",
                    json={"repository": repo_base[0], "base_commit": repo_base[1]},
                )
            source = sources[repo_base]
            candidate = await request(
                "POST",
                "candidates",
                json={
                    "snapshot_id": source["id"],
                    "patch": (root / example["patch"]).read_text(),
                    "approved_paths": example["approved_paths"],
                    "author_label": "G1 integration example (declared)",
                    "source_reference": example["patch_provenance"],
                },
            )
            image = next(
                r for r in runtimes if r["runtime"] == example["runtime"] and r["available"]
            )
            plan = await request(
                "POST",
                "plans",
                json={
                    "snapshot_id": source["id"],
                    "candidate_hash": candidate["candidate_hash"],
                    "runtime": example["runtime"],
                    "image_id": image["image_id"],
                    "tests": example["tests"],
                    "test_description": example["test_description"],
                },
            )
            if not args.confirm_local_execution:
                (output / f"{key}-review.json").write_text(
                    json.dumps({"source": source, "candidate": candidate, "plan": plan}, indent=2)
                    + "\n"
                )
                print(key, "review prepared; execution not approved")
                continue
            audit = await request(
                "POST",
                "runs",
                json={
                    "candidate_id": candidate["id"],
                    "plan_id": plan["id"],
                    "approve_exact_plan": True,
                    "confirm_local_execution": True,
                },
            )
            async with asyncio.timeout(180):
                while audit["status"] == "running":
                    await asyncio.sleep(0.3)
                    audit = await request("GET", "runs/" + audit["id"])
            downloaded = await request("GET", "runs/" + audit["id"] + "/evidence")
            reopened = await request("GET", "runs/" + audit["id"])
            assert audit == downloaded == reopened
            evidence = audit["evidence"]
            decode_files(evidence["snapshot"])
            validate(
                evidence["result"],
                UUID(audit["id"]),
                evidence["snapshot"],
                evidence["candidate"],
                evidence["plan"],
                evidence["engine_id"],
            )
            (output / f"{key}.json").write_text(json.dumps(audit, indent=2) + "\n")
            assert audit["status"] == example["expected_status"], audit
            print(key, audit["status"], audit["id"], "download validated; saved result reopened")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="evaluation/repository-examples/g1/examples.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", default="artifacts/repository-audit/external")
    parser.add_argument("--example")
    parser.add_argument("--confirm-local-execution", action="store_true")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (
        url.scheme != "http"
        or url.hostname not in ("localhost", "127.0.0.1", "::1")
        or url.username
        or url.password
        or url.path
        or url.query
        or url.fragment
    ):
        parser.error("Use a loopback HTTP API origin")
    asyncio.run(run(args))
