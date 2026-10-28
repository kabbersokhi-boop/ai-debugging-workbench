# Current Patch Audit walkthrough

[Download the narrated, captioned film](../../../frontend/public/demo/patch-audit/walkthrough.mp4?raw=true) ·
[WebVTT captions](../../../frontend/public/demo/patch-audit/captions.vtt) ·
[Transcript](../../../frontend/public/demo/patch-audit/transcript.txt) ·
[Poster](../../../frontend/public/demo/patch-audit/poster.png).

The film shows real read-only browser interactions with a local build of the v1.2.0 recorded
application. It opens the authentic Boltons missed-copy record, the ordinary log showing 155
selected tests passed, the pinned task requirement, the exact patch, the omitted `addlist` method,
the `standalone_urlutils:empty` observation, evidence downloads and execution identities. It ends
with the separate G3 outcome and the real local quickstart on GitHub.

No patch is imported, approved, executed or generated during capture. The evidence download is
compared with the original recording, and the patch download is compared byte for byte with the
retained patch. The capture asserts zero mutation requests to the recorded service and zero page
errors. GitHub's own analytics on the final documentation page are outside that service-origin
assertion.

## How it was made

- Playwright records actual navigation, clicks, downloads and scrolling at 1440×810. CSS zoom of
  1.1 improves readability. There are no response substitutions, reconstructed controls or edited
  result text.
- The retained source panel is scrolled to its actual `addlist` method. Expected and observed JSON
  are opened in the real result UI.
- FFmpeg pads a dedicated caption band to 1440×900, adds narration and visible captions, then
  encodes H.264/yuv420p with AAC and fast-start metadata. No UI content is covered by the captions.
- The renderer enforces a **4,000,000-byte** media budget. The existing host serves static files
  through its recorded FastAPI Function; Vercel documents a
  [4.5 MB response limit](https://vercel.com/docs/errors/function_response_payload_too_large).
  Staying below the budget avoids relying on browser Range behavior to fit the response limit.
- The poster crops genuine result pixels and adds an editorial title. It does not add a product
  control or alter a result.
- Narration uses the existing local Kokoro-82M `af_heart` voice on CPU. No paid API, coding-model
  call, stock footage, music or voice impersonation is used. Speech asset licenses and pinned model
  hashes are documented in the [earlier media reproduction guide](README.md#regenerate-narration--audio-qa).

[current-story.json](current-story.json) is the complete narration.
[current-capture.json](current-capture.json) records scene timings, source/recording identities and
the final asset digests. Raw browser video, screenshots and speech intermediates remain locally in
`artifacts/public-presentation/`; they are not a new public release asset or an execution campaign.

## Reproduce

Use the media environment and FFmpeg/font prerequisites in the
[existing production guide](README.md#reproduce-the-edit). Start only the restricted recorded image
on loopback; the privileged local workbench is unnecessary:

```sh
COMPOSE_PROJECT_NAME=patch-audit-presentation-preview RECORDED_PORT=18020 \
  docker compose -f compose.release.yaml up --build -d --wait

artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/current_demo.py narrate
backend/.venv/bin/python docs/demo/patch-audit/current_demo.py capture --base-url http://127.0.0.1:18020
artifacts/demo-production/tools/venv/bin/python docs/demo/patch-audit/current_demo.py render
```

The capture refuses to replace an existing `capture.json`. Use `--work-dir` with a fresh directory
for each command to make another take. Capture needs outbound access for the real GitHub quickstart;
speech synthesis and rendering use local assets. Font and encoder versions can change the final
media bytes; the committed manifest identifies this particular cut.

The video demonstrates saved inspection and documented local setup. It does not show a fresh audit
or establish that a new user can author a correct specification unaided.
