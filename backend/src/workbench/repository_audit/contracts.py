"""Versioned local-owner contracts. Repository content cannot approve an execution plan."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from workbench.evaluator.catalog import identity

SHA = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
HASH = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\Z")
PATH = re.compile(r"[A-Za-z0-9_.@+/-]{1,240}\Z")
MAX_FILES = 1000
MAX_SOURCE = 8_000_000
MAX_FILE = 1_000_000
MAX_ARCHIVE = 8_000_000
MAX_EXPANDED = 16_000_000
RUNTIMES = {
    "python312": "ai-agent-evaluator:python312-v1",
    "node22": "patch-audit-node:22-v1",
}
POLICY = {
    "version": "repository-sandbox-v1",
    "network": "none",
    "uid": "1000:1000",
    "rootfs": "read-only",
    "source": "read-only named volume; separate bounded scratch and offline dependencies",
    "cpu": 1,
    "memory_bytes": 536870912,
    "pids": 64,
    "scratch_bytes": 134217728,
    "tmp_bytes": 8388608,
    "shm_bytes": 8388608,
    "output_bytes_per_stream": 65536,
    "log_storage_bytes": 131072,
    "file_bytes": 16777216,
    "host_mounts": [],
    "capabilities": [],
    "credentials": False,
    "docker_socket": False,
    "artifacts": ["stdout", "stderr", "exit status", "runtime identity"],
}


def repository(value: str) -> str:
    if not REPOSITORY.fullmatch(value) or value.split("/")[1] in (".", ".."):
        raise ValueError("Use owner/repository, without a URL, credentials, query or .git suffix")
    if value.endswith(".git"):
        raise ValueError("Use owner/repository without .git")
    return value.lower()


def path(value: str) -> str:
    if not PATH.fullmatch(value) or any(p in ("", ".", "..", ".git") for p in value.split("/")):
        raise ValueError("Unsupported or unsafe repository path")
    return value


def production(value: str) -> bool:
    """Conservative scope filter, not an anti-tampering claim about ordinary tests."""
    path(value)
    parts = value.lower().split("/")
    name = parts[-1]
    forbidden = {
        "test",
        "tests",
        "__tests__",
        "spec",
        "specs",
        "scripts",
        "benchmark",
        "benchmarks",
    }
    return (
        not any(p.startswith(".") or p in forbidden for p in parts)
        and name.endswith((".py", ".js", ".mjs", ".cjs"))
        and not name.startswith(("test_", "test.", "conftest.", "setup.", "noxfile.", "gulpfile."))
        and not any(s in name for s in (".test.", "_test.", ".spec.", ".config.", "config."))
        and name not in ("manage.py", "fabfile.py", "wscript.py")
    )


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Intake(Contract):
    repository: str = Field(max_length=140)
    base_commit: SHA

    @field_validator("repository")
    @classmethod
    def validated_repository(cls, value: str) -> str:
        return repository(value)


class Import(Contract):
    snapshot_id: HASH
    patch: str = Field(min_length=1, max_length=65536)
    approved_paths: list[str] = Field(min_length=1, max_length=4)
    source_reference: str = Field(default="", max_length=500)
    author_label: str = Field(default="Unknown authorship", max_length=200)


Argument = Annotated[str, Field(min_length=1, max_length=500)]
Command = Annotated[list[Argument], Field(min_length=1, max_length=32)]


class Plan(Contract):
    version: Literal["repository-plan-v1"] = "repository-plan-v1"
    snapshot_id: HASH
    candidate_hash: HASH
    runtime: Literal["python312", "node22"]
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    working_directory: str = Field(default=".", max_length=240)
    setup: list[Command] = Field(default_factory=list, max_length=3)
    tests: Command
    test_description: str = Field(min_length=1, max_length=500)
    timeout_seconds: int = Field(default=45, ge=1, le=120)
    dependency_policy: Literal["offline-only"] = "offline-only"
    policy_hash: HASH = identity(POLICY)

    @field_validator("working_directory")
    @classmethod
    def directory(cls, value):
        return value if value == "." else path(value)

    @field_validator("tests", "setup")
    @classmethod
    def arguments(cls, value):
        for command in value if value and isinstance(value[0], list) else [value]:
            if any(
                "\x00" in argument or "\n" in argument or "\r" in argument for argument in command
            ):
                raise ValueError("Command arguments cannot contain control characters")
            if sum(map(len, command)) > 4096:
                raise ValueError("Command length limit exceeded")
        return value


class Confirm(Contract):
    candidate_id: HASH
    plan_id: HASH
    approve_exact_plan: Literal[True]
    confirm_local_execution: Literal[True]
