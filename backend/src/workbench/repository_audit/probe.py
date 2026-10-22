"""Fixed JSON observation adapter. Executed only inside an approved disposable container."""

import contextlib
import importlib.util
import json
import sys
from typing import Any


def main():
    with open("/verifier/inputs.json") as stream:
        inputs = json.load(stream)
    sys.path[:0] = ["/work/deps", "/source"]
    observations = []
    for call in inputs["calls"]:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                spec = importlib.util.spec_from_file_location(
                    "_independent_target", inputs["module"]
                )
                if spec is None or spec.loader is None:
                    raise ValueError("Unsupported Python import")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                function: Any = module
                for name in inputs["export"].split("."):
                    function = getattr(function, name)
                value = function(*call["args"], **call["kwargs"])
                # Reject non-JSON values instead of stringifying them into apparent observations.
                value = json.loads(json.dumps(value, allow_nan=False))
            observations.append({"id": call["id"], "kind": "value", "value": value})
        except Exception as error:
            observations.append(
                {"id": call["id"], "kind": "execution_error", "error": type(error).__name__}
            )
    print(json.dumps({"version": "observations-v1", "observations": observations}, allow_nan=False))


if __name__ == "__main__":
    main()
