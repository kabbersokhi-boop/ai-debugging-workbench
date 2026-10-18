"""Record actual supported journeys. Requires local owner stack; never calls a model.

No network interception, response substitution, result changes, or application code edits.
CSS zoom and smooth scrolling are presentation adjustments only. Raw browser videos,
actual downloads, screenshots, action timing, and read-only Docker events are retained.
"""
import asyncio
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import docker
import httpx
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'artifacts/demo-production'
RAW = WORK / 'raw'
STORY = json.loads(Path(__file__).with_name('story.json').read_text())
UNITS = {u['id']: u for u in STORY['full']}
FAIL = 'm02-v2-development-boltons-addlist-nemotron3-r02'
PASS = 'm02-v1-boltons-addlist-nemotron35-r02'
BASE = 'http://127.0.0.1:8010'
PUBLIC = 'https://ai-debugging-workbench-recorded.vercel.app'

class Camera:
    def __init__(self, page, origin):
        self.page, self.origin = page, origin
        self.zero = time.monotonic()
        self.epoch_zero = time.time()
        self.shots, self.actions = [], []

    async def aim(self, locator, align='start'):
        await locator.evaluate('(el,align)=>el.scrollIntoView({behavior:"smooth",block:align})', align)
        await asyncio.sleep(.8)

    async def click(self, locator):
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        if box:
            await self.page.mouse.move(box['x']+min(24,box['width']/2), box['y']+box['height']/2, steps=16)
        await locator.click()
        self.actions.append({'at': time.monotonic()-self.zero, 'action': 'click', 'text': (await locator.inner_text())[:140]})
        await asyncio.sleep(.4)

    async def shot(self, key, action=None, minimum=19):
        started = time.monotonic()
        shot = {'id': key, 'start': started-self.zero, 'origin':self.origin, 'url':self.page.url}
        if action:
            await action()
        timing = WORK / 'narration' / (key+'.json')
        target = max(minimum, json.loads(timing.read_text())['duration']+1.2) if timing.exists() else minimum
        await asyncio.sleep(max(.8, target-(time.monotonic()-started)))
        shot['end'] = time.monotonic()-self.zero
        shot['url_end'] = self.page.url
        await self.page.screenshot(path=str(RAW / (key+'.png')))
        self.shots.append(shot)
        (RAW / (self.origin+'-shots.json')).write_text(json.dumps({'video_zero_epoch':self.epoch_zero, 'shots':self.shots,'actions':self.actions},indent=2)+'\n')
        print(self.origin,key,round(shot['end']-shot['start'],2),flush=True)

async def focus_diff(page,line):
    # Read-only cursor navigation; the minimal Monaco build has no Go to Line contribution.
    await page.locator('.monaco-diff-editor:visible .editor.modified').click(position={'x':250,'y':100})
    await page.keyboard.press('Control+Home')
    for _ in range(line):
        await page.keyboard.press('ArrowDown')
    await asyncio.sleep(.5)

async def main():
    RAW.mkdir(parents=True, exist_ok=True)
    if (RAW/'capture.json').exists():
        raise SystemExit('Capture is append-only. Move the complete prior take to a retained directory before recording another.')
    client = docker.from_env()
    stream = client.events(decode=True,filters={'label':'ai-debugging-workbench.evaluator','type':'container'})
    events = []
    def collect():
        try:
            for event in stream:
                # Events carry Docker names/IDs, no environment or coordinator configuration.
                events.append(event)
                (RAW/'docker-events.json').write_text(json.dumps(events,indent=2)+'\n')
        except Exception:
            pass  # stream is closed after capture
    observer = threading.Thread(target=collect,daemon=True)
    observer.start()
    records = {}
    async with httpx.AsyncClient(base_url=BASE,timeout=20) as api, async_playwright() as p:
        before = (await api.get('/api/patch-audits/runs')).json()
        browser = await p.chromium.launch()
        async def context(origin):
            c = await browser.new_context(viewport={'width':1440,'height':660},device_scale_factor=1,
                record_video_dir=str(RAW/origin),record_video_size={'width':1440,'height':660},
                locale='en-GB',timezone_id='UTC',color_scheme='dark',accept_downloads=True)
            page = await c.new_page()
            camera = Camera(page,origin)
            await page.goto(BASE if origin=='local' else PUBLIC,wait_until='networkidle')
            await expect(page.get_by_role('heading',name='Patch Audit',exact=True)).to_be_visible()
            # Real browser zoom, no synthetic result data or semantic DOM changes.
            await page.evaluate("document.documentElement.style.zoom='1.4'")
            await asyncio.sleep(1)
            return c,page,camera
        c,page,cam = await context('local')
        result = lambda: page.get_by_role('region',name='Patch audit result')
        review = lambda: page.get_by_role('region',name='Candidate review')
        async def task():
            await cam.click(page.get_by_text('Problem, explicit requirement and pinned source',exact=True))
            await cam.aim(page.get_by_text('Problem, explicit requirement and pinned source',exact=True))
        await cam.shot('task',task)
        await cam.shot('contract',lambda: cam.aim(page.locator('details.evaluation-panel').filter(has=page.get_by_text('Problem, explicit requirement and pinned source',exact=True))))
        await cam.shot('retained',lambda: cam.aim(review()))
        retained_fail = (await api.get('/api/patch-audits/examples/'+FAIL)).json()
        (RAW/'retained-incomplete.patch').write_text(retained_fail['patch'])
        async def imported():
            await cam.click(page.get_by_text('Import a completed patch · review before execution',exact=True))
            await cam.aim(page.get_by_text('Import a completed patch · review before execution',exact=True))
            await page.get_by_label('Plain-text patch file',exact=True).set_input_files(RAW/'retained-incomplete.patch')
            await expect(page.get_by_label('Unified diff',exact=True)).to_have_value(retained_fail['patch'])
            await asyncio.sleep(1)
            await page.get_by_label('Declared authorship').select_option('user_declared')
            await page.get_by_label('Optional producer label',exact=True).fill('Film import · retained incomplete patch')
            await page.get_by_label('Optional model or tool',exact=True).fill('NVIDIA retained output · declared import')
            await cam.aim(page.get_by_label('Declared authorship'))
            async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/patch-audits/candidates')) as response:
                await cam.click(page.get_by_role('button',name='Import for review',exact=True))
            candidate = await (await response.value).json()
            records['imported_candidate'] = candidate
            assert candidate['candidate_hash']==retained_fail['candidate_hash']
            assert len((await api.get('/api/patch-audits/runs')).json())==len(before), 'Import executed code'
            await cam.aim(review())
        await cam.shot('import',imported)
        await cam.shot('declaration',lambda: cam.aim(review()))
        async def diff():
            await cam.click(page.get_by_text('Open code comparison · boltons/dictutils.py',exact=True))
            await expect(page.locator('.monaco-diff-editor:visible')).to_be_visible(timeout=20000)
            await cam.aim(page.get_by_text('Open code comparison · boltons/dictutils.py',exact=True))
            await focus_diff(page,235)
        await cam.shot('review',diff)
        async def confirm():
            await cam.aim(page.locator('.audit-confirm'))
            await expect(page.get_by_role('button',name='Run fresh audit',exact=True)).to_be_disabled()
            await asyncio.sleep(2)
            await page.get_by_role('checkbox').check()
            await asyncio.sleep(1)
        await cam.shot('confirmation',confirm)
        async def run(expected,key):
            async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/patch-audits/runs')) as response:
                await cam.click(page.get_by_role('button',name='Run fresh audit',exact=True))
            audit = await (await response.value).json()
            records[key+'_id'] = audit['id']
            await cam.aim(result())
            await expect(result().get_by_role('status')).to_have_text(expected,timeout=90000)
            saved = (await api.get('/api/patch-audits/runs/'+audit['id'])).json()
            envelope = saved['evidence']['envelope']['result']
            assert envelope['ordinary']['outcome']=='passed'
            assert '155 passed' in envelope['ordinary']['stdout']
            assert envelope['independent']['outcome']==expected
            assert envelope['ordinary']['container_id']!=envelope['independent']['container_id']
            records[key] = saved
            (RAW/(key+'-audit.json')).write_text(json.dumps(saved,indent=2)+'\n')
        await cam.shot('start',lambda:run('failed','incomplete'),minimum=12)
        async def ordinary():
            await cam.click(result().get_by_text('Execution logs',exact=True).first)
            await cam.aim(result().locator('.evaluation-phases'))
        await cam.shot('ordinary',ordinary)
        async def contrast():
            await cam.click(result().get_by_text('Execution logs',exact=True).first)
            await cam.aim(result())
        await cam.shot('contrast',contrast)
        await cam.shot('hook',lambda:cam.aim(result()))
        await cam.shot('question',lambda:cam.aim(result()))
        await cam.shot('missed',lambda:cam.aim(page.locator('.audit-case')))
        async def cause():
            await cam.click(page.get_by_text('Inspect the omitted standalone file · boltons/urlutils.py',exact=True))
            omitted=page.locator('.audit-case pre')
            await cam.aim(page.get_by_text('Inspect the omitted standalone file · boltons/urlutils.py',exact=True))
            await omitted.evaluate('''el=>{const node=el.firstChild; const i=node.textContent.indexOf('    def addlist(');const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+15);el.scrollTop+=(r.getBoundingClientRect().top-el.getBoundingClientRect().top)/parseFloat(document.documentElement.style.zoom)-30;}''')
        await cam.shot('cause',cause)
        async def empty():
            await cam.click(page.get_by_text('Detailed behavioral observations · 15',exact=True))
            await cam.click(page.get_by_text('failed · standalone_urlutils:empty',exact=True))
            target=page.locator('.evaluation-observations details').filter(has=page.get_by_text('failed · standalone_urlutils:empty',exact=True))
            # Font and block position only; the original complete JSON is preserved.
            await target.locator('pre').evaluate_all("els=>els.forEach(el=>el.style.fontSize='15px')")
            await cam.aim(target)
        await cam.shot('empty',empty)
        await cam.shot('scope',lambda:cam.aim(page.locator('.evaluation-observations')))
        async def complete():
            await cam.aim(page.get_by_label('Retained candidate'))
            await page.get_by_label('Retained candidate').select_option(PASS)
            await expect(review()).to_contain_text('captured generation evidence')
            await cam.aim(review())
        await cam.shot('complete',complete)
        async def complete_diff():
            await cam.click(page.get_by_text('Open code comparison · boltons/urlutils.py',exact=True))
            await expect(page.locator('.monaco-diff-editor:visible')).to_be_visible(timeout=20000)
            await cam.aim(page.get_by_text('Open code comparison · boltons/urlutils.py',exact=True))
            await focus_diff(page,1134)
        await cam.shot('complete_diff',complete_diff)
        async def pass_run():
            await cam.aim(page.locator('.audit-confirm'))
            await page.get_by_role('checkbox').check()
            await asyncio.sleep(1)
            await run('passed','complete')
        await cam.shot('pass_run',pass_run,minimum=15)
        await cam.shot('pass',lambda:cam.aim(result()))
        async def identity():
            await cam.click(page.get_by_text('Execution identities and reproduction',exact=True))
            await cam.aim(page.get_by_text('Execution identities and reproduction',exact=True))
        await cam.shot('identity',identity)
        async def download():
            await cam.aim(page.get_by_role('link',name='Download exact patch',exact=True))
            for label,name in [('Download exact patch','complete-downloaded.patch'),('Download audit evidence','complete-downloaded.json')]:
                async with page.expect_download() as pending:
                    await cam.click(page.get_by_role('link',name=label,exact=True))
                await (await pending.value).save_as(RAW/name)
            assert json.loads((RAW/'complete-downloaded.json').read_text())==records['complete']
        await cam.shot('download',download)
        async def history():
            await cam.aim(page.get_by_role('heading',name='Saved audit history',exact=True))
            await cam.click(page.locator('.evaluation-history button').filter(has_text=records['incomplete_id'][:8]))
            await expect(result().get_by_role('status')).to_have_text('failed')
            await cam.aim(result())
            await asyncio.sleep(3)
            await page.reload(wait_until='networkidle')
            await page.evaluate("document.documentElement.style.zoom='1.4'")
            await expect(result().get_by_role('status')).to_have_text('failed')
            assert (await api.get('/api/patch-audits/runs/'+records['incomplete_id'])).json()==records['incomplete']
            await cam.aim(result())
        await cam.shot('history',history)
        local_video = page.video
        await c.close()
        records['local_video'] = str(Path(await local_video.path()).relative_to(WORK))
        records['local_zero_epoch'] = cam.epoch_zero
        c,page,cam = await context('public')
        result=lambda:page.get_by_role('region',name='Patch audit result')
        async def public():
            await expect(page.get_by_text('RECORDED EVIDENCE · NO EXECUTION',exact=True)).to_be_visible()
            await cam.aim(page.locator('.evaluation-intro'))
        await cam.shot('public',public)
        async def public_switch():
            await cam.aim(page.get_by_label('Saved patch audit'))
            await page.get_by_label('Saved patch audit').select_option(PASS)
            await expect(result().get_by_role('status')).to_have_text('passed')
            await cam.aim(result())
            await asyncio.sleep(5)
            await cam.aim(page.get_by_label('Saved patch audit'))
            await page.get_by_label('Saved patch audit').select_option(FAIL)
            await expect(result().get_by_role('status')).to_have_text('failed')
            await cam.aim(result())
        await cam.shot('public_switch',public_switch)
        await cam.shot('limits',lambda:cam.aim(result()))
        await cam.shot('close',lambda:cam.aim(page.get_by_role('heading',name='Patch Audit',exact=True)))
        public_video = page.video
        await c.close()
        records['public_video'] = str(Path(await public_video.path()).relative_to(WORK))
        records['public_zero_epoch'] = cam.epoch_zero
        await browser.close()
        after = (await api.get('/api/patch-audits/runs')).json()
        assert len(after)==len(before)+2
        records['new_audits']=2
        records['captured_at']=datetime.now(timezone.utc).isoformat()
        records['product_source']=os.popen('git rev-parse HEAD').read().strip()
        records['viewport']={'width':1440,'height':660,'css_zoom':1.4}
        records['before_audit_count']=len(before)
        records['after_audit_count']=len(after)
    stream.close()
    client.close()
    (RAW/'capture.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Capture complete',records['incomplete_id'],records['complete_id'],flush=True)

if __name__=='__main__':
    asyncio.run(main())
