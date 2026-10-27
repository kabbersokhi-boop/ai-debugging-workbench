# Product demonstrations

## Current Patch Audit · v1.2.0 recorded viewer

[Watch the narrated walkthrough](../../frontend/public/demo/patch-audit/walkthrough.mp4) ·
[Captions](../../frontend/public/demo/patch-audit/captions.vtt) ·
[Transcript](../../frontend/public/demo/patch-audit/transcript.txt) ·
[Capture, reproduction and limitations](patch-audit/CURRENT-DEMO.md).

Actual read-only browser interactions open the retained Boltons result, ordinary logs, independent
requirement, exact patch, omitted implementation and behavioral observation. The recording then
downloads the evidence and opens the local quickstart. Narration and visible captions describe the
saved execution; the public viewer runs no candidate code.

## Earlier Patch Audit · v1.1.0 prepared-task workflow

[Watch the 60-second highlight](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-60s-captioned.mp4) ·
[Watch the full end-to-end demonstration](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-full-captioned.mp4) ·
[Films, captions, transcripts and production scripts](patch-audit/README.md) ·
[Production verification](PATCH-AUDIT-DEMO-PRODUCTION.md).

## Original debugger demonstration

### Captioned walkthrough

`walkthrough.mp4` shows reopening and interacting with the actual successful NVIDIA shipping repair recorded in `recordings/m4-shipping-success.json`. This walkthrough makes no new inference or repair call. Original and candidate are compared at quantity two, then saved evidence and mobile layout are inspected. Captions are burned in; `walkthrough.srt` supplies the text transcript.

The underlying live run reproduced the shipping defect, retrieved source, obtained a structured NVIDIA diagnosis, generated a model patch and passed twelve trusted checks. The initial live browser acceptance also caught a Monaco teardown error. That outcome is retained in the milestone evidence; this walkthrough was captured after the lifecycle correction, using the same saved repair. No proposal was manually corrected.

Source capture: Playwright's local saved-run browser test (`M4_SAVED_REOPEN=1 ./scripts/e2e -k m4_saved_shipping`). There is no recorded output masquerading as a new live run.
