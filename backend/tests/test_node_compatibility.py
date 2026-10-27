"""Safe path expansion, immutable dependency provenance and historical evidence guards."""

import copy
import gzip
import io
import json
import tarfile

import pytest
from test_repository_audit import archive_for

from workbench.config import ROOT
from workbench.evaluator.catalog import digest
from workbench.repository_audit.campaign import retained_campaign
from workbench.repository_audit.contracts import LEGACY_PATH_POLICY, PATH_POLICY, path
from workbench.repository_audit.intake import (
    Rejected,
    git_tree,
    snapshot_record,
    unpack,
    validate_files,
)

HISTORICAL_PATH = "benchmark/code/arr-flatten-0.1.0 (do-while).js"


def test_exact_historical_filename_is_preserved_without_normalization():
    assert path(HISTORICAL_PATH) == HISTORICAL_PATH
    with pytest.raises(ValueError):
        path(HISTORICAL_PATH, LEGACY_PATH_POLICY)
    files = {HISTORICAL_PATH: b"module.exports = [1];\n", "LICENSE": b"MIT\n"}
    decoded, modes = unpack(archive_for(files))
    assert decoded == files
    snapshot = snapshot_record(
        "fixture/spaces",
        "a" * 40,
        git_tree(files, modes),
        files,
        modes,
        {"path_policy": PATH_POLICY},
    )
    assert snapshot["file_hashes"][HISTORICAL_PATH] == digest(files[HISTORICAL_PATH])


@pytest.mark.parametrize(
    "name",
    [
        "/absolute.js",
        "../escape.js",
        "a/../escape.js",
        "a//alias.js",
        "a/./alias.js",
        "a\\escape.js",
        "C:/escape.js",
        "a/ file.js",
        "a/file.js ",
        "a/file.js.",
        ".Git/config",
        "a\nscript.js",
        "a\x00script.js",
        "bad\udcff.js",
        "a;touch x.js",
        "$(touch x).js",
        "`touch x`.js",
        "a\tfile.js",
        "a" * 241,
    ],
)
def test_unsafe_or_ambiguous_names_remain_rejected(name):
    with pytest.raises(ValueError):
        path(name)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_links_cannot_escape_via_the_new_filename_contract(kind):
    with pytest.raises(Rejected):
        unpack(archive_for({HISTORICAL_PATH: b""}, special=kind))


def test_prefix_collisions_duplicates_and_aliases_fail_closed():
    files = {"dir": b"file", "dir/child (1).js": b"child"}
    with pytest.raises(Rejected, match="collision"):
        validate_files(files, dict.fromkeys(files, "100644"))
    for names in (("file.js", "file.js"), ("file.js/",), ("a//file.js",)):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for name in names:
                member = tarfile.TarInfo("root/" + name)
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
        with pytest.raises((Rejected, ValueError)):
            unpack(gzip.compress(stream.getvalue()))


def test_existing_byte_and_file_limits_are_unchanged():
    with pytest.raises(Rejected):
        validate_files({str(i): b"x" for i in range(1001)}, {str(i): "100644" for i in range(1001)})
    with pytest.raises(Rejected):
        validate_files({"large (1).js": b"x" * 1000001}, {"large (1).js": "100644"})
    with pytest.raises(Rejected):
        unpack(b"x" * 8000001)


def test_capsule_bytes_license_and_version_match_pinned_manifest():
    root = ROOT / "docker/node-compat"
    manifest = json.loads((root / "manifest.json").read_text())
    package = json.loads((root / "array-flatten/package.json").read_text())
    assert manifest["version_pin"] == package["version"] == "1.0.0"
    assert package["license"] == manifest["license"] == "MIT"
    assert not package.get("dependencies")
    for name, checksum in manifest["files"].items():
        assert digest((root / "array-flatten" / name).read_bytes()) == checksum
    assert "Permission is hereby granted" in (root / "array-flatten/LICENSE").read_text()
    changed = copy.deepcopy(manifest)
    changed["files"]["array-flatten.js"] = "0" * 64
    assert (
        digest((root / "array-flatten/array-flatten.js").read_bytes())
        != changed["files"]["array-flatten.js"]
    )


def test_original_g3_stays_four_of_six_and_every_saved_identity_replays():
    summary, records = retained_campaign(ROOT / "evaluation/repository-examples/g3")
    assert len(records) == 28
    assert summary["counts"]["genuine_candidates_executed"] == 4
    assert summary["counts"]["candidate_outcomes"] == {
        "ordinary_pass_independent_pass": 3,
        "ordinary_failure": 1,
        "unsupported_environment": 1,
        "unsupported_source": 1,
    }


def test_new_runtime_requires_fresh_control_and_exact_plan_bindings():
    from workbench.evaluator.catalog import identity
    from workbench.repository_audit import independent

    root = ROOT / "evaluation/repository-examples/g3/results"
    original = json.loads(
        gzip.decompress((root / "flatten-recursive-reference-1.json.gz").read_bytes())
    )
    evidence = copy.deepcopy(original["evidence"])
    evidence["plan"]["runtime"] = "node22_compat"
    evidence["plan"]["image_id"] = "sha256:" + "b" * 64
    vp = evidence["verification"]["plan"]
    vp.update(
        runtime="node22_compat",
        image_id=evidence["plan"]["image_id"],
        ordinary_plan_id=identity(evidence["plan"]),
    )
    evidence["verification"]["id"] = identity(vp)
    evidence["approval"].update(plan_id=identity(evidence["plan"]), verification_id=identity(vp))
    with pytest.raises(ValueError):
        independent.check(evidence)


def test_base_preflight_rejects_an_unapproved_or_changed_plan_before_docker():
    from workbench.repository_audit.base_preflight import execute

    with pytest.raises(ValueError, match="exact source/runtime plan"):
        execute({}, {"tests": []}, "0" * 64)
