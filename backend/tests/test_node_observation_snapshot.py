"""Execute the real Node adapter; shim only its fixed input-file transport offline."""

import json
import subprocess

import pytest
from test_independent_verification import checked_plan, fixture_verification

from workbench.repository_audit.verification import ROOT, VerificationPlan, interpret
from workbench.repository_audit.verifiers import LEGACY_VERIFIER, verifier_sources

CASES = [
    (
        "shared_object",
        "'use strict'; const result={value:0}; module.exports=x=>{result.value=x;return result}",
        [[1], [2]],
        [{"value": 1}, {"value": 2}],
        "checks_passed",
    ),
    (
        "hidden_early_failure",
        "const result={value:0}; module.exports=x=>{result.value=x===1?0:1;return result}",
        [[1], [2]],
        [{"value": 1}, {"value": 1}],
        "assertions_failed",
    ),
    (
        "nested_shared_arrays",
        "const child={value:0}; const result={a:child,b:[child,[child]]};"
        "module.exports=x=>{child.value=x;return result}",
        [[1], [2]],
        [{"a": {"value": i}, "b": [{"value": i}, [{"value": i}]]} for i in (1, 2)],
        "checks_passed",
    ),
    (
        "shared_array",
        "const result=[0,{value:0}];"
        "module.exports=x=>{result[0]=x;result[1].value=x;return result}",
        [[1], [2]],
        [[1, {"value": 1}], [2, {"value": 2}]],
        "checks_passed",
    ),
    (
        "scalars",
        "module.exports=x=>x",
        [[None], [True], [False], [0], [-2], [1.5], ["é🚀"]],
        [None, True, False, 0, -2, 1.5, "é🚀"],
        "checks_passed",
    ),
]


def case_plan(case):
    _, _, args, expected, _ = case
    original = checked_plan(fixture_verification("node22"))
    value = original.model_dump()
    value["export"] = ""
    value["assertions"] = [
        {
            "id": f"call{i}",
            "requirement_id": original.assertions[0].requirement_id,
            "args": arguments,
            "kwargs": {},
            "expected": want,
        }
        for i, (arguments, want) in enumerate(zip(args, expected, strict=True))
    ]
    return VerificationPlan.model_validate(value)


def run_adapter(tmp_path, source, plan, adapter=None):
    module = tmp_path / "candidate.cjs"
    module.write_text(source)
    inputs = {
        "module": str(module),
        "export": "",
        "calls": [a.model_dump(include={"id", "args", "kwargs"}) for a in plan.assertions],
    }
    bootstrap = """
const fs = require('node:fs');
const original = fs.readFileSync;
fs.readFileSync = function(path, ...rest) {
  return path === '/verifier/inputs.json' ? process.argv[1] : original.call(this, path, ...rest);
};
require(process.argv[2]);
"""
    result = subprocess.run(
        ["node", "-e", bootstrap, json.dumps(inputs), str(adapter or ROOT / "probe.cjs")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    execution = {
        "status": "tests_passed" if result.returncode == 0 else "tests_failed",
        "ordinary": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "output_truncated": False,
        },
    }
    return execution, interpret(plan, execution)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_actual_adapter_captures_each_completed_call(tmp_path, case):
    plan = case_plan(case)
    execution, interpreted = run_adapter(tmp_path, case[1], plan)
    assert execution["ordinary"]["exit_code"] == 0, execution
    assert interpreted["status"] == case[4], interpreted
    observed = [c["observed"] for c in interpreted["checks"]]
    expected = case[3] if case[0] != "hidden_early_failure" else [{"value": 0}, {"value": 1}]
    assert observed == expected


@pytest.mark.parametrize("case", CASES[:2], ids=lambda c: c[0])
def test_retired_actual_adapter_reproduces_both_review_findings(tmp_path, case):
    plan = case_plan(case)
    _, interpreted = run_adapter(tmp_path, case[1], plan, ROOT / "verifiers/v1/probe.cjs")
    expected = "assertions_failed" if case[0] == "shared_object" else "checks_passed"
    assert interpreted["status"] == expected
    values = [c["observed"] for c in interpreted["checks"]]
    assert values == ([{"value": 2}] * 2 if case[0] == "shared_object" else [{"value": 1}] * 2)


UNSUPPORTED = [
    "undefined",
    "NaN",
    "Infinity",
    "-Infinity",
    "1n",
    "Symbol('x')",
    "(()=>0)",
    "({value:undefined})",
    "([undefined])",
    "({value:NaN})",
    "new Date(0)",
    "new (class Value {constructor(){this.value=1}})()",
    "Object.create(null)",
    "Array(2)",
    "(()=>{const a={};a.self=a;return a})()",
    "(()=>{const a=[];a.push(a);return a})()",
    "({get value(){throw Error('unreadable')}})",
    "({toJSON(){return undefined}})",
    "({toJSON(){return 1}})",
    "(()=>{const a={};Object.defineProperty(a,'toJSON',{value(){throw Error('bad')}});return a})()",
    "new Proxy({},{ownKeys(){throw Error('bad keys')}})",
    "Array(257).fill(0)",
    "Object.fromEntries(Array.from({length:257},(_,i)=>['k'+i,0]))",
    "'a'.repeat(16383)",
    "'é'.repeat(9000)",
    "'\\u0000'.repeat(3000)",
    "Array.from({length:9}).reduce(a=>[a],0)",
]


@pytest.mark.parametrize("expression", UNSUPPORTED)
def test_unsupported_or_unserializable_call_is_explicit_error_not_coerced(tmp_path, expression):
    case = ("unsupported", "", [[1], [2]], [None, 7], "check_execution_failed")
    plan = case_plan(case)
    execution, interpreted = run_adapter(
        tmp_path, f"module.exports=x=>x===1?({expression}):7", plan
    )
    assert execution["ordinary"]["exit_code"] == 0, execution
    assert interpreted["status"] == "check_execution_failed", interpreted
    observations = json.loads(execution["ordinary"]["stdout"])["observations"]
    assert observations[0]["kind"] == "execution_error"
    assert observations[1] == {"id": "call1", "kind": "value", "value": 7}


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("Array(256).fill(0)", [0] * 256),
        (
            "Object.fromEntries(Array.from({length:256},(_,i)=>['k'+i,0]))",
            {f"k{i}": 0 for i in range(256)},
        ),
        ("'a'.repeat(16382)", "a" * 16382),
        ("Array.from({length:8}).reduce(a=>[a],0)", [[[[[[[[0]]]]]]]]),
        (
            'JSON.parse(\'{"__proto__":{"value":1},"toJSON":"ordinary data"}\')',
            {"__proto__": {"value": 1}, "toJSON": "ordinary data"},
        ),
    ],
)
def test_supported_boundaries_and_json_property_names(tmp_path, expression, expected):
    plan = case_plan(("boundary", "", [[]], [expected], "checks_passed"))
    _, interpreted = run_adapter(tmp_path, "module.exports=()=>" + expression, plan)
    assert interpreted["status"] == "checks_passed", interpreted


def test_candidate_owned_values_remain_mutable_and_unmodified(tmp_path):
    source = """'use strict';
const nested={value:0}; const result={nested};
module.exports=x=>{
  if(Object.isFrozen(result)||Object.isFrozen(nested)||Object.keys(result).join()!=='nested')
    throw Error('candidate object modified');
  nested.value=x;
  return result;
};"""
    plan = case_plan(
        (
            "unmodified",
            "",
            [[1], [2]],
            [{"nested": {"value": 1}}, {"nested": {"value": 2}}],
            "checks_passed",
        )
    )
    _, interpreted = run_adapter(tmp_path, source, plan)
    assert interpreted["status"] == "checks_passed", interpreted


def test_array_length_is_captured_once_before_reading_items(tmp_path):
    source = """module.exports=()=>{
  let reads=0;
  return new Proxy([''],{get(target,key){
    if(key==='length' && ++reads>1) throw Error('length read again');
    return target[key];
  }});
};"""
    plan = case_plan(("length", "", [[]], [[""]], "checks_passed"))
    _, interpreted = run_adapter(tmp_path, source, plan)
    assert interpreted["status"] == "checks_passed", interpreted


def test_pinned_archive_is_the_exact_reviewed_adapter():
    from workbench.evaluator.catalog import digest

    sources = verifier_sources(LEGACY_VERIFIER)
    assert (
        digest(sources["probe.cjs"])
        == "512cb089d8fab0de8bf700c0d14fdfa254a2cb0d26dcba29b347b9c3dbffa8bb"
    )
    assert (ROOT / "probe.py").read_text() == sources["probe.py"]
