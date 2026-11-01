"""Package an explicit, bounded CI review artifact; never traverse arbitrary runtime history."""

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "generated/authored-negative.json": "artifacts/generated-verifier-v3/authored-negative.json",
    "generated/authored-negative.md": "artifacts/generated-verifier-v3/authored-negative.md",
    "generated/reproduction.json": "artifacts/generated-verifier-v3/reproduction.json",
    "generated/failure-desktop.png": "artifacts/generated-verifier-v3/failure-desktop.png",
    "generated/failure-mobile.png": "artifacts/generated-verifier-v3/failure-mobile.png",
    **{
        f"checklists/{language}-{suffix}": f"artifacts/project-checklists/{language}-{suffix}"
        for language in ("python", "node")
        for suffix in ("parity.json", "desktop.png", "mobile.png")
    },
    "results/integration.xml": "artifacts/ci-results/integration.xml",
    "results/integration.log": "artifacts/ci-results/integration.log",
    "results/recorded.xml": "artifacts/ci-results/recorded.xml",
    "results/recorded.log": "artifacts/ci-results/recorded.log",
    "results/check.log": "artifacts/ci-results/check.log",
    "results/recovery.log": "artifacts/ci-results/recovery.log",
    "results/recovery.json": "artifacts/acceptance/recovery-check.json",
    "results/recorded-boundary.json": "artifacts/milestone-04/release-boundary.json",
    "results/migration.txt": "artifacts/ci-results/migration.txt",
}
SECRET = re.compile(
    rb"(?:nvapi-[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{32,}|sk-[A-Za-z0-9]{40,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def package(root: Path, head: str):
    output = root / "artifacts/ci-review-evidence.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    assets = {}
    missing = []
    for name, source in FILES.items():
        path = root / source
        if not path.is_file() or path.is_symlink() or not path.stat().st_size:
            missing.append(name)
            continue
        if path.stat().st_size > 16_000_000:
            raise ValueError("CI review asset exceeds its size budget: " + name)
        value = path.read_bytes()
        if not name.endswith(".png") and SECRET.search(value):
            raise ValueError(
                "Credential-shaped material rejected in CI review asset: " + name
            )
        assets[name] = value
    manifest = {
        "head_sha": head,
        "classification": "fixed public examples and authored mechanism controls; no unfamiliar-user observations",
        "missing": missing,
        "sha256": {
            name: hashlib.sha256(value).hexdigest()
            for name, value in sorted(assets.items())
        },
    }
    assets["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    assets["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(value).hexdigest()}  {name}\n"
        for name, value in sorted(assets.items())
    ).encode()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(assets.items()):
            archive.writestr(name, value)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("CI evidence ZIP integrity failure")
        for name, digest in manifest["sha256"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("CI evidence checksum mismatch")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(
        json.dumps(
            {
                "head_sha": head,
                "path": str(output),
                "sha256": digest,
                "missing": missing,
            }
        )
    )
    if missing:
        raise ValueError(
            "Required CI review evidence is missing; incomplete diagnostic package retained"
        )
    return output


if __name__ == "__main__":
    package(
        ROOT,
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    )
