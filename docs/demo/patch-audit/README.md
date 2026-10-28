# Patch Audit · the films

These films show the historical **v1.1.0 prepared-task workflow**. For the current v1.2.0 recorded
viewer, use the [current walkthrough and capture guide](CURRENT-DEMO.md).

One genuine retained patch passed 155 **selected** upstream tests but missed the required
standalone implementation. Independent checks exposed length one with empty keys/items.
A different retained patch fixes both implementations. Different generation procedures are
not a fair vendor comparison. The films make no new coding-model call.

| Film | With burned captions | Clean image | Complete subtitles | Transcript / finished cut |
| --- | --- | --- | --- | --- |
| Full end-to-end | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-full-captioned.mp4) | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-full.mp4) | [SRT](patch-audit-full.srt) · [VTT](patch-audit-full.vtt) | [Transcript](full-transcript.md) · [shot list](full-shot-list.md) |
| 60-second highlight | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-60s-captioned.mp4) | [MP4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-60s.mp4) | [SRT](patch-audit-60s.srt) · [VTT](patch-audit-60s.vtt) | [Transcript](short-transcript.md) · [shot list](short-shot-list.md) |

[Thumbnail](thumbnail.png) · [Public recorded product](https://ai-debugging-workbench-recorded.vercel.app/) ·
[QA and exact execution identities](../PATCH-AUDIT-DEMO-PRODUCTION.md) ·
[Raw capture and reproduction material](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-demo-reproduction.tar.gz) ·
[Asset checksums](https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/patch-audit-demo.sha256).

Both films are 1920×1080, 30 fps, H.264/yuv420p MP4 with stereo AAC narration.
Release assets are public direct MP4 downloads; browser behavior may be playback or download.
No login is needed. The public application displays historical evidence; fresh execution is local.

## Reproduce the edit

System requirements: Python 3.12, the existing backend environment and Playwright Chromium,
FFmpeg with libx264/libass/drawtext, Fontconfig, Open Sans and DejaVu Sans Mono.
The tools environment is separate from product dependencies. Allow approximately 1 GB for
free local speech models/dependencies and several GB for intermediates; no GPU is required.

```sh
uv venv --python 3.12 artifacts/demo-production/tools/venv
uv pip install --python artifacts/demo-production/tools/venv/bin/python -r docs/demo/patch-audit/requirements-media.txt
```

Extract the reproduction archive **at the repository root**. It restores
`artifacts/demo-production/raw`, `narration`, `alignment`, and QA material. The final edit uses
its recorded video files, append-only audit UUIDs and exact relative timing in
[full-timeline.json](full-timeline.json) / [short-timeline.json](short-timeline.json).

```sh
backend/.venv/bin/python docs/demo/patch-audit/verify_evidence.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/render.py --kind full
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/render.py --kind short
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/support.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/qa.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/audio_qa.py
backend/.venv/bin/python docs/demo/patch-audit/playback_qa.py
```

The renderer builds visual clips, normalizes matched stereo narration in two EBU R128 passes,
limits peaks at 192 kHz with delay compensation, assembles the
clean version, writes complete SRT/VTT cues and burns a separate 1080p ASS caption track.
`--assemble-only` resumes audio/caption assembly only if every cached visual input still matches.
`--audio-only` remuxes a new narration track into both existing visual variants without re-encoding video.
Normalization and limiter settings are verified on the encoded AAC, rather than assumed from filter targets.
[FFmpeg filter reference](https://ffmpeg.org/ffmpeg-filters.html#loudnorm).
H.264 output may differ across FFmpeg/font versions; published checksums identify the actual films.

## Make a new authentic recording

This is optional; replaying the edit above makes **no new audit**. A new capture appends two fresh
local executions. Start the existing approved local stack, then use a new take directory (retain
prior captures). Capture refuses to overwrite its completed capture manifest.

```sh
docker compose up --build -d --wait api
backend/.venv/bin/python docs/demo/patch-audit/capture.py
backend/.venv/bin/python docs/demo/patch-audit/closeups.py
```

`capture.py` uses exact retained bytes, imports one declared copy, reviews, explicitly confirms,
runs the real incomplete and complete candidates, downloads and reopens evidence, then records
the real public site. `closeups.py` only reopens saved identities; it starts no execution.
A few unused coverage shots are retained alongside the finished-cut selections.
No response interception, substituted results or semantic DOM changes are used. CSS zoom,
font size, smooth scrolling, read-only cursor navigation and editorial camera pushes aid readability.
The empty-input close-up enlarges two crops of the original UI pixels after first showing the full observation.
Actual UI shows one overall running state. The separate **capture timeline** annotation derives
ordinary/independent phase timing from the actual saved execution, not invented UI progress.
Accelerated execution segments state their exact playback factor; full raw recordings remain.

## Regenerate narration / audio QA

Download the two assets from the [official Kokoro ONNX model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)
into `artifacts/demo-production/tools/` and verify these SHA-256 values:

- `kokoro-v1.0.onnx`: `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a`
- `voices-v1.0.bin`: `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`

```sh
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/narrate.py --audition
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/narrate.py
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/align.py
```

`story.json` is the complete finished narration. Sentence synthesis supplies exact sentence timing;
local Whisper supplies word anchors for caption splits and checks intelligibility. The approved
text supplies every caption word. ASR never narrates or scores the candidate. `av==16.1.0` is
pinned because PyAV 19 removed an argument used by faster-whisper 1.2.1.

Narration: Kokoro-82M `af_heart`, synthesized on CPU via kokoro-onnx 0.6.0 at speed 0.97.
[Model Apache-2.0 declaration](https://huggingface.co/hexgrad/Kokoro-82M) ·
[wrapper MIT license](https://github.com/thewh1teagle/kokoro-onnx/blob/main/LICENSE).
Audio QA uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with the local `base.en`
model. No music, stock imagery, paid API, voice impersonation or exclusive voice ownership claim.
Typography uses installed Open Sans and DejaVu; font files and speech weights are not redistributed.
Original Boltons source and upstream copyright attribution remain in the retained evidence.

## Product verification

`./scripts/check` and `docs/demo/patch-audit/verify-product.sh` run the existing checks.
The latter uses separate local Compose volumes/ports and explicitly disables live-provider opt-ins.
The owner stack must be idle: evaluator cleanup labels span projects. It tears down only its own
Compose project and retains its volumes. CI runs the unchanged credential-free product suite;
media synthesis/encoding is a separate reproducible local procedure.

`verify_public.py` checks anonymous release downloads against local SHA-256 digests and MP4 byte ranges.
`playback_qa.py --public` plays the published streams in a fresh context.

`package.py` builds a sanitized, deterministic reproduction archive after local/public QA.
It requires matching final media hashes and all four public playback records; speech weights,
tool environments and intermediate encoded clips are excluded.
