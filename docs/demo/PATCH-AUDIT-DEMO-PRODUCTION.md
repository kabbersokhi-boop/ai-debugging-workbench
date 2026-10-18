# Patch Audit · demo production

## Watch

| Film | Runtime | Burned captions | Clean image |
| --- | --- | --- | --- |
| End-to-end | 5:43.933 | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-full-captioned.mp4) | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-full.mp4) |
| Highlight | 1:00.733 | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-60s-captioned.mp4) | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-60s.mp4) |

All four files: 1920×1080, 16:9, 30 fps, H.264/yuv420p, stereo AAC at 48 kHz.
[Thumbnail](patch-audit/thumbnail.png) · [Complete SRT/VTT, transcripts and actual shot lists](patch-audit/README.md) ·
[Public recorded application](https://ai-debugging-workbench-recorded.vercel.app/).
Direct MP4 links need no authentication; browsers may play or download them.

## What the films show

**155 selected upstream tests passed; one genuine repair remained incomplete.** The full
24-shot film follows the original Boltons requirement, exact retained patch, local import and
provenance declaration, diff review, explicit execution confirmation, actual checks, empty-input
failure, complete correction, saved/downloaded evidence, history reopening, and public browsing.
The six-shot highlight edits the same real captures. No coding model was called for production.

The incomplete patch fixes `dictutils.py` but misses the required standalone `urlutils.py` copy.
Empty input leaves length **1**, while keys/items are empty; expected length is **0**. Five related
failed standalone groups describe **one incomplete repair**. The alternative retained genuine patch
fixes both copies and passes all 15 independent groups. Different generation procedures prevent a
fair vendor comparison. M1's zero extra discoveries and the frozen M2 comparison remain intact.

### Exact filmed executions

Filmed product source: `e1e611b13468d74581cd10d5778b459ef3dfdd6e`; released runtime source:
`c3bb3df5d6727ec36b837c3510f70ff60b1d41ae`. Both fresh local audits use Boltons base
`d45cc414e33aa4e08a73e0993574df4397e2e9db` and the existing trusted admission/verification path.

| | Incomplete repair | Complete correction |
| --- | --- | --- |
| Fresh audit UUID | `d1435cca-259e-4ea8-986d-4d08ecacb96b` | `f5f1ebb3-88c4-4adb-abb6-09f93aba5eb5` |
| Candidate SHA-256 | `5cab12b5c1b25239d4418e84aae45f166041390a6895d24f2a6ae1d1d85d6246` | `ad55f9039233a94d71447bbf043e94537de73ca0aa7d2b5174b9753abcb90f29` |
| Historical source | `m02-v2-development-boltons-addlist-nemotron3-r02` | `m02-v1-boltons-addlist-nemotron35-r02` |
| Filmed provenance | Imported exact bytes; **user declared** | **Retained model** record |
| Selected ordinary checks | 155 passed | 155 passed |
| Independent procedure | Failed behavioral comparison | All 15 groups passed |

Local scenes are newly executed audits of unchanged historical patch bytes, not live model
generation. The final public scenes show the actual Vercel **recorded-only** application and its
two curated historical results. Supplemental code/evidence takes only reopen saved results.
Raw continuous takes, camera-origin maps, phase timestamps, exact patches, downloads, Docker
events and validated envelopes are in the [reproduction archive](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-demo-reproduction.tar.gz).

## Production and reproduction

[Scripts and commands](patch-audit/README.md) · [Full finished cut](patch-audit/full-shot-list.md) ·
[Highlight finished cut](patch-audit/short-shot-list.md).
Playwright captures real application behavior; FFmpeg edits authentic footage, aspect-preserving
camera pushes, explicit accelerated segments, restrained titles and separate complete subtitle tracks.
The empty-input close-up enlarges original expected/observed UI pixels after showing their context.
The product displays one overall running state. An editorial **capture timeline** uses saved phase
timestamps; it is not a fabricated application progress indicator. Raw execution segments compressed
at 2.39× / 1.18× are labeled on screen and retained uncut.

Narration uses local Kokoro-82M `af_heart`, speed 0.97; no music or paid API. Local Whisper supplies
word anchors; every caption word comes from the complete approved narration. Python 3.12.13,
Playwright 1.58, FFmpeg n9.0.1, pinned media dependencies and model/font digests are recorded.
Two-pass matched-stereo normalization plus oversampled peak limiting is checked after AAC encoding.

```sh
./scripts/check
docs/demo/patch-audit/verify-product.sh
backend/.venv/bin/python docs/demo/patch-audit/verify_evidence.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/qa.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/audio_qa.py
backend/.venv/bin/python docs/demo/patch-audit/playback_qa.py
backend/.venv/bin/python docs/demo/patch-audit/playback_qa.py --public
```

## Verification and publication

- Product: **124 offline tests passed**, lint, formatting, typing and frontend build passed.
  The isolated, unchanged acceptance suite passed **67 tests, 4 opt-in skips**; the two unauthenticated
  public recorded browser journeys also passed. An earlier run during encoding had one 5-second
  initial review-region visibility timeout (66 passed, 4 skipped). That failure is retained; the quiet
  rerun changed no test, timeout, candidate, verifier or product code.
- Both saved audit envelopes and exact patch bytes pass the existing admission, verifier and envelope
  validators. Probe process exit status is distinct from a behavioral comparison result.
- Final media: every frame decoded; stream dimensions/rate/codecs, duration, blank/black-frame guards,
  encoded loudness/true peaks, complete caption text and synchronized per-shot audio checked.
  Clean and captioned audio decode identically; no narration is truncated. Scene content, both sides
  of every cut, evidence-zoom boundaries and endings reviewed from actual rendered frames, with
  critical evidence also inspected at 1080p and a 960-pixel playback width.
- Fresh Chromium contexts play, seek and reach the end of all four local and public MP4s with audio
  decoding, at desktop and small sizes. Public asset bytes/checksums are checked without credentials.
  Detailed observations, frames and reports accompany the reproduction archive.
- Draft QA caught an early evidence crop and an AAC true-peak overshoot. Both were corrected before
  publication; audio remuxing preserved all four encoded H.264 streams exactly. Failed attempts are
  documented rather than counted as final passes. Caption validation joins legal line wraps after
  hyphens before exact transcript comparison; the original check flagged two such wraps, not missing words.
- Privacy: fresh browser contexts; no private account pages or credentials in footage. Secret scans
  cover production sources and retained raw material. Archive metadata and test paths are sanitized.
  No stock imagery/music; model/wrapper licenses and exact assets are linked in the production guide.

The [publication record](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-demo-publication.json)
records the exact demo PR, reviewed head, final merge commit, CI URLs, final media digests and
preservation checks. [Checksums](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-demo.sha256)
cover added media and reproduction material. The existing v1.1.0 tag, original notes and two evidence
assets are retained. This change adds documentation/media only; no app deployment is required.

## Limits

Audio QA uses ASR, waveform synchronization, encoded loudness/peaks and native playback/decoding;
**no human listening review is claimed**. Frame sampling plus every-frame decoding/blank guards is
not an assertion that every frame was manually inspected. Speech is synthetic; proper names may
sound unfamiliar. Encoding/font versions can change regenerated pixels; checksums identify the
published files. The archived captures reproduce the edit without re-running an audit; a new
capture creates new audit IDs and requires the approved local stack.

These finite checks do not prove universal correctness or security. Restricted containers and
in-process Python observations are **not a complete anti-tampering boundary** against malicious
candidates. The public site cannot execute patches. No additional experiment, general repository
support, model ranking, new product milestone or privileged public endpoint is implied.
