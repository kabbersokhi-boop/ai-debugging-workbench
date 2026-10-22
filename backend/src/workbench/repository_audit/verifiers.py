"""Trusted adapter registry. Retired bytes may verify history but cannot authorize new runs."""

from pathlib import Path

from workbench.evaluator.catalog import digest

ROOT = Path(__file__).parent
CURRENT_VERIFIER = "json-observer-v2"
LEGACY_VERIFIER = "json-observer-v1"
LEGACY_HASHES = {
    "probe.py": "8c86960b6df2dc2a166497a93b09cfd8faf3e249c253c64811d6364b115b78bc",
    "probe.cjs": "512cb089d8fab0de8bf700c0d14fdfa254a2cb0d26dcba29b347b9c3dbffa8bb",
}


def verifier_sources(version=CURRENT_VERIFIER):
    if version not in (CURRENT_VERIFIER, LEGACY_VERIFIER):
        raise ValueError("Unknown observation verifier version")
    folder = ROOT if version == CURRENT_VERIFIER else ROOT / "verifiers" / "v1"
    sources = {name: (folder / name).read_text() for name in ("probe.py", "probe.cjs")}
    if version == LEGACY_VERIFIER and {k: digest(v) for k, v in sources.items()} != LEGACY_HASHES:
        raise ValueError("Trusted historical verifier archive integrity failure")
    return sources


def verifier_hashes(version=CURRENT_VERIFIER):
    return {name: digest(source) for name, source in verifier_sources(version).items()}
