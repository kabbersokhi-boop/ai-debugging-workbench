# Milestone 4 — evaluation, usability and release candidate

**Final-review correction:** guest UUID authorization was corrected after reviewed head `f1865c0`. Section 9 contains the correction and current sign-off references. The frozen benchmark records and original evidence below are unchanged.

## 1. Executive summary

The existing repair engine now supports four selectable development scenarios, backed by twelve immutable implementation defects spanning pricing, shipping, transitions and input bounds. Actual NVIDIA workflows reproduced, diagnosed and repaired all four development cases. The frozen eight-case held-out comparison completed all 24 condition runs. **One-shot whole-target, loop whole-target and loop retrieval each resolved 8/8 cases; this experiment demonstrates no resolution improvement from the loop or retrieval.** This is a small related-source synthetic suite, not a production accuracy estimate.

The product puts workflow progress, result, original/candidate comparison, diff and named checks ahead of raw engineering records. Delayed start/cancel responses cannot cross investigation selections. Candidate interaction now runs in a constrained remote browser and returns pixels; generated scripts are no longer delivered to visitor tabs.

A separate, read-only recorded release works without NVIDIA or database credentials. It includes actual successful model-generated repairs, an explicitly offline stopped security probe, source/diff/check inspection and a [captioned walkthrough](../demo/walkthrough.mp4). No public endpoint was activated. The private repository and earlier PRs remain unmerged.

## 2. Delivered functionality and evidence modes

| Capability | Actual status |
| --- | --- |
| Four selectable scenarios; reproduce → diagnose → repair | Working with real NVIDIA, PostgreSQL checkpoints, actual MCP and independent browser verification |
| Twelve immutable source variants, four behaviors, development/evaluation split | Working; four source files per snapshot, only four development cases selectable |
| Saved history, cancellation, evidence downloads and original source preservation | Retained and regression tested |
| Retrieval inspector, source citations, Monaco diff and readable execution records | Working; verbose identities/requests remain expandable |
| Original/candidate interaction | Trusted frozen original storefront plus private remote candidate controls/pixels |
| Recorded explorer | Working without provider credentials; three actual curated records, no live fallback or new inference |
| Stopped/nonverified example | Actual infinite-loop **offline security probe**, explicitly not an AI repair failure or verified fix |
| Frozen held-out comparison | Completed once under experiment v2; every final candidate passed issue, feedback and sealed checks |
| Public live repair, arbitrary repositories/uploads/commands/publication | Deliberately excluded |
| Public demo URL | **Not deployed**; owner-authorized destination/TLS activation remains required |

Offline deterministic provider tests are separate from real-provider evidence. Historical M3 recordings retain their historical source, verifier and runtime identity. A saved passing result is not relabeled as verification under the current image.

## 3. Decisions, source identity and isolation

### Explicit scenarios rather than a platform

[Versioned scenario manifest](../../evals/scenarios-v1.json), [runtime allowlist](../../backend/src/workbench/rag/scenarios.json) and committed snapshots identify each defect. Variants originate in commit `9e8668b`; canonical citation/patch paths remain target-application paths while `origin_path` identifies the committed variant. The original defective fixture/snapshot is unchanged. Ingestion and MCP accept only approved immutable target files. Reports, recordings, verifier code, final checks and evaluation controls are excluded from runtime retrieval and source tools.

Every reproduction uses its selected source. Diagnosis, graph state, candidate creation and original preview retain that identity. Cache keys and verification artifacts bind source snapshot, exact candidate bytes, scenario expectations, verifier version and **actual candidate runtime image ID**. Candidate files are hashed before and after browser execution. Old artifacts stay readable; they cannot establish a new image's pass.

### Reuse the working engine

The existing NVIDIA adapters, LangChain grounding, LangGraph repair loop, native PostgreSQL checkpoints and real MCP tools remain. The benchmark runs that same graph with an in-memory saver and atomic disk records; it does not claim benchmark persistence is the product's native checkpoint store. No second agent framework, model leaderboard or repair publication workflow was added.

### Split public release from privileged execution

[Recorded release configuration](../../compose.release.yaml) runs a minimal image containing only the recorded server, frontend and curated immutable evidence. It has no workbench execution modules, provider/database credentials, Docker SDK/socket, candidate environment or live run routes. It runs as UID 10001, read-only root, no capabilities/new privileges, 192 MiB memory, 0.5 CPU, 32 PIDs, 8 MiB tmp and one worker/32 request slots. Mutation methods return 405; private run APIs return 404. CSP denies framing/forms/objects and arbitrary connections. Request/session admission and explicit unavailable mode are tested.

Private guest staging adds persisted ownership and row-locked nonrefundable session/global request/token reservations; artifacts and derived records follow run ownership. Cross-origin actions are denied. Public mode has zero provider/execution budget. Expired public sessions are reaped; immutable release records need no generated-artifact cleanup. Private candidate verification/cancellation/timeout removes containers; idle previews expire and broker restart reconciles leftovers. Historical owner evidence is intentionally retained.

The broker still has Docker authority; candidate Chromium still uses `--no-sandbox`. Remote named controls and bounded screenshots protect the visitor from executing candidate scripts, but this is **not a complete hostile-code sandbox**. Keep the live stack private. [Deployment boundary and exact activation steps](../RELEASE.md) distinguish tested local preparation from public hosting.

## 4. Frozen evaluation and measured outcomes

[Full results](../RESULTS.md), [raw 24 records](assets/milestone-04/evaluation-results.json), [summary](assets/milestone-04/evaluation-summary.json), [final checks/screenshots](assets/milestone-04/evaluation/) and [protocol](../../evals/README.md).

- Frozen experiment: `retail-repair-comparison-experiment-v2`, committed at `78989e3` before any held-out call.
- Configuration SHA-256: `e4b319b0881395f940e2828bba8a179be0195e4a6e01c0d084aa78c6a176d138`.
- Twelve distinct source implementations: four development, eight held out. No report paraphrases count as new defects.
- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`, temperature 0, thinking disabled, 2,000 output tokens/request, 32,768 input bound. Existing model/settings reused.
- Same symptom report and original issue observation; no prior AI diagnosis in any condition. Whole input contains all four target files; retrieval uses existing PostgreSQL lexical/dense fusion, NVIDIA reranking and bounded selected context.
- One-shot: one decision/patch, at most two chat HTTP attempts including transient retry. Each loop: six decisions, two patches, at most eight chat HTTP attempts. Source tools remain bounded in all conditions.
- Available feedback: fixed twelve trusted browser checks and proposal-validation errors. Twelve separate sealed final probes run only after termination and never reach the model. Final scoring binds candidate bytes, source, scenario, scoring code and actual runtime.
- Predeclared total budget: **256 HTTP attempts, 256,000 reserved output tokens, 90 persisted wall-clock minutes**, at most 300 seconds per case/condition. V1 was frozen but never executed: a pre-call audit found missing persisted-deadline enforcement, corrected and frozen as v2 without held-out feedback. V1 remains committed.

| Condition | Usable | Issue passed | All feedback passed | All sealed checks passed | Resolved | Median elapsed | Chat HTTP attempts | All provider attempts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| One-shot whole target | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 28.60 s | 9 | 9 |
| Loop whole target | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 20.13 s | 8 | 8 |
| Loop retrieval | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 38.49 s | 16 | 64 |

All conditions produced one usable patch per case. No proposal was manually corrected or hidden. There were no terminal invalid-output, verification, timeout or infrastructure failures in these 24 runs. One `ConnectTimeout` occurred for `invalid-default` one-shot; its configured retry succeeded. Both HTTP attempts remain in the ledger/raw evidence. The stopped offline example is **not** counted as a held-out model failure.

Actual transport usage: **81/256 HTTP attempts**, **66,000/256,000 reserved output tokens**. The 81 include 33 chat attempts (32 successful, one timeout), 40 embedding requests and eight reranking requests. Returned usage reports 166,681 chat prompt + 9,529 completion tokens; embeddings report 44,205 tokens and reranking 12,224 tokens. These provider workload units are not a verified billing formula. The timeout returned no usage. **Monetary cost is unavailable.** Failed attempts are still charged against request reservations.

Median initial context was 15,431 JSON UTF-8 bytes for whole context versus 3,775.5 for retrieval. Retrieval's additional source decisions/workloads increased measured aggregate usage; it did not improve resolution. Fixed condition order, original-check cache reuse, cold indexing and shared-host noise prevent a causal speed claim. The prior M2 eight-query retrieval suite is reused honestly: lexical mean recall@5 1.000 over six labeled queries versus 0.833 for hybrid/reranking, plus two no-answer cases. It was one defect, not eight.

Exact frozen candidate runtime: `sha256:edaa4ae5534a7d6ed8ec84fc3808b90fbb305fab28763022650c06f83b94251a`. Frozen broker image: `sha256:0abfd845a03d191fdee177cea24fd8ccd8087ab2af723b781a9001f6cb9b17d6`, retained locally as `ai-debugging-workbench:eval-v2`. Frozen verifier: `c39b63186c6c3d9d7d3d9196729044db38efa1f76484afd87d205423b8e9b11a`. The committed protocol contains code/runtime hashes and refuses changed identities. [Final identity audit](assets/milestone-04/protocol-identity.json) confirms all 32 frozen engine/scoring/snapshot hashes still match and both exact experiment images are retained. On a different host without these exact images, create a new versioned replication as documented; do not overwrite v2 or call these cases untouched again.

### Actual product workflows

Four development runs separately reproduced, diagnosed and feedback-verified: [shipping](assets/milestone-04/live-shipping-run.json), [quantity](assets/milestone-04/live-cart-quantity.json), [decrement](assets/milestone-04/live-decrement-skip.json), [lower bound](assets/milestone-04/live-clamp-zero.json). They used 32 provider HTTP calls within the separately declared 80-request development ceiling. These product runs are not held-out scores. No extra provider run was made to hide the UI failure described below.

Actual successful endpoints reused: NVIDIA chat `/v1/chat/completions` and embeddings `/v1/embeddings` at `integrate.api.nvidia.com`; native reranking `nvidia/llama-nemotron-rerank-vl-1b-v2` through the existing NVIDIA retrieval adapter. Embeddings use `nvidia/nemotron-3-embed-1b`. Sanitized calls/outputs/usage accompany the records; keys and authorization headers do not.

## 5. Verification and preservation

The following commands were executed; final implementation and image coverage are identified separately from earlier live captures. Logs distinguish final offline acceptance, real provider execution, saved-run reopening and earlier failures.

| Command / actual check | Result |
| --- | --- |
| `./scripts/check` | Ruff/format passed, Pyright 0 errors; 57 unit tests passed; TypeScript/Vite production build passed |
| `M4_SAVED_REOPEN=1 ./scripts/e2e` | 48 passed, three explicit real-provider opt-in skips, 57 deselected in 229.00 s on tested implementation `d603447`; includes final compact mobile geometry and actual saved-run reopening without inference |
| `./scripts/e2e` | 47 passed, four explicit opt-in skips, 57 deselected in 238.21 s; final presentation also covered by the final-image browser checks below |
| `M4_SAVED_REOPEN=1 ./scripts/e2e -k 'm4_saved_shipping or repair_action_response or offline_repair_browser or recorded_explorer_first or selected_scenario'` | Earlier image: six passed in 58.40 s before the mobile/dependency follow-up; saved NVIDIA run, delayed selection/reset, diff lifecycle, evidence, source identity and recorded desktop/mobile |
| Final source/credential/image audit | 24 backend source files match each service; private/public frontend index matches the production build; only API has NVIDIA configuration; no environment file in images; only broker has Docker socket |
| `./scripts/recovery-smoke` | API SIGKILL/restart; unfinished reproduction interrupted, historical completed rows retained, fresh reproduction succeeds |
| `M4_SAVED_REOPEN=1 ./scripts/e2e -k 'm4_saved_shipping or repair_action_response'` | 3 passed; actual saved shipping comparison and delayed start/cancel identity tests, no new inference |
| `LIVE_NVIDIA_M4=1 ./scripts/e2e -k m4_live_workflow` | Actual shipping repair verified; browser test exposed Monaco teardown error. Original/candidate $136/$128 evidence retained. Corrected UI tested by saved reopen |
| `uv run --project backend python scripts/demo_scenarios.py --live` | Other three development workflows reproduced/diagnosed/verified |
| `uv run --project backend python scripts/evaluate_repairs.py --live --split evaluation` | All 24 frozen condition runs completed; 8/8 resolved per condition, 81 provider attempts |
| `uv run --project backend python scripts/summarize_repairs.py` | Complete denominator and configuration identity validated; read-only summary generation |
| `docker compose -f compose.release.yaml up --build -d --wait` | Actual minimal recorded container built and healthy |
| `uv run --project backend python scripts/check_release.py` | Passed actual Docker/resource/authority/API audit; no credential or execution authority |
| `E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first` | 1 passed in 3.09 s on `d603447`; desktop/mobile, stopped record selection, no live request or page error |
| `npm audit --prefix frontend --omit=dev --json` | Zero findings after the sanitizer patch override; initial two low findings retained |
| `uvx pip-audit --no-deps --disable-pip -r docker/release-requirements.txt --format json` | No known vulnerabilities in the fourteen pinned public Python packages |
| Backup restore + Alembic 004 → 005 → 004 → 005 | Passed on disposable restored DB; production volume never reset |
| Historical subset / artifact / source comparison | All prior rows unchanged; reviewed M1 screenshots byte-identical; original fixture/snapshot and M1–M3 reports unchanged |
| Staged credential scan / `git diff --check` | Passed staged credential scan and whitespace validation after transcript normalization |
| GitHub Actions offline acceptance | Core implementation passed [38822693122](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/38822693122); final `d603447` mobile/dependency acceptance passed [38823735676](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/38823735676), including full offline suite, crash recovery, recorded build, actual container audit and desktop/mobile browser checks |

Focused coverage includes scenario/source/cache isolation, exact verification identity, retrieval leakage boundaries, private guest ownership/artifact access/idempotency/expiry, atomic shared quotas, candidate/network/filesystem restrictions, cancellation/recovery/cleanup, invalid outputs and failed checks, recorded mode, first-visit/mobile flows, and deterministic delayed-response selection/reset regressions. CI requires no NVIDIA key.

Logs: [final checks](assets/milestone-04/m4-final-acceptance-check.txt), [full offline suite](assets/milestone-04/m4-final-acceptance-e2e.txt), [final-image browser journey](assets/milestone-04/m4-final-image-browser.txt), [recorded container audit](assets/milestone-04/release-boundary.json), [source/credential identity audit](assets/milestone-04/final-runtime-binding.json), [recorded public browser](assets/milestone-04/m4-final-acceptance-public-browser.txt), [final crash recovery](assets/milestone-04/m4-release-acceptance-recovery.txt), [clean-runner implementation CI](assets/milestone-04/ci-final-implementation.json).

[Preservation audit](assets/milestone-04/preservation.json): all pre-M4 54 runs, 245 events, ten investigations, eight repairs, one snapshot/index, 84 chunks and PostgreSQL checkpoint rows retained unchanged. Revision 005 adds nullable ownership plus guest/quota tables; old evidence is not rewritten. Reviewed M1 screenshot hashes remain `addefe4e…a2a3a5` and `69d81a27…97b2a`.

## 6. Material problems resolved

- **Selection identity:** start/cancel responses now bind to investigation identity, selection epoch and initiating action. Switching A → B cannot install A's response or clear B's loading/error state. Deterministic browser tests delay both actions and switch selection.
- **Preview replacement race:** initial remote CI run `38820202280` passed 45 browser/integration cases but failed one cold preview-reset interaction. Old controls remained clickable while replacement startup was pending. Startup now removes the previous viewer immediately; a deterministic delayed-reset test checks this boundary. The original failed CI log is retained.
- **Monaco lifecycle:** initial real shipping workflow verified the patch but hit `TextModel got disposed before DiffEditorWidget model got reset`. The diff now owns model/widget teardown and detaches models before disposal. Reopening the same actual repair, changing views, remote comparison and mobile navigation passed without inference or page errors. Initial failure evidence remains available.
- **Remote exhaustion:** the negative probe must invoke Add to exercise an infinite `reduce` callback; an empty reset alone does not execute it. The actual probe now proves bounded error/timeout and environment cleanup. It never became an AI success.
- **Mobile diff and dependency review:** forced screen-reader mode prevented compact inline rendering for ordinary mobile viewers. Detected accessibility mode preserves screen-reader support and permits inline rendering; the browser regression checks the actual compact geometry. Locator assertions avoid unsafe evaluation under the unchanged strict release CSP. A patch override updates Monaco's pinned DOMPurify dependency to 3.4.17 after two low-severity advisories; final npm audit has zero findings.
- **Release packaging:** environment-provided root is resolved without eagerly evaluating a development path inside the minimal image. Health validates declared assets. Dependencies are pinned; actual image authority/resource checks and desktop/mobile acceptance cover the release image.

Live development evidence predates the final UI corrections. [Image/source binding](assets/milestone-04/live-engine-binding.json) records its actual image and source hashes, including four files differing from `fc918a6`. It is not falsely attributed to the final commit. The held-out protocol and final offline checks have their own exact identities. Final UI reopening demonstrates the corrected interaction with the saved model candidate; it does not claim fresh model inference at the final review head.

## 7. Limits and activation requirements

**Known release-blocking correctness/security defects:** none known for the stated read-only recorded release and bounded private live scope after the final checks. The private stack is not approved for public hostile-code execution.

Dependency checks cover the built frontend and pinned minimal public Python image. The first npm audit found two low-severity sanitizer/editor advisories; the sanitizer patch override removes those findings without replacing Monaco. Initial and final audit records are retained. This is an advisory-database check, not proof of absence of vulnerabilities.

**Public activation blocker:** no authorized hosting destination/TLS origin was supplied. Owner authorization must identify one, deploy only the recorded image, enable secure cookies, retain tested limits and rerun health/recorded-browser acceptance at that origin. There is no public URL. This is an explicit activation dependency, not a claimed deployment.

**Nonblocking limitations:** eight related synthetic held-out defects cannot establish general repair accuracy; whole context fits and performs equally well. Finite checks are not proof of correctness. Provider dollar pricing is unverified. Exact frozen image reuse requires retained local images or a newly versioned replication. Native Chromium/OS/Docker exploit resistance and public live execution are unproven. Local historical artifact retention is manual; Monaco's lazy editor bundle remains large. No arbitrary repositories, uploads, shell commands, autonomous publication or broad repair platform was built.

## 8. GitHub references and final review

- Private repository: https://github.com/kabbersokhi-boop/ai-debugging-workbench.
- Branch: `milestone/04-release-readiness`.
- Base: accepted `milestone/03-verified-repair`, `0c2dc0348d1b0b3f961466f214884e53c21bc14d`; PR #3 remains unmerged.
- Tested release implementation: [`d60344756baf75ae43152c7f1547b8db69d78522`](https://github.com/kabbersokhi-boop/ai-debugging-workbench/commit/d60344756baf75ae43152c7f1547b8db69d78522).
- Frozen experiment implementation/configuration: `78989e3`; original scenario sources: `9e8668b`.
- Review PR: https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/4.
- Final review head: [`review/milestone-04`](https://github.com/kabbersokhi-boop/ai-debugging-workbench/tree/review/milestone-04), a tag pointing to the final report/evidence commit. Exact SHA is in the PR delivery summary.
- Report: `docs/reports/MILESTONE-04.md`.
- Source tour: [critical code map](../CODE_TOUR.md), [architecture](../ARCHITECTURE.md), [decisions](../DECISIONS.md), [results](../RESULTS.md), [walkthrough provenance](../demo/README.md).

Ready for final owner review. No PR was merged, no code/repository was published, and no additional milestone was started.

## 9. Final-review correction — guest resource authorization

**Root cause:** authorization recognized resource IDs with a narrow lowercase UUID regex. Alternate spellings accepted by the installed FastAPI/Pydantic validator skipped ownership checks. The new actual-application/PostgreSQL test reproduced HTTP 200 for a synthetic foreign uppercase run ID before the fix; [original failing regression](assets/milestone-04/guest-auth/m4-auth-before-fix.txt).

**Fix:** identify the protected resource namespace first, parse its UUID, and require its canonical lowercase/hyphenated spelling. Malformed and noncanonical guest paths now return the same 404 before handlers. Canonical IDs undergo the existing ownership check using the parsed UUID. Collection history filtering, snapshot/artifact ownership, expiry, quota reservations and trusted local mode retain their behavior. No schema change, volume reset, inference or frozen NVIDIA evaluation rerun was performed.

**Coverage:** two actual guest sessions and disposable PostgreSQL schemas; sixteen spellings across all sixteen current protected routes (512 guest resource requests). The matrix includes canonical, uppercase, mixed-case, hyphenless, uppercase hex, braces, URNs and malformed variants. Trusted-local requests probe the actual installed route validator: nine forms remain accepted there, seven rejected. Guest requests deny all 256 foreign accesses and all 240 noncanonical owner accesses; sixteen canonical owner paths succeed. Instrumented real handler entry and deterministic effect boundaries assert no unauthorized request reaches provider admission, cancellation/start, broker preview/remote controls or artifact handlers. Real database get/history and response serialization remain in use; only effectful coordinator operations and broker I/O use explicit offline fixtures. Root/nested history, evidence/patch downloads, screenshots, source ownership, expiry and atomic reservations are covered.

| Exact command | Actual result |
| --- | --- |
| `./scripts/e2e -k guest_uuid_spellings` before correction | 1 failed in 1.95 s: uppercase foreign UUID returned 200 |
| `./scripts/e2e -k 'guest_uuid_spellings or guest_ownership or reservations_are_atomic'` | 3 passed in 4.72 s |
| `./scripts/check` | Ruff/format passed; Pyright zero errors; 57 unit tests passed in 3.57 s; TypeScript/Vite build passed |
| `./scripts/e2e` | 48 passed, four explicit opt-in skips, 57 deselected in 223.15 s |
| `E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first` | 1 passed in 3.18 s; actual recorded container desktop/mobile, no live requests or page errors |
| `uv run --project backend python scripts/check_release.py` | Actual recorded container boundary checks passed; it still has no protected guest resource routes or execution authority |

The refreshed [desktop screenshot](assets/milestone-04/recorded-desktop.png) waits for both original `20000` and candidate `10000` shipping-threshold source lines to render in Monaco. No UI redesign was made. [Correction logs and preservation evidence](assets/milestone-04/guest-auth/) retain the before/after outcome, full checks and confirmation that all 32 frozen engine/scoring/source hashes and historical benchmark files remain unchanged.

- Reviewed original head: `f1865c07d32f3e4b113870a95e5f73e96c7461b3`; original `review/milestone-04` tag is retained.
- Tested correction implementation: [`e860ed65a5fed2aaadc0fcffaa823f8a32420fc0`](https://github.com/kabbersokhi-boop/ai-debugging-workbench/commit/e860ed65a5fed2aaadc0fcffaa823f8a32420fc0).
- Final correction review head: [`review/milestone-04-guest-auth`](https://github.com/kabbersokhi-boop/ai-debugging-workbench/tree/review/milestone-04-guest-auth), an immutable tag for the correction report/evidence commit. Its exact SHA and final-head CI run/outcome are recorded in the PR delivery summary.
- Existing [PR #4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/4), same `milestone/04-release-readiness` branch and base. [Final correction CI checks](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/4/checks) exercise the committed correction, full offline suite, crash recovery and recorded release checks; delivery waits for their outcome.

This correction supersedes the original submission's guest-authorization claim. Public hosting remains inactive, all PRs remain unmerged, and no additional milestone was started.
