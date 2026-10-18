"""Re-audit one saved candidate through the local API; never inference or arbitrary commands."""

import argparse
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id")
    parser.add_argument("--confirm-local-execution", action="store_true", required=True)
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8010/api/patch-audits", timeout=10) as client:
        response = client.get("/candidates/" + args.candidate_id)
        response.raise_for_status()
        c = response.json()
        response = client.post(
            "/runs",
            json={k: c[k] for k in ("candidate_hash", "record_hash")}
            | {"candidate_id": c["id"], "confirm_local_execution": True},
        )
        response.raise_for_status()
        audit_id = response.json()["id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            response = client.get("/runs/" + audit_id)
            response.raise_for_status()
            value = response.json()
            if value["status"] != "running":
                print(value["status"], "http://127.0.0.1:8010/?audit=" + audit_id)
                return
            time.sleep(0.5)
        raise SystemExit(
            "Observation deadline reached; inspect saved audit " + audit_id + ". No retry started."
        )


if __name__ == "__main__":
    main()
