"""Opt-in bounded G2 trial through the local G1 API. No inference; no host project imports."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from workbench.evaluator.catalog import digest
from workbench.repository_audit.intake import decode_files
from workbench.repository_audit.service import validate_saved


async def run(args):
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        async def request(method, route, **kwargs):
            response = await client.request(method, "/api/repository-audits/" + route, **kwargs)
            response.raise_for_status()
            return response.json()

        async def execute(payload, name):
            audit = await request("POST", "runs", json=payload)
            async with asyncio.timeout(360):
                while audit["status"] == "running":
                    await asyncio.sleep(0.3)
                    audit = await request("GET", "runs/" + audit["id"])
            assert audit == await request("GET", "runs/" + audit["id"] + "/evidence")
            assert audit == await request("GET", "runs/" + audit["id"])
            validate_saved(audit["evidence"], audit["id"])
            (output / (name + "-" + audit["id"] + ".json")).write_text(json.dumps(audit, indent=2) + "\n")
            return audit

        runtimes = await request("GET", "runtimes")
        sources = {}
        for example in manifest["examples"]:
            key = example["key"]
            repo_base = (example["repository"], example["base_commit"])
            if repo_base not in sources:
                sources[repo_base] = await request("POST", "sources", json={
                    "repository": repo_base[0], "base_commit": repo_base[1]})
            source = sources[repo_base]
            candidate = await request("POST", "candidates", json={
                "snapshot_id": source["id"], "patch": (root / example["patch"]).read_text(),
                "approved_paths": [example["module"]], "author_label": "G2 declared " + key,
                "source_reference": example["patch_provenance"]})
            image = next(r for r in runtimes if r["runtime"] == example["runtime"] and r["available"])
            ordinary = await request("POST", "plans", json={"snapshot_id": source["id"],
                "candidate_hash": candidate["candidate_hash"], "runtime": example["runtime"],
                "image_id": image["image_id"], "tests": example["tests"],
                "test_description": "Full unchanged upstream test file, predeclared G2 trial"})
            requirement = await request("POST", "requirements", json={
                "snapshot_id": source["id"], **example["requirement"]})
            verification = await request("POST", "verification-plans", json={
                "snapshot_id": source["id"], "candidate_id": candidate["id"],
                "candidate_hash": candidate["candidate_hash"], "ordinary_plan_id": ordinary["id"],
                "runtime": example["runtime"], "image_id": image["image_id"],
                "module": example["module"], "export": example["export"],
                "assertions": [{**a, "requirement_id": requirement["id"]} for a in example["assertions"]]})
            payload = {"candidate_id": candidate["id"], "plan_id": ordinary["id"],
                "verification_id": verification["id"], "approve_independent_plan": True,
                "approve_exact_plan": True, "confirm_local_execution": True}
            review = {"source": source, "candidate": candidate, "ordinary": ordinary,
                      "verification": verification, "manifest_sha256": digest(manifest_path.read_bytes())}
            (output / (key + "-review.json")).write_text(json.dumps(review, indent=2) + "\n")
            if not args.confirm_local_execution:
                print(key, "review prepared; execution not approved", flush=True)
                continue
            validation = await execute({**payload, "stage": "validation"}, key + "-validation")
            assert validation["status"] == "validation_passed", validation
            audit = await execute({**payload, "validation_run_id": validation["id"]}, key)
            result = audit["evidence"]["result"]
            assert result["ordinary"]["status"] == example["expected_ordinary"], audit
            assert result["independent"]["status"] == example["expected_independent"], audit
            files = decode_files(audit["evidence"]["snapshot"])
            upstream_doc = "README.rst" if example["runtime"] == "python312" else "README.md"
            assert digest(files[upstream_doc]) == example["source_doc_sha256"]
            print(key, audit["id"], result["ordinary"]["status"], result["independent"]["status"],
                  "download/reopen validated", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="evaluation/repository-examples/g2/examples.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", default="artifacts/repository-audit-g2/external")
    parser.add_argument("--confirm-local-execution", action="store_true")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1")
        or url.username or url.password or url.path or url.query or url.fragment):
        parser.error("Use a loopback HTTP API origin")
    asyncio.run(run(args))
