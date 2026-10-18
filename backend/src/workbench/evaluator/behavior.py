"""Trusted comparison rules stay in the coordinator; probes contain no expected answers."""

import json
from typing import Any

# Each probe observes library API behavior. It runs in a separate disposable container.
BUCKET = """
import json, sys
sys.path.insert(0, '/source')
from more_itertools import bucket
class Validator:
    def __bool__(self): return False
    def __call__(self, key): return key % 2 == 0
class Empty(set):
    def __call__(self, key): return key in self
source = iter([1, 2, 3, 4])
b = bucket(source, key=lambda x: x, validator=Validator())
selected = list(b[1])
remaining = list(source)
source = iter([1, 2, 3, 4])
b = bucket(source, key=lambda x: x, validator=Validator())
member = 1 in b
membership_remaining = list(source)
b = bucket([1, 2, 3, 4, 2], key=lambda x: x, validator=Validator())
keys = sorted(b)
e = bucket([1, 2, 3], key=lambda x: x, validator=Empty())
empty = list(e[1])
default = bucket([1, 2, 1], key=lambda x: x)
truthy = bucket([1, 2, 3, 4], key=lambda x: x, validator=lambda x: x % 2 == 0)
print(json.dumps({'rejected_selection': selected, 'selection_remaining': remaining,
'rejected_membership': member, 'membership_remaining': membership_remaining,
'validated_keys': keys, 'accepted_values': list(b[2]), 'empty_callable': empty,
'default_values': list(default[1]), 'truthy_values': list(truthy[2])}))
"""

ADDLIST = """
import json, sys
sys.path.insert(0, '/source')
from boltons.dictutils import OrderedMultiDict as D
from boltons.urlutils import OrderedMultiDict as U
import importlib.util
spec = importlib.util.spec_from_file_location('standalone_urlutils', '/source/boltons/urlutils.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = {}
for name, cls in [('dictutils', D), ('urlutils', U),
                  ('standalone_urlutils', module.OrderedMultiDict)]:
    for kind in ['list', 'tuple', 'iterator', 'generator']:
        values = [0, False, None, 2, 2]
        inp = {'list': lambda: list(values), 'tuple': lambda: tuple(values),
               'iterator': lambda: iter(values), 'generator': lambda: (x for x in values)}[kind]()
        d = cls()
        d.addlist('a', inp)
        d.addlist('b', iter([8, 9]))
        d.addlist('a', iter([3]))
        d.addlist('empty', iter([]))
        result[name + ':' + kind] = {'values': d.getlist('a'), 'keys': d.keys(),
            'length': len(d), 'items': list(d.iteritems(multi=True)),
            'last': d.getlist('a')[-1:]}
    d = cls()
    d.addlist('empty', (x for x in []))
    result[name + ':empty'] = {'keys': d.keys(), 'length': len(d),
                              'items': list(d.iteritems(multi=True))}
print(json.dumps(result))
"""


def expected(task_id: str) -> dict[str, Any]:
    if task_id == "more-bucket":
        return {
            "rejected_selection": [],
            "selection_remaining": [1, 2, 3, 4],
            "rejected_membership": False,
            "membership_remaining": [1, 2, 3, 4],
            "validated_keys": [2, 4],
            "accepted_values": [2, 2],
            "empty_callable": [],
            "default_values": [1, 1],
            "truthy_values": [2],
        }
    result = {}
    for module in ("dictutils", "urlutils", "standalone_urlutils"):
        for kind in ("list", "tuple", "iterator", "generator"):
            result[module + ":" + kind] = {
                "values": [0, False, None, 2, 2, 3],
                "keys": ["a", "b"],
                "length": 2,
                "items": [
                    ["a", 0],
                    ["a", False],
                    ["a", None],
                    ["a", 2],
                    ["a", 2],
                    ["b", 8],
                    ["b", 9],
                    ["a", 3],
                ],
                "last": [3],
            }
        result[module + ":empty"] = {"keys": [], "length": 0, "items": []}
    return result


def probe(task_id: str) -> str:
    return BUCKET if task_id == "more-bucket" else ADDLIST


def compare(task_id: str, output: str) -> list[dict[str, Any]]:
    observed = json.loads(output)
    if not isinstance(observed, dict) or set(observed) != set(expected(task_id)):
        raise ValueError("Missing or unexpected observations; no pass can be inferred")
    return [
        {
            "name": key,
            "expected": value,
            "observed": observed[key],
            "status": "passed"
            if json.dumps(value, sort_keys=True) == json.dumps(observed[key], sort_keys=True)
            else "failed",
        }
        for key, value in expected(task_id).items()
    ]
