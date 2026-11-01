# Patch Audit: unfamiliar-developer session

This is a protocol and blank observation record for Phase 5. No participant sessions
or usability outcomes have been recorded here. Automated journeys and authored controls
are engineering evidence, not participant observations.

Use the private local application and the [quickstart](PATCH-AUDIT-QUICKSTART.md).
Keep raw recordings, patches and session notes local. Public sharing and publication
remain separate decisions. Use a participant label rather than identifying information.

## Before the session

Record the application revision or worktree identity, environment, browser, viewport,
participant's relevant experience and prior familiarity with Patch Audit. Note whether
dependencies, Docker, runtime images and the stack were already prepared. Those facts
affect setup time. Ask the participant to describe what they expect the tool to do.

If recording, agree on it with the participant first. Keep secrets, account details and
unrelated windows out of the capture. Record actual interactions, including errors and
retries. Identify any edited excerpt as an excerpt when preparing a later demonstration.

## Tasks to read aloud

1. “Explore the saved Boltons example. Explain what passed, what failed, why it matters
   and whether you ran anything. Find the evidence you would use to inspect the result.”
2. “Use the quickstart to run a prepared Python or Node example locally. Review what
   will run, approve it when you understand it, and explain the result and its limits.”
3. “Save a reusable checklist and use it with another supported patch. Explain what
   carries over and what you must approve again. Export a report and reproduction
   material another developer could inspect.”
4. When supported: “Use the Python generated-check workflow. Explain the property,
   input domain, retained failing input, expected and actual behavior, and how to
   reproduce it. What does a passing result establish?”
5. Optional: “Try a change from your own project.” Record unsupported inputs and stop
   at the supported boundary. Preserve admission and exact execution approval checks.

Let the participant work without coaching. Record requests for help verbatim. If help
is needed, record exactly what was provided and mark that task assisted. Do not count an
assisted completion as an unassisted one. Failures and abandonment are valid outcomes.

## Timing and observations

Record timestamps from observation, not estimates reconstructed afterward. Leave unknown
values unknown. Report prerequisite installation separately from application setup:

| Event | Observed timestamp | Notes |
| --- | --- | --- |
| Prerequisite installation starts / finishes | | Include downloads and runtime builds |
| Task shown | | Start of application setup |
| First execution request accepted | | End setup; start audit wait |
| Terminal result visible | | End audit wait |
| Participant finishes interpretation and export | | End inspection |

Keep cancelled attempts, failed control validation, retries and help intervals visible.
For multiple attempts, record each interval rather than folding them into one successful
duration. State whether wall-clock timing includes interruptions.

| Observation | Evidence to record |
| --- | --- |
| Completion | Completed / assisted / abandoned / unsupported; task number |
| Understanding | Participant's own explanation and any mistaken inference |
| Confusion | Concrete screen/action, quotation, expectation and observed behavior |
| Failure | Visible outcome, exact input classification, audit ID and retained logs |
| Reproduction | Another person's attempt, identities checked, result and mismatch |
| Intervention | Help given, by whom, timestamp and resulting action |

Label evidence explicitly: saved historical playback, prepared example, authored
positive/negative control, participant observation, or participant's own change. A
prepared negative revealing its intended defect is not a newly discovered defect.

## Blank session record

- Participant label / experience / prior familiarity:
- Date / environment / app identity / prerequisite state:
- Tasks attempted and exact examples or source/patch identities:
- Observed timestamps, interruptions and per-attempt durations:
- Outcomes and participant explanations:
- Confusion, unsupported cases and failures:
- Assistance and its effect:
- Audit IDs, report/evidence locations and reproduction attempts:
- Recording location and participant agreement, if recorded:
- Candidate friction fix and evidence needed to verify it:

## After observation

Fix demonstrated friction, run relevant engineering checks, and observe the affected task
again where possible. Preserve the initial observation alongside the follow-up. Report
participant counts and individual outcomes; do not infer general usability from a small
sample or replace missing observations with automated timings.

Before claiming Phase 5 complete, retain an actual interaction recording, a readable
read-only evidence report and an independent explanation/reproduction attempt. Prepare
any social-post draft around those measured results and link to the corresponding
evidence. Publishing, uploading recordings, hosting reports and releasing software
require their separate decisions; a local export does not claim a public share exists.
