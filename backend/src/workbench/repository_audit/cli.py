"""Local CLI using the same admission, checklist, approval and evidence API as the UI."""

import argparse
import json
import time
from pathlib import Path

import httpx

from workbench.evaluator.catalog import identity
from workbench.repository_audit.checklists import Checklist

BASE = "http://127.0.0.1:8010/api/repository-audits"


def request(client, method, path, payload=None):
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def approval_id(prepared):
    return identity(prepared)


def wait(client, audit, seconds=300):
    deadline = time.monotonic() + seconds
    while audit["status"] == "running":
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Observation deadline reached for {audit['id']}; no retry started. "
                "Use the evidence command to inspect the saved run."
            )
        time.sleep(0.5)
        audit = request(client, "GET", "/runs/" + audit["id"])
    return audit


def export(client, audit_id, directory):
    directory.mkdir(parents=True, exist_ok=True)
    audit = request(client, "GET", f"/runs/{audit_id}/evidence")
    (directory / f"{audit_id}.json").write_text(json.dumps(audit, indent=2) + "\n")
    report = client.get(f"/runs/{audit_id}/report")
    report.raise_for_status()
    (directory / f"{audit_id}.md").write_text(report.text)
    patch = client.get(f"/candidates/{audit['candidate_id']}/patch")
    patch.raise_for_status()
    (directory / f"{audit_id}.patch").write_text(patch.text)
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare", help="Admit a patch and prepare plans; never executes code")
    prepare.add_argument("--checklist", type=Path, required=True)
    prepare.add_argument("--patch", type=Path, required=True)
    prepare.add_argument("--commit", required=True)
    prepare.add_argument("--snapshot-id", help="Reuse an already admitted local source snapshot")
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--approve-requirements", action="store_true", required=True)
    generated = sub.add_parser(
        "generated-prepare", help="Approve a bounded property search; never executes"
    )
    generated.add_argument("--preparation", type=Path, required=True)
    generated.add_argument("--search", type=Path, required=True)
    generated.add_argument("--approve-property", action="store_true", required=True)
    generated.add_argument(
        "--replay-audit", help="Use a saved reduced input from this exact candidate"
    )
    generated.add_argument("--out", type=Path, required=True)
    for action in ("controls", "run"):
        command = sub.add_parser(action)
        command.add_argument("--preparation", type=Path, required=True)
        command.add_argument(
            "--approve-exact",
            required=True,
            help="SHA-256 printed by prepare after reviewing the exact plans",
        )
        command.add_argument("--out-dir", type=Path, required=True)
        if action == "run":
            command.add_argument("--validation", required=True)
    evidence = sub.add_parser("evidence", help="Read saved evidence without executing")
    evidence.add_argument("audit_id")
    evidence.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with httpx.Client(base_url=BASE, timeout=120, trust_env=False) as client:
            if args.action == "generated-prepare":
                original = json.loads(args.preparation.read_bytes())
                approved = original["verification"]
                ordinary = original["ordinary"]
                source_plan = approved["plan"]
                if len(approved["requirements"]) != 1:
                    raise ValueError("Generation needs exactly one reviewed requirement")
                search = json.loads(args.search.read_bytes())
                replay_plan = None
                if args.replay_audit:
                    from workbench.repository_audit.replay import prepare_replay

                    saved = request(client, "GET", "/runs/" + args.replay_audit + "/evidence")
                    replay_plan = prepare_replay(saved, original, search)
                verification = request(
                    client,
                    "POST",
                    f"/runs/{args.replay_audit}/generated-replay-plans"
                    if args.replay_audit
                    else "/generated-plans",
                    {"plan": replay_plan}
                    if args.replay_audit
                    else {
                        "snapshot_id": source_plan["snapshot_id"],
                        "candidate_id": source_plan["candidate_id"],
                        "candidate_hash": source_plan["candidate_hash"],
                        "ordinary_plan_id": ordinary["id"],
                        "image_id": ordinary["plan"]["image_id"],
                        "module": source_plan["module"],
                        "export": source_plan["export"],
                        "setup": source_plan["setup"],
                        "requirement_id": approved["requirements"][0]["id"],
                        "property_approval": "owner_approved",
                        "stateless_function": True,
                        "search": search,
                    },
                )
                prepared = {
                    "ordinary": ordinary,
                    "verification": verification,
                    "execution_approval": "not_approved",
                    "validation": "awaiting_fresh_controls",
                    **({"replay_of": args.replay_audit} if args.replay_audit else {}),
                }
                args.out.write_text(json.dumps(prepared, indent=2) + "\n")
                print(json.dumps(prepared, indent=2))
                print(
                    "Review the exact property, domain and budgets. Approval fingerprint:",
                    approval_id(prepared),
                )
                return 0
            if args.action == "prepare":
                checklist = Checklist.model_validate_json(args.checklist.read_bytes())
                if args.snapshot_id:
                    source = request(client, "GET", "/sources/" + args.snapshot_id)
                    if source["base_commit"] != args.commit:
                        raise ValueError("Admitted source does not match the selected commit")
                else:
                    source = request(
                        client,
                        "POST",
                        "/sources",
                        {
                            "repository": checklist.repository,
                            "base_commit": args.commit,
                        },
                    )
                candidate = request(
                    client,
                    "POST",
                    "/candidates",
                    {
                        "snapshot_id": source["id"],
                        "patch": args.patch.read_text(),
                        "approved_paths": checklist.approved_paths,
                    },
                )
                payload = {"candidate_id": candidate["id"], "checklist": checklist.model_dump()}
                match = request(client, "POST", "/checklists/compatibility", payload)
                if match["status"] != "compatible":
                    raise ValueError(json.dumps(match))
                runtime = next(
                    (
                        r
                        for r in request(client, "GET", "/runtimes")
                        if r["runtime"] == checklist.runtime and r["available"]
                    ),
                    None,
                )
                if not runtime:
                    raise ValueError("Build the selected local runtime before preparing plans")
                prepared = request(
                    client,
                    "POST",
                    "/checklists/prepare",
                    {
                        **payload,
                        "image_id": runtime["image_id"],
                        "approve_requirements": True,
                    },
                )
                args.out.write_text(json.dumps(prepared, indent=2) + "\n")
                print(json.dumps(prepared, indent=2))
                print("Review these exact inputs. Approval fingerprint:", approval_id(prepared))
                return 0
            if args.action == "evidence":
                audit = export(client, args.audit_id, args.out_dir)
            else:
                prepared = json.loads(args.preparation.read_bytes())
                if args.approve_exact != approval_id(prepared):
                    raise ValueError("Approval fingerprint differs; review this exact preparation")
                use = prepared.get("checklist_use")
                verification = prepared["verification"]
                payload = {
                    "candidate_id": verification["plan"]["candidate_id"],
                    "plan_id": prepared["ordinary"]["id"],
                    "verification_id": verification["id"],
                    **({"checklist_use_id": use["id"]} if use else {}),
                    **(
                        {"replay_audit_id": prepared["replay_of"]}
                        if prepared.get("replay_of")
                        else {}
                    ),
                    "approve_exact_plan": True,
                    "confirm_local_execution": True,
                    "approve_independent_plan": True,
                    "stage": "validation" if args.action == "controls" else "execution",
                }
                if args.action == "run":
                    payload["validation_run_id"] = args.validation
                audit = wait(client, request(client, "POST", "/runs", payload))
                audit = export(client, audit["id"], args.out_dir)
            print(json.dumps({"audit_id": audit["id"], "status": audit["status"]}))
            return 0 if audit["status"] in {"completed", "tests_passed", "validation_passed"} else 1
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        IndexError,
        OSError,
        RuntimeError,
        httpx.HTTPError,
    ) as error:
        print(str(error))
        if isinstance(error, httpx.HTTPStatusError):
            print(error.response.text)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
