"""Verify the actual recorded container boundary. No provider credential is needed."""

import json
from pathlib import Path

import httpx

import docker

client = docker.from_env()
try:
    container = client.containers.get("ai-debugging-recorded-release-explorer-1")
    config, host = container.attrs["Config"], container.attrs["HostConfig"]
    names = [value.split("=", 1)[0] for value in config["Env"]]
    assert not any("NVIDIA" in name or "DATABASE" in name for name in names)
    assert config["User"] == "10001:10001"
    assert host["ReadonlyRootfs"] and host["Memory"] == 192 * 1024 * 1024
    assert host["PidsLimit"] == 32 and host["NanoCpus"] == 500000000
    assert host["CapDrop"] == ["ALL"] and not container.attrs["Mounts"]
    probe = container.exec_run(
        [
            "python",
            "-c",
            "import importlib.util,pathlib,json; "
            "print(json.dumps({name:importlib.util.find_spec(name) is not None "
            "for name in ('workbench','docker','langgraph')} | "
            "{'socket':pathlib.Path('/var/run/docker.sock').exists()}))",
        ]
    )
    assert probe.exit_code == 0
    authority = json.loads(probe.output)
    assert not any(authority.values())
    write = container.exec_run(
        ["python", "-c", "open('/release/unapproved-write','w').write('x')"]
    )
    assert write.exit_code != 0
    with httpx.Client(base_url="http://127.0.0.1:8020", timeout=10) as http:
        response = http.get("/api/health")
        response.raise_for_status()
        health = response.json()
        assert health["mode"] == "recorded" and health["provider_token_budget"] == 0
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        for path in (
            "/api/runs",
            "/api/repairs/unknown",
            "/retail/cart.js",
            "/candidates",
        ):
            assert http.get(path).status_code == 404
            assert http.post(path, json={}).status_code == 405
        manifest = http.get("/api/recordings").json()
        assert len(manifest["records"]) >= 3
        for row in manifest["records"]:
            recording = http.get("/api/recordings/" + row["id"])
            recording.raise_for_status()
            assert recording.json()["recording"]["historical"]
    proof = {
        "mode": "real_recorded_container_audit",
        "container_image_id": container.attrs["Image"],
        "nonroot": True,
        "read_only": True,
        "memory_bytes": host["Memory"],
        "pids": host["PidsLimit"],
        "cpu_nanos": host["NanoCpus"],
        "mounts": [],
        "authority_modules": authority,
        "provider_credentials": False,
        "database_credentials": False,
        "mutation_routes": "405",
        "private_history": "404",
        "health": health,
    }
    output = Path("artifacts/milestone-04/release-boundary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))
finally:
    client.close()
