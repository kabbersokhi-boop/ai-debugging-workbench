"""One-time byte-for-byte upstream snapshots and authored validation controls (no inference)."""

import json
import subprocess
from pathlib import Path
from workbench.evaluator.catalog import identity, digest
from workbench.evaluator.experiment_catalog import ROOT, build_candidate, exclusive_json

TASKS = [
    {
        "id": "more-seekable",
        "project": "more-itertools",
        "repo": "/tmp/evaluator-more-itertools",
        "upstream": "https://github.com/more-itertools/more-itertools",
        "base_commit": "ca711220a6657a22655f6fa497524d006a735c5f",
        "reference_commit": "6b1907de293a655fb77881bf81948f95fd15bd7c",
        "issue": "https://github.com/more-itertools/more-itertools/issues/1268",
        "license": "MIT",
        "title": "Preserve iterator state during zero-cache observations",
        "problem": "seekable(iterable, maxlen=0) loses source items when peek() or bool() observes it. Observation followed by iteration must preserve the unconsumed sequence, including false-valued items.",
        "expected": "Repeated peek and truth testing must not advance the logical iterator. next() must return the peeked item. maxlen=0 must keep elements() empty. Empty and exhausted sources retain StopIteration/default/false behavior. Existing positive/default-cache seeking behavior must remain intact.",
        "allowed_paths": ["more_itertools/more.py"],
        "producer_symbols": ["seekable"],
        "files": [
            "more_itertools/__init__.py",
            "more_itertools/more.py",
            "more_itertools/recipes.py",
            "tests/test_more.py",
            "LICENSE",
        ],
        "ordinary": [
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_more.py::SeekableTest",
        ],
    },
    {
        "id": "boltons-indexedset",
        "project": "Boltons",
        "repo": "/tmp/boltons-history.gRDTMj",
        "upstream": "https://github.com/mahmoud/boltons",
        "base_commit": "979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe",
        "reference_commit": "609cabe932a1ea1423b24568644945abb1b8bb84",
        "issue": "https://github.com/mahmoud/boltons/pull/423",
        "license": "BSD-3-Clause",
        "title": "Slice IndexedSet correctly after removals",
        "problem": "Removing values leaves internal dead slots. IndexedSet slicing then mixes physical storage offsets with visible item positions and returns incorrect contents. Slicing must depend on the visible ordered contents rather than mutation history.",
        "expected": "Positive-step slices must match slicing the visible list, including negative bounds and out-of-range bounds. Preserve the established Boltons negative-step convention: normalize negative bounds against visible length, reverse the stream, then apply forward bounds and absolute step (not Python list negative-step semantics). Preserve IndexedSet return type, scalar indexing, item order, length, and nonmutation by slicing.",
        "allowed_paths": ["boltons/setutils.py"],
        "producer_symbols": [
            "IndexedSet.iter_slice",
            "IndexedSet.__getitem__",
            "IndexedSet.remove",
            "IndexedSet._get_real_index",
        ],
        "files": [
            "boltons/__init__.py",
            "boltons/setutils.py",
            "tests/test_setutils.py",
            "LICENSE",
        ],
        "ordinary": [
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_setutils.py",
        ],
    },
]


def upstream(t, revision, path):
    return subprocess.check_output(
        ["git", "-C", t["repo"], "show", revision + ":" + path]
    ).decode()


def main():
    for config in TASKS:
        t = dict(config)
        files = {p: upstream(t, t["base_commit"], p) for p in t.pop("files")}
        t.pop("repo")
        t.update(
            schema_version=1,
            environment="python312-v1",
            verifier="m02-behavior-v1",
            timeout_seconds=25,
            ordinary_scope="Existing applicable upstream tests, byte-for-byte at the defective base. Not the entire suite. No later regression tests.",
            source_files={p: digest(v) for p, v in files.items()},
        )
        folder = ROOT / "tasks" / t["id"]
        exclusive_json(folder / "manifest.json", t)
        for p, v in files.items():
            path = folder / "source" / p
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(v)
        spec = {**t, "files": files, "spec_hash": identity(t)}
        path = t["allowed_paths"][0]
        original = files[path]
        reference = upstream(config, t["reference_commit"], path)
        if t["id"] == "more-seekable":
            start = original.index("class seekable:")
            end = original.index("\n\nclass run_length:", start)
            old = original[start:end]
            ref = reference[
                reference.index("class seekable:") : reference.index(
                    "\n\nclass run_length:"
                )
            ]
            alt = old.replace(
                "self._source = iter(iterable)",
                "self._source = peekable(iterable) if maxlen == 0 else iter(iterable)",
            ).replace(
                "    def peek(self, default=_marker):\n",
                "    def peek(self, default=_marker):\n        if isinstance(self._cache, deque) and self._cache.maxlen == 0:\n            return self._source.peek(default)\n",
            )
            negative = old.replace(
                "    def __bool__(self):\n",
                "    def __bool__(self):\n        if isinstance(self._cache, deque) and self._cache.maxlen == 0:\n            try:\n                value = next(self._source)\n            except StopIteration:\n                return False\n            self._source = chain((value,), self._source)\n            return True\n",
            )
        else:
            start = original.index("    def iter_slice(")
            end = original.index("\n    # list operations", start)
            old = original[start:end]
            ref = reference[
                reference.index("    def iter_slice(") : reference.index(
                    "\n    # list operations", reference.index("    def iter_slice(")
                )
            ]
            alt = """    def iter_slice(self, start, stop, step=None):
        values = list(self)
        if start is not None and start < 0:
            start = max(len(values) + start, 0)
        if stop is not None and stop < 0:
            stop = max(len(values) + stop, 0)
        if step is not None and step < 0:
            values.reverse()
            step = -step
        return iter(values[slice(start, stop, step)])
"""
            negative = old.replace(
                "        if start is not None:\n            start = self._get_real_index(start)\n",
                "",
            ).replace(
                "        if stop is not None:\n            stop = self._get_real_index(stop)\n",
                "",
            )
        for name, replacement in [
            ("baseline", old),
            ("reference", ref),
            ("negative", negative),
            ("alternate", alt),
        ]:
            record = {
                "id": t["id"] + "-" + name,
                "task_id": t["id"],
                "spec_hash": spec["spec_hash"],
                "label": name + " authored control",
                "kind": "control",
                "producer": "authored control (upstream reference)"
                if name == "reference"
                else "authored control",
                "provenance": "Validation control; excluded from producer outcomes. Reference uses exact upstream production hunk; alternatives/negative are deliberately authored.",
                "edits": []
                if name == "baseline"
                else [{"path": path, "old": old, "new": replacement}],
            }
            c = build_candidate(spec, record)
            record["candidate_hash"] = c["candidate_hash"]
            exclusive_json(ROOT / "candidates" / (c["id"] + ".json"), record)


if __name__ == "__main__":
    main()
