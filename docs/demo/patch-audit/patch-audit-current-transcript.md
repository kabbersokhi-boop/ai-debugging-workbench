# Current Patch Audit walkthrough (73 seconds)

**Format:** silent screen recording with a WebVTT caption track. The capture shows the actual
v1.2.0 recorded-release application replaying the retained Boltons evidence. The cursor and scroll
movement are real browser interactions. It does not start an audit or execute code.

- **0:00** Patch Audit checks completed changes; public mode replays saved evidence.
- **0:05** Open the real saved Boltons example.
- **0:13** The selected ordinary test suite passed 155 tests.
- **0:21** Inspect the separate independent-check result.
- **0:29** The patch missed the standalone `urlutils.py` copy; empty input reported length one instead of zero. These observations describe one incomplete repair.
- **0:41** Inspect retained observations and exact patch. Playback does not rerun the patch.
- **0:57** New audits require the private local application and an explicit approval workflow.
- **1:03** The public viewer cannot import or execute a patch; use the linked local quickstart to try an audit.

[Captions](patch-audit-current.vtt) · [MP4](patch-audit-current.mp4) · [Poster](patch-audit-current-poster.png)

The walkthrough records a local preview of the released recorded-only application built from this
review branch. No user code was executed and no production deployment was made.
