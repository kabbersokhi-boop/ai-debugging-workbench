"""Reproduce from committed task/candidate identities; no inference or arbitrary input."""

import argparse
import json
import threading
from pathlib import Path

from workbench.evaluator.catalog import candidate, task
from workbench.evaluator.runner import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = candidate(args.candidate_id)
    result = evaluate(task(value["task_id"]), value, threading.Event())
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output)
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
