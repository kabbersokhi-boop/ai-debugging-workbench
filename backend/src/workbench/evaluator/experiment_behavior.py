"""Additional M2 observations; expected values never enter the producer tools."""

import json
from typing import Any

SEEKABLE = """
import json, sys
sys.path.insert(0, '/source')
from more_itertools import seekable
result = {}
for name, values in [('mixed', [0, False, None, 2]), ('single', [7]), ('empty', [])]:
    count = [0]
    def source():
        for value in values:
            count[0] += 1
            yield value
    s = seekable(source(), maxlen=0)
    events = []
    for op in ['peek','peek','bool','bool','next','peek','next','bool',
               'next','next','bool','peek_default','next']:
        try:
            if op == 'peek': value = s.peek()
            elif op == 'peek_default': value = s.peek('end')
            elif op == 'bool': value = bool(s)
            else: value = next(s)
        except Exception as error:
            value = {'error': type(error).__name__}
        events.append({'op': op, 'value': value, 'pulled': count[0], 'cache': list(s.elements())})
    result[name] = events
for name, limit in [('default', None), ('positive', 2)]:
    s = seekable([1,2,3], maxlen=limit)
    truth, first, n1, n2 = bool(s), s.peek(), next(s), next(s)
    s.seek(0)
    replay = list(s)
    result[name] = {'truth': truth, 'peek': first, 'next': [n1,n2], 'replay': replay,
                    'cache': list(s.elements()), 'exhausted': bool(s)}
print(json.dumps(result))
"""

INDEXEDSET = """
import json, sys
sys.path.insert(0, '/source')
from boltons.setutils import IndexedSet
result = {}
bounds = [(1,4,None),(-3,None,None),(2,-1,None),(0,20,2),(-30,4,None),
          (3,3,None),(None,None,None),(2,5,-1),(-4,-1,-2),(None,None,-1)]
for removed in [[2],[1,4],[0,8],[3,7,9]]:
    s = IndexedSet(range(12))
    for value in removed: s.remove(value)
    before = list(s)
    observations = []
    for start, stop, step in bounds:
        try:
            sliced = s[slice(start,stop,step)]
            observations.append({'values': list(sliced), 'type_ok': isinstance(sliced, IndexedSet)})
        except Exception as error:
            observations.append({'error': type(error).__name__})
    result[','.join(map(str,removed))] = {'before': before, 'slices': observations,
        'after': list(s), 'length': len(s), 'scalar': [s[0],s[2],s[-1]]}
print(json.dumps(result))
"""


def probe(task_id: str) -> str:
    return {"more-seekable": SEEKABLE, "boltons-indexedset": INDEXEDSET}[task_id]


def expected(task_id: str) -> dict[str, Any]:
    if task_id == "more-seekable":
        result: dict[str, Any] = {}
        for name, values in [("mixed", [0, False, None, 2]), ("single", [7]), ("empty", [])]:
            position = pulled = 0
            events = []
            for op in [
                "peek",
                "peek",
                "bool",
                "bool",
                "next",
                "peek",
                "next",
                "bool",
                "next",
                "next",
                "bool",
                "peek_default",
                "next",
            ]:
                available = position < len(values)
                if available:
                    pulled = max(pulled, position + 1)
                value = (
                    available
                    if op == "bool"
                    else values[position]
                    if available
                    else "end"
                    if op == "peek_default"
                    else {"error": "StopIteration"}
                )
                if op == "next" and available:
                    position += 1
                events.append({"op": op, "value": value, "pulled": pulled, "cache": []})
            result[name] = events
        for name, cache in [("default", [1, 2, 3]), ("positive", [2, 3])]:
            result[name] = {
                "truth": True,
                "peek": 1,
                "next": [1, 2],
                "replay": [1, 2, 3],
                "cache": cache,
                "exhausted": False,
            }
        return result
    if task_id != "boltons-indexedset":
        raise ValueError("Unknown additional task")
    bounds = [
        (1, 4, None),
        (-3, None, None),
        (2, -1, None),
        (0, 20, 2),
        (-30, 4, None),
        (3, 3, None),
        (None, None, None),
        (2, 5, -1),
        (-4, -1, -2),
        (None, None, -1),
    ]
    result = {}
    for removed in [[2], [1, 4], [0, 8], [3, 7, 9]]:
        values = [v for v in range(12) if v not in removed]
        observations = []
        for start, stop, step in bounds:
            if step is not None and step < 0:
                start = max(len(values) + start, 0) if start is not None and start < 0 else start
                stop = max(len(values) + stop, 0) if stop is not None and stop < 0 else stop
                sliced = list(reversed(values))[slice(start, stop, -step)]
            else:
                sliced = values[slice(start, stop, step)]
            observations.append({"values": sliced, "type_ok": True})
        result[",".join(map(str, removed))] = {
            "before": values,
            "slices": observations,
            "after": values,
            "length": len(values),
            "scalar": [values[0], values[2], values[-1]],
        }
    return result


def compare(task_id: str, output: str) -> list[dict[str, Any]]:
    observed = json.loads(output)
    wanted = expected(task_id)
    if not isinstance(observed, dict) or set(observed) != set(wanted):
        raise ValueError("Missing or unexpected observations")
    return [
        {
            "name": k,
            "expected": v,
            "observed": observed[k],
            "status": "passed"
            if json.dumps(v, sort_keys=True) == json.dumps(observed[k], sort_keys=True)
            else "failed",
        }
        for k, v in wanted.items()
    ]
