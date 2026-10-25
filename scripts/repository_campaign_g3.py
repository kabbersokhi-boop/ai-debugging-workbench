"""Drive a frozen, bounded G3 campaign through the existing local application API."""

import argparse
import asyncio
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from workbench.evaluator.catalog import identity
from workbench.repository_audit.campaign import bind_audit, load_campaign, summarize


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


async def run(args):
    root, output = Path(args.manifest_dir), Path(args.output)
    declaration, cases, campaign_hash = load_campaign(root)
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {
        "campaign_sha256": campaign_hash, "entries": [], "started_at": datetime.now(UTC).isoformat()
    }
    if index["campaign_sha256"] != campaign_hash:
        raise ValueError("Output belongs to a different campaign")
    entries = index["entries"]
    audits = {}
    for entry in entries:
        audits[entry["run_id"]] = json.loads(gzip.decompress((output / entry["file"]).read_bytes()))
    # Revalidate saved material before resuming; never silently rerun a completed slot.
    summarize(root, declaration, cases, campaign_hash, entries, audits)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        async def request(method, route, **kwargs):
            response = await client.request(method, "/api/repository-audits/" + route, **kwargs)
            if response.is_error:
                raise RuntimeError(f"{method} {route}: {response.status_code} {response.text[:1000]}")
            return response.json()

        async def prepare(case, alternative=False):
            if declaration.get("prepared_plans"):
                kind = "alternative" if alternative else "reference"
                material = json.loads((root / declaration["prepared_plans"][case["key"]][kind]).read_text())
                return {**material["execution_payload"], "approve_independent_plan": True,
                        "approve_exact_plan": True, "confirm_local_execution": True}
            # Intake metadata includes fetched_at. Re-fetching creates a different snapshot;
            # reuse the exact admitted source/plan whose controls were validated.
            control_role = "alternative_control" if alternative else "control"
            journal = output / f"{case['key']}-{control_role}-1-attempt.json"
            if journal.exists():
                prepared = json.loads(journal.read_text())["payload"]
                return {k: v for k, v in prepared.items() if k != "stage"}
            source = await request("POST", "sources", json={
                "repository": case["repository"], "base_commit": case["base_commit"]})
            patch = case["alternative_patch"] if alternative else case["patch"]
            candidate = await request("POST", "candidates", json={
                "snapshot_id": source["id"], "patch": (root / patch).read_text(),
                "approved_paths": [case["module"]],
                "author_label": "G3 authored specification alternative" if alternative else "G3 upstream developer submission",
                "source_reference": "G3 alternate declared-domain implementation, not a genuine candidate" if alternative else case["provenance"]["reference"]})
            ordinary = await request("POST", "plans", json={
                "snapshot_id": source["id"], "candidate_hash": candidate["candidate_hash"],
                "runtime": case["runtime"], "image_id": declaration["runtime_images"][case["runtime"]],
                **case["ordinary"]})
            requirement = await request("POST", "requirements", json={
                "snapshot_id": source["id"], **case["requirement"]})
            verification = await request("POST", "verification-plans", json={
                "snapshot_id": source["id"], "candidate_id": candidate["id"],
                "candidate_hash": candidate["candidate_hash"], "ordinary_plan_id": ordinary["id"],
                "runtime": case["runtime"], "image_id": declaration["runtime_images"][case["runtime"]],
                "module": case["module"], "export": case["export"],
                "assertions": [{k: v for k, v in a.items() if k != "rationale"} | {"requirement_id": requirement["id"]} for a in case["assertions"]]})
            return {"candidate_id": candidate["id"], "plan_id": ordinary["id"],
                    "verification_id": verification["id"], "approve_independent_plan": True,
                    "approve_exact_plan": True, "confirm_local_execution": True}

        async def execute(case, role, trial, payload):
            previous = next((e for e in entries if (e["case"], e["role"], e["trial"]) == (case["key"], role, trial)), None)
            if previous:
                audit = await request("GET", "runs/" + previous["run_id"])
                if audit != audits[previous["run_id"]]:
                    raise ValueError("Reopened audit changed")
                return audit
            name = f"{case['key']}-{role}-{trial}"
            journal = output / (name + "-attempt.json")
            if journal.exists():
                attempt = json.loads(journal.read_text())
                if not attempt.get("run_id"):
                    raise ValueError("Uncertain POST; inspect authoritative history before recovery: " + name)
                audit = await request("GET", "runs/" + attempt["run_id"])
            else:
                if not args.confirm_local_execution:
                    raise ValueError("Execution needs the explicit local-owner workflow flag")
                attempt = {"campaign_sha256": campaign_hash, "case": case["key"], "role": role,
                           "trial": trial, "payload": payload, "started_at": datetime.now(UTC).isoformat()}
                write_json(journal, attempt)  # Record intent before the POST; no automatic retries.
                audit = await request("POST", "runs", json=payload)
                attempt["run_id"] = audit["id"]
                write_json(journal, attempt)
            # An observation timeout leaves the run ID available for resuming this same handle.
            async with asyncio.timeout(600):
                while audit["status"] == "running":
                    await asyncio.sleep(0.5)
                    audit = await request("GET", "runs/" + audit["id"])
            download = await request("GET", "runs/" + audit["id"] + "/evidence")
            reopened = await request("GET", "runs/" + audit["id"])
            if audit != download or audit != reopened:
                raise ValueError("Download/reopen differs")
            # Preserve even failed/invalid evidence before interpreting it.
            filename = name + ".json.gz"
            (output / filename).write_bytes(gzip.compress(json.dumps(audit, ensure_ascii=False).encode(), mtime=0))
            bind_audit(root, case, audit, role, declaration)
            entry = {"case": case["key"], "role": role, "trial": trial,
                     "run_id": audit["id"], "audit_hash": identity(audit), "file": filename}
            entries.append(entry)
            audits[audit["id"]] = audit
            write_json(index_path, index)
            result = audit["evidence"]["result"]
            print(name, audit["id"], audit["status"],
                  (result.get("ordinary") or {}).get("status"), result["independent"]["status"], flush=True)
            return audit

        if args.phase != "summary":
            runtimes = await request("GET", "runtimes")
            for runtime, image in declaration["runtime_images"].items():
                if not any(r["runtime"] == runtime and r["image_id"] == image and r["available"] for r in runtimes):
                    raise ValueError("Frozen runtime unavailable")
            blocked_path = output / "blocked.json"
            blocked = json.loads(blocked_path.read_text()) if blocked_path.exists() else {}
            for case in cases:
                if case["key"] in blocked:
                    print(case["key"], "not executed:", blocked[case["key"]], flush=True)
                    continue
                payload = await prepare(case)
                if args.phase == "preflight":
                    validation = await execute(case, "control", 1, {**payload, "stage": "validation"})
                    if validation["status"] != "validation_passed":
                        raise ValueError("Synthetic controls did not pass; scoring forbidden")
                    await execute(case, "reference", 1, {**payload, "validation_run_id": validation["id"]})
                    alternate = await prepare(case, True)
                    validation = await execute(case, "alternative_control", 1, {**alternate, "stage": "validation"})
                    if validation["status"] != "validation_passed":
                        raise ValueError("Alternative controls did not pass")
                    await execute(case, "alternative", 1, {**alternate, "validation_run_id": validation["id"]})
                else:
                    validation_entry = next(e for e in entries if e["case"] == case["key"] and e["role"] == "control")
                    if not {"reference", "alternative", "control", "alternative_control"}.issubset(
                        {e["role"] for e in entries if e["case"] == case["key"]}
                    ):
                        raise ValueError("Complete declared case specification validation before formal scoring")
                    for trial in (1, 2):
                        await execute(case, "candidate", trial, {**payload, "validation_run_id": validation_entry["run_id"]})
    assessments = json.loads(Path(args.adjudications).read_text()) if args.adjudications else {}
    summary = summarize(root, declaration, cases, campaign_hash, entries, audits, assessments)
    write_json(output / "summary.json", summary)
    print(json.dumps(summary["counts"], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", default="evaluation/repository-examples/g3")
    parser.add_argument("--output", default="artifacts/repository-audit-g3/campaign-v1")
    parser.add_argument("--base-url", default="http://127.0.0.1:18030")
    parser.add_argument("--phase", choices=("preflight", "score", "summary"), required=True)
    parser.add_argument("--adjudications")
    parser.add_argument("--confirm-local-execution", action="store_true")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1") or any(
        (url.username, url.password, url.path, url.query, url.fragment)
    ):
        parser.error("Use a loopback HTTP API origin")
    asyncio.run(run(args))
