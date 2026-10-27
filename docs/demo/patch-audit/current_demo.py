"""Produce the current demo from real read-only browser interactions and local speech.

Run narrate/render in the existing media tools environment; capture uses Playwright.
The recorded service is required. No patch is admitted, approved, or executed here.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "artifacts/public-presentation"
MEDIA = ROOT / "frontend/public/demo/patch-audit"
STORY_PATH = Path(__file__).with_name("current-story.json")
STORY = json.loads(STORY_PATH.read_text())
MISSED = "m02-v2-development-boltons-addlist-nemotron3-r02"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def narrate() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    from kokoro_onnx import Kokoro

    model_dir = ROOT / "artifacts/demo-production/tools"
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_dir / "kokoro-v1.0.onnx"), options, providers=["CPUExecutionProvider"]
    )
    voice = Kokoro.from_session(session, str(model_dir / "voices-v1.0.bin"))
    WORK.mkdir(parents=True, exist_ok=True)
    for scene in STORY:
        chunks, timings, cursor = [], [], 0.0
        for line in scene["lines"]:
            sound, rate = voice.create(line, voice="af_heart", speed=0.98, lang="en-us")
            timings.append(
                {"text": line, "start": cursor, "end": cursor + len(sound) / rate}
            )
            gap = np.zeros(round(rate * 0.24), dtype=np.float32)
            chunks.extend([sound, gap])
            cursor += (len(sound) + len(gap)) / rate
        sf.write(
            WORK / f"{scene['id']}.wav", np.concatenate(chunks), rate, subtype="PCM_16"
        )
        (WORK / f"{scene['id']}.json").write_text(
            json.dumps({"duration": cursor, "lines": timings}, indent=2)
        )
        print(scene["id"], round(cursor, 2), flush=True)


async def capture(base: str) -> None:
    from playwright.async_api import async_playwright, expect

    WORK.mkdir(parents=True, exist_ok=True)
    if (WORK / "capture.json").exists():
        raise RuntimeError(
            "Keep the existing capture; select a fresh WORK directory for another take."
        )
    errors, mutations, events = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 810},
            record_video_dir=str(WORK),
            record_video_size={"width": 1440, "height": 810},
            reduced_motion="reduce",
        )
        start = time.monotonic()
        page = await context.new_page()
        video = page.video
        page.on("pageerror", lambda e: errors.append(str(e)))
        # The final scene opens GitHub's real quickstart, whose own analytics may POST.
        # Audit authority is measured on the recorded service origin throughout capture.
        page.on(
            "request",
            lambda r: (
                mutations.append(r.url)
                if r.url.startswith(base + "/") and r.method not in ("GET", "HEAD")
                else None
            ),
        )
        await page.goto(base + "/?recordedAudit=" + MISSED, wait_until="networkidle")
        region = page.get_by_label("Patch audit result", exact=True)
        await expect(region.get_by_role("status")).to_have_text("failed")
        # Presentation-only zoom changes layout, never content or responses.
        await page.evaluate("document.documentElement.style.zoom = '1.1'")
        for scene in STORY:
            key = scene["id"]
            if key == "hook":
                await page.evaluate("scrollTo(0, 0)")
            elif key == "ordinary":
                await page.get_by_role(
                    "link", name="Explore the real missed fix", exact=True
                ).click()
                await expect(region.get_by_role("status")).to_have_text("failed")
                await page.evaluate("document.documentElement.style.zoom = '1.1'")
                ordinary = region.locator("article").filter(
                    has=page.get_by_role(
                        "heading", name="Ordinary repository checks", exact=True
                    )
                )
                await ordinary.get_by_text("Execution logs", exact=True).click()
                await expect(ordinary).to_contain_text("155 passed")
                await ordinary.scroll_into_view_if_needed()
            elif key == "requirement":
                await page.get_by_text(
                    "Problem, explicit requirement and pinned source", exact=True
                ).click()
                await (
                    page.get_by_text(
                        "Problem, explicit requirement and pinned source", exact=True
                    )
                    .locator("..")
                    .scroll_into_view_if_needed()
                )
            elif key == "patch":
                await page.get_by_text(
                    "Problem, explicit requirement and pinned source", exact=True
                ).click()
                review = page.get_by_label("Candidate review", exact=True)
                await review.locator(".evaluation-patch").scroll_into_view_if_needed()
            elif key == "omitted":
                summary = page.get_by_text(
                    "Inspect the omitted standalone file · boltons/urlutils.py",
                    exact=True,
                )
                await summary.click()
                code = summary.locator("..").locator("pre")
                await code.scroll_into_view_if_needed()
                await code.evaluate("""el => {
                  const index = el.textContent.indexOf('    def addlist(');
                  if (index < 0) throw new Error('Missing original addlist');
                  const range = document.createRange();
                  range.setStart(el.firstChild, index); range.setEnd(el.firstChild, index + 1);
                  const zoom = el.getBoundingClientRect().width / el.offsetWidth;
                  el.scrollTop += (range.getBoundingClientRect().top - el.getBoundingClientRect().top) / zoom - 20;
                }""")
            elif key == "observation":
                await page.get_by_text(
                    "Inspect the omitted standalone file · boltons/urlutils.py",
                    exact=True,
                ).click()
                await page.get_by_text(
                    "Detailed behavioral observations · 15", exact=True
                ).click()
                check = page.get_by_text(
                    "failed · standalone_urlutils:empty", exact=True
                )
                await check.click()
                await check.locator("..").evaluate(
                    "el => el.scrollIntoView({block: 'center'})"
                )
            elif key == "evidence":
                async with page.expect_download() as result:
                    await page.get_by_role(
                        "link", name="Download audit evidence", exact=True
                    ).click()
                download = await result.value
                path = await download.path()
                saved = json.loads(Path(path).read_text())
                assert saved["id"] == MISSED and saved["execution_mode"] == "recorded"
                assert saved == json.loads(
                    (ROOT / "recordings/patch-audit-missed.json").read_text()
                )
                async with page.expect_download() as patch:
                    await page.get_by_role(
                        "link", name="Download exact patch", exact=True
                    ).click()
                patch_path = await (await patch.value).path()
                original = (
                    ROOT
                    / "evaluation/experiments/m02-v2/development/independent"
                    / (MISSED + ".patch")
                )
                assert Path(patch_path).read_bytes() == original.read_bytes()
                await page.get_by_text(
                    "Execution identities and reproduction", exact=True
                ).click()
                await (
                    page.get_by_text(
                        "Execution identities and reproduction", exact=True
                    )
                    .locator("..")
                    .scroll_into_view_if_needed()
                )
            elif key == "limits":
                await page.get_by_label(
                    "Evidence provenance", exact=True
                ).scroll_into_view_if_needed()
            elif key == "local":
                link = page.get_by_role("link", name="Run an audit locally", exact=True)
                await link.scroll_into_view_if_needed()
                await link.click()
                await page.wait_for_load_state("networkidle")
                await page.get_by_role(
                    "heading", name="Start the private local application", exact=True
                ).scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            metadata = json.loads((WORK / f"{key}.json").read_text())
            event = {
                "id": key,
                "audio_start": time.monotonic() - start,
                "duration": metadata["duration"],
            }
            events.append(event)
            await page.screenshot(path=str(WORK / f"{key}.png"))
            await page.wait_for_timeout((metadata["duration"] + 0.65) * 1000)
        end = time.monotonic() - start
        await context.close()
        assert video is not None
        await video.save_as(str(WORK / "raw.webm"))
        await browser.close()
    assert not errors and not mutations, (errors, mutations)
    capture_info = {
        "base_url": base,
        "record": MISSED,
        "fresh_execution": False,
        "events": events,
        "duration": end,
        "page_errors": errors,
        "mutation_requests": mutations,
        "recording_sha256": digest(ROOT / "recordings/patch-audit-missed.json"),
        "story_sha256": digest(STORY_PATH),
        "raw_sha256": digest(WORK / "raw.webm"),
        "frontend_sources": {
            f: digest(ROOT / f)
            for f in [
                "frontend/src/AuditGuide.tsx",
                "frontend/src/PatchAudit.tsx",
                "frontend/src/patchAudit.css",
            ]
        },
    }
    (WORK / "capture.json").write_text(json.dumps(capture_info, indent=2) + "\n")
    print("Captured authentic playback; no mutations or page errors.")


def stamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    return (
        f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"
    )


def ass_stamp(seconds: float) -> str:
    cs = round(seconds * 100)
    return f"{cs // 360000:01}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def render() -> None:
    import numpy as np
    import soundfile as sf

    capture_info = json.loads((WORK / "capture.json").read_text())
    assert capture_info["raw_sha256"] == digest(WORK / "raw.webm")
    assert capture_info["story_sha256"] == digest(STORY_PATH)
    lead = capture_info["events"][0]["audio_start"]
    duration = capture_info["duration"] - lead
    rate = 24000
    sound = np.zeros(round(duration * rate), dtype=np.float32)
    vtt = ["WEBVTT", ""]
    ass = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1440",
        "PlayResY: 900",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,DejaVu Sans,26,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,50,50,12,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    transcript = [
        "Patch Audit: 155 tests passed. The fix was incomplete.",
        "",
        "Actual saved evidence in the v1.2.0 recorded viewer. No fresh audit or model evaluation.",
        "",
    ]
    for scene, event in zip(STORY, capture_info["events"], strict=True):
        clip, clip_rate = sf.read(WORK / f"{scene['id']}.wav")
        assert clip_rate == rate
        offset = event["audio_start"] - lead
        first = round(offset * rate)
        sound[first : first + len(clip)] += clip[: len(sound) - first]
        meta = json.loads((WORK / f"{scene['id']}.json").read_text())
        for line in meta["lines"]:
            begin, end = offset + line["start"], offset + line["end"]
            vtt += [
                f"{stamp(begin)} --> {stamp(end)}",
                textwrap.fill(line["text"], width=80),
                "",
            ]
            wrapped = "\\N".join(textwrap.wrap(line["text"], width=85))
            ass.append(
                f"Dialogue: 0,{ass_stamp(begin)},{ass_stamp(end)},Default,,0,0,0,,{wrapped}"
            )
            transcript.append(f"{stamp(begin)[:8]}  {line['text']}")
    MEDIA.mkdir(parents=True, exist_ok=True)
    (MEDIA / "captions.vtt").write_text("\n".join(vtt))
    (MEDIA / "transcript.txt").write_text("\n".join(transcript) + "\n")
    (WORK / "captions.ass").write_text("\n".join(ass) + "\n")
    sf.write(WORK / "narration.wav", sound, rate, subtype="PCM_16")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(lead),
            "-i",
            str(WORK / "raw.webm"),
            "-i",
            str(WORK / "narration.wav"),
            "-t",
            str(duration),
            "-vf",
            f"pad=iw:900:0:0:color=0x0b111c,ass={WORK / 'captions.ass'}",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(MEDIA / "walkthrough.mp4"),
        ],
        check=True,
    )
    # The existing public server serves static files through a Vercel Function.
    # Keep the full response below its documented 4.5 MB limit with headroom.
    if (MEDIA / "walkthrough.mp4").stat().st_size >= 4_000_000:
        raise RuntimeError(
            "Demo exceeds the 4 MB publication budget; review compression."
        )
    # Crop genuine result pixels; the added title identifies the walkthrough.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(WORK / "ordinary.png"),
            "-vf",
            (
                "crop=1300:600:69:195,pad=1300:710:0:110:color=0x0d1420,"
                "drawtext=font='DejaVu Sans':"
                "text='155 tests passed. The fix was incomplete.':fontsize=34:fontcolor=white:x=32:y=24,"
                "drawtext=font='DejaVu Sans':"
                "text='WATCH THE EVIDENCE WALKTHROUGH  /  PATCH AUDIT':fontsize=14:fontcolor=0xa7d9ca:x=32:y=75"
            ),
            "-frames:v",
            "1",
            str(MEDIA / "poster.png"),
        ],
        check=True,
    )
    manifest = {
        k: v for k, v in capture_info.items() if k not in ("events", "base_url")
    }
    manifest.update(
        {
            "duration_seconds": round(duration, 2),
            "voice": "Kokoro-82M af_heart, local CPU speech",
            "assets": {
                f: digest(MEDIA / f)
                for f in [
                    "walkthrough.mp4",
                    "poster.png",
                    "captions.vtt",
                    "transcript.txt",
                ]
            },
            "scenes": [
                {"id": e["id"], "start": round(e["audio_start"] - lead, 2)}
                for e in capture_info["events"]
            ],
        }
    )
    Path(__file__).with_name("current-capture.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        "Rendered", round(duration, 2), "seconds with narration and visible captions."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["narrate", "capture", "render"])
    parser.add_argument("--base-url", default="http://127.0.0.1:18020")
    parser.add_argument("--work-dir", type=Path, default=WORK)
    args = parser.parse_args()
    WORK = args.work_dir.resolve()
    if args.action == "capture":
        asyncio.run(capture(args.base_url.rstrip("/")))
    else:
        globals()[args.action]()
