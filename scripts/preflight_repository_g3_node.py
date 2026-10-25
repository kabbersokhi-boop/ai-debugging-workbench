"""Prepare exact unchanged-base reviews, then explicitly approve each restricted preflight."""

import argparse
import asyncio
import gzip
import json
from pathlib import Path

import httpx
from workbench.db import RepositorySource
from workbench.evaluator.catalog import identity
from workbench.repository_audit.base_preflight import execute, review
from workbench.repository_audit.service import load


async def run(args):
    root = Path("evaluation/repository-examples/g3")
    cases = json.loads((root / "cases.json").read_text())["cases"][-2:]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    capsule = json.loads(Path("docker/node-compat/manifest.json").read_text())
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18050", timeout=60) as client:
        runtimes = (await client.get("/api/repository-audits/runtimes")).json()
        image = next(r["image_id"] for r in runtimes if r["runtime"] == "node22_compat" and r["available"])
        for case in cases:
            prefix = output / case["key"]
            source_path = prefix.with_suffix(".source.json.gz")
            if source_path.exists():
                source = json.loads(gzip.decompress(source_path.read_bytes()))
            else:
                response = await client.post("/api/repository-audits/sources", json={
                    "repository": case["repository"], "base_commit": case["base_commit"]})
                response.raise_for_status()
                source = await load(RepositorySource, response.json()["id"])
                source_path.write_bytes(gzip.compress(json.dumps(source).encode(), mtime=0))
            plan = review(source, image, case["ordinary"]["tests"], capsule)
            plan_id = identity(plan)
            review_path = prefix.with_suffix(".review.json")
            material = {"id": plan_id, "plan": plan}
            if review_path.exists() and json.loads(review_path.read_text()) != material:
                raise ValueError("Prepared preflight changed; use a separately versioned output")
            review_path.write_text(json.dumps(material, indent=2) + "\n")
            if plan_id not in args.approve_plan:
                print(case["key"], "exact plan prepared:", plan_id, flush=True)
                continue
            result_path = prefix.with_suffix(".result.json")
            if result_path.exists():
                print(case["key"], "retained existing result; not executed again", flush=True)
                continue
            intent = prefix.with_suffix(".attempt.json")
            with intent.open("x") as stream:
                json.dump({"approved_plan_id": plan_id, "case": case["key"]}, stream)
            result = await asyncio.to_thread(execute, source, plan, plan_id)
            result_path.write_text(json.dumps(result, indent=2) + "\n")
            print(case["key"], result["status"], result.get("container_id"), flush=True)
            if result["status"] != "tests_passed":
                raise ValueError("Unchanged-base preflight failed; formal scoring forbidden")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/repository-audit-g3c/preflights-v1")
    parser.add_argument("--approve-plan", action="append", default=[])
    asyncio.run(run(parser.parse_args()))
