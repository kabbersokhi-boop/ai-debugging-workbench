# Recorded viewer and local execution

Patch Audit has two separate applications:

| Application | Purpose | Can run new code? |
| --- | --- | --- |
| Local Docker application | Review and run patches you explicitly approve | Yes, in restricted local containers |
| Recorded viewer | Inspect saved patches, results and downloads | No |

The [public viewer](https://ai-debugging-workbench-recorded.vercel.app/) serves saved evidence. It has no model or database credentials, Docker access, repository-import endpoints or private execution history. Opening a result does not run it again. Unavailable evidence stays unavailable; the viewer does not fall back to live execution.

The source on `main`, published releases and the hosted viewer can be different versions. See [published releases](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases) for released versions. Merging a source change does not deploy the hosted viewer.

## Run the viewer locally

From a checkout of the version you want to inspect:

```sh
docker compose -f compose.release.yaml up --build -d --wait
```

Open <http://127.0.0.1:8020/>. Building the image needs network access to package sources. Once built, the viewer serves its bundled evidence without running a candidate patch or contacting a model provider.

Stop it with:

```sh
docker compose -f compose.release.yaml down
```

For fresh audits, follow the [local quickstart](PATCH-AUDIT-QUICKSTART.md). Keep that application private. Its source import, execution and saved-history endpoints do not belong in the public viewer.

## What the build contains

The recorded image includes the small server in [`release.py`](../backend/src/workbench/release.py), the built interface and an approved set of saved recordings. It excludes the execution services and their credentials. The [image definition](../docker/release.Dockerfile) and [Compose settings](../compose.release.yaml) run it as a non-root user with a read-only filesystem and resource limits.

Content is displayed as text or read-only code. Security headers restrict loading of scripts, frames and other remote content. The viewer accepts no submitted patch, command or target URL. Container limits apply to the local image; they do not establish the settings of a hosted platform.

## Verification

The normal CI pipeline builds both applications and checks the separation. For local
checks, start the recorded viewer above and install the browser-test prerequisites:

```sh
uv sync --project backend --frozen
uv run --project backend playwright install --with-deps chromium
uv run --project backend python scripts/check_release.py
E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first
```

These checks cover the actual recorded container, absent execution/private-history routes, saved results, downloads and browser navigation. See [verification and evidence](VALIDATION.md).

Deployment configuration is in [`app.py`](../app.py), [`vercel.json`](../vercel.json) and the recorded server. Configure your own hosting account separately. Deploying or creating a release is a separate action from merging source changes; never deploy the full local execution stack as the public viewer.
