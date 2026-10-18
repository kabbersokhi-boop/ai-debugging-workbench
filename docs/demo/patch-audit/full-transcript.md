# Patch Audit · Full end-to-end film

Narration synthesized locally with Kokoro-82M (`af_heart`). No new coding-model generation.

## 0:00 · 155 tests passed. The repair was incomplete.

An AI-generated patch passed one hundred and fifty-five selected upstream tests. But the repair was incomplete. Independent behavioral checks caught what those tests missed.

## 0:12 · A real task, on an exact upstream base

The task comes from Boltons, a Python utility library. Its ordered multi-dictionary must accept one-shot inputs without inconsistent state. Empty input must add nothing.

## 0:25 · A completed, genuine model patch

We begin with a genuine retained model output, backed by its captured generation evidence. It changes the main dictionary implementation. The requirement also covers a standalone copy in the URL utility module.

## 0:41 · Import for review. Execution comes later.

Here, I import the exact retained patch bytes through the supported local workflow. Importing checks the patch against the approved task source. It does not execute the candidate.

## 0:53 · Same code. A different provenance record.

The imported copy is labeled user-declared and unverified. Matching code does not recreate captured authorship evidence. Its software candidate identity stays the same; its provenance record is separate.

## 1:08 · Review the exact change

The patch materializes the input once, returns early when it is empty, then reuses those values. That is a sensible correction, but this change touches only the main implementation.

## 1:21 · An explicit execution decision

Before execution, the owner reviews this exact patch and explicitly authorizes the pinned task. The application supports four approved historical Python tasks. It does not accept arbitrary repositories or shell commands.

## 1:37 · A real audit, in restricted containers

Now the real audit starts. Ordinary tests run first, then independent behavioral checks, in separate restricted containers. The interface shows one running state until completed evidence is published.

## 1:52 · The selected ordinary suite passes

The ordinary log confirms one hundred and fifty-five tests passed. That is the selected upstream suite for this task, not a claim that every possible test passed.

## 2:03 · Ordinary: passed. Independent: failed.

Independent checks nevertheless fail. The audit retains both outcomes rather than reducing them to a single reassuring badge. The additional information is specific: the required standalone behavior is still broken.

## 2:19 · The repair stopped one file too soon

The main dictionary file was repaired. The standalone implementation in the URL utility file was left unchanged. Normal package imports use the repaired class; standalone mode still uses the missed copy.

## 2:34 · Length: 1. Keys: empty. Items: empty.

Here is the clearest observation: empty input should leave length zero. Instead, the standalone object reports length one, while its returned keys and items are empty. Its views of the same state disagree.

## 2:49 · An iterator can only be consumed once

An iterator is consumed by the first loop, so the second update sees nothing. An empty generator is truthy, creating a key before the method discovers there are no values.

## 3:01 · One incomplete repair, inspectable evidence

The detailed checks exercise several related cases. They describe one incomplete repair, not five distinct AI defects. This example is development evidence, not a general model accuracy statistic.

## 3:16 · Now inspect a genuine complete patch

Next, we load a different genuine retained patch. Its captured generation procedure differs, so these two examples are not a controlled vendor comparison. We are comparing their behavior on this named task.

## 3:30 · Both implementations receive the correction

This correction updates both the main and standalone implementations. Each materializes the input once, rejects an empty addition, and reuses the same values for both internal updates.

## 3:44 · Fresh execution of the complete patch

After review and explicit confirmation, we run a fresh local audit of that retained candidate. This is another execution of existing code, not a new model generation trial.

## 3:57 · Both named check sets pass

The complete patch passes the selected ordinary suite and all fifteen independent observation groups. That supports this task-specific conclusion. It does not establish universal correctness or security.

## 4:11 · Bind the outcome to the exact inputs

Behind each result are the exact candidate and source identities, verifier identity, runtime image, and execution details. The separate containers restrict execution; they are not a complete anti-tampering boundary for malicious code.

## 4:28 · Download the patch and the evidence

Download the exact patch and the complete audit evidence, including logs and expected-versus-observed behavior. The reproduction instructions use the supported local stack and require a new explicit execution confirmation.

## 4:44 · Saved history. The same saved result.

The audit also persists in history. Reopen its saved link and the same evidence is available again. A new execution gets a new audit identifier; it does not become another independent defect discovery.

## 4:59 · Public browsing, without public execution

Now we switch to the actual public showcase. Anyone can inspect the two selected historical audits without an AI API key, Docker access, or privileged code execution.

## 5:12 · Historical failure and passing example

The recorded banner matters. These are saved historical results, not fresh audits or animated execution. Both examples expose their exact patches and evidence. New patch import and execution remain in the local application.

## 5:29 · AI can write the patch. Check the evidence.

AI can write the patch. Patch Audit checks the evidence. Explore the public recorded showcase, or open the repository to reproduce the local workflow. The exact code and the limits are there to inspect.
