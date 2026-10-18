"""Read-only supplementary camera takes. Reuses saved identities; starts no audits."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, expect
from capture import BASE, PUBLIC, WORK, RAW, Camera, focus_diff

async def main():
    capture=json.loads((RAW/'capture.json').read_text())
    if (RAW/'closeups-shots.json').exists():raise SystemExit('Retain the previous closeup take before recording again.')
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(viewport={'width':1440,'height':660},record_video_dir=str(RAW/'closeups'),record_video_size={'width':1440,'height':660},locale='en-GB',timezone_id='UTC')
        page=await context.new_page();cam=Camera(page,'closeups')
        async def open_url(url):
            await page.goto(url,wait_until='networkidle')
            await expect(page.get_by_role('heading',name='Patch Audit',exact=True)).to_be_visible()
            await page.evaluate("document.documentElement.style.zoom='1.4'")
        await open_url(BASE+'/?candidate='+capture['imported_candidate']['id'])
        await cam.click(page.get_by_text('Open code comparison · boltons/dictutils.py',exact=True))
        await expect(page.locator('.monaco-diff-editor:visible')).to_be_visible()
        await cam.aim(page.get_by_text('Open code comparison · boltons/dictutils.py',exact=True))
        await focus_diff(page,235)
        await cam.shot('review')
        await open_url(BASE+'/?audit='+capture['incomplete_id'])
        await cam.click(page.get_by_text('Inspect the omitted standalone file · boltons/urlutils.py',exact=True))
        await cam.aim(page.get_by_text('Inspect the omitted standalone file · boltons/urlutils.py',exact=True))
        await page.locator('.audit-case pre').evaluate('''el=>{const node=el.firstChild;const i=node.textContent.indexOf('    def addlist(');const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+15);el.scrollTop+=(r.getBoundingClientRect().top-el.getBoundingClientRect().top)/parseFloat(document.documentElement.style.zoom)-20;}''')
        await cam.shot('cause')
        await open_url(BASE+'/?candidate='+capture['complete']['candidate_id'])
        await cam.click(page.get_by_text('Open code comparison · boltons/urlutils.py',exact=True))
        await expect(page.locator('.monaco-diff-editor:visible')).to_be_visible()
        await cam.aim(page.get_by_text('Open code comparison · boltons/urlutils.py',exact=True))
        await focus_diff(page,1134)
        await cam.shot('complete_diff')
        video=page.video;await context.close()
        capture['closeups_video']=str(Path(await video.path()).relative_to(WORK));capture['closeups_zero_epoch']=cam.epoch_zero
        context=await browser.new_context(viewport={'width':1440,'height':660},record_video_dir=str(RAW/'public-closeup'),record_video_size={'width':1440,'height':660},locale='en-GB',timezone_id='UTC')
        page=await context.new_page();cam=Camera(page,'public-closeup')
        await open_url(PUBLIC)
        await expect(page.get_by_text('RECORDED EVIDENCE · NO EXECUTION',exact=True)).to_be_visible()
        await cam.aim(page.locator('.evaluation-intro'))
        await cam.shot('public')
        await cam.shot('close')
        video=page.video;await context.close()
        capture['public-closeup_video']=str(Path(await video.path()).relative_to(WORK));capture['public-closeup_zero_epoch']=cam.epoch_zero
        await browser.close()
    capture['camera_origins']=['local','public','closeups','public-closeup']
    (RAW/'capture-with-closeups.json').write_text(json.dumps(capture,indent=2)+'\n')
    print('Read-only closeups complete',flush=True)

if __name__=='__main__':asyncio.run(main())
