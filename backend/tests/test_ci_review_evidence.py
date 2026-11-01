"""CI evidence allowlist and failure diagnostics, without any candidate execution."""

import hashlib
import json
import runpy
import zipfile

import pytest

from workbench.config import ROOT


def test_incomplete_ci_package_fails_but_retains_inspectable_diagnostic_and_checksum(tmp_path):
    module = runpy.run_path(str(ROOT / "scripts/ci_review_evidence.py"))
    with pytest.raises(ValueError, match="missing"):
        module["package"](tmp_path, "a" * 40)
    target = tmp_path / "artifacts/ci-review-evidence.zip"
    with zipfile.ZipFile(target) as z:
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["head_sha"] == "a" * 40
        assert manifest["missing"] and not manifest["sha256"]
        assert z.testzip() is None
    assert (
        target.with_suffix(".zip.sha256").read_text().split()[0]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )


def test_ci_package_rejects_credential_shaped_log_and_ignores_unlisted_history(tmp_path):
    module = runpy.run_path(str(ROOT / "scripts/ci_review_evidence.py"))
    directory = tmp_path / "artifacts/ci-results"
    directory.mkdir(parents=True)
    (directory / "integration.log").write_text("nvapi-" + "x" * 40)
    private = tmp_path / "artifacts/private-owner-history.json"
    private.write_text("private")
    with pytest.raises(ValueError, match="Credential-shaped"):
        module["package"](tmp_path, "a" * 40)
    assert not (tmp_path / "artifacts/ci-review-evidence.zip").exists()
    assert "artifacts/private-owner-history.json" not in module["FILES"].values()
