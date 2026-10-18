"""Play real MP4 streams in Chromium at desktop and small sizes, without auth.

--public verifies release assets after publication using a fresh browser context.
The loopback page is a media QA player, separate from the product interface.
"""
import argparse
import asyncio
import functools
import http.server
import json
import re
import threading
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'artifacts/demo-production'
ASSETS='https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/'
FILES=['patch-audit-full.mp4','patch-audit-full-captioned.mp4','patch-audit-60s.mp4','patch-audit-60s-captioned.mp4']

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=Path(self.translate_path(self.path))
        header=self.headers.get('Range')
        if not header or path.name not in FILES or path.parent.resolve()!=(WORK/'finished').resolve():
            return super().do_GET()
        match=re.fullmatch(r'bytes=(\d+)-(\d*)',header)
        size=path.stat().st_size
        if not match:
            self.send_error(416);return
        start=int(match[1]);end=min(size-1,int(match[2]) if match[2] else size-1)
        if start> end:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
        self.send_response(206)
        self.send_header('Content-Type','video/mp4')
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1))
        self.end_headers()
        try:
            with path.open('rb') as source:
                source.seek(start);remaining=end-start+1
                while remaining:
                    block=source.read(min(65536,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
        except (BrokenPipeError,ConnectionResetError):pass

async def main(public,kind):
    qa=WORK/'qa';qa.mkdir(exist_ok=True)
    player=qa/'player.html'
    player.write_text('''<!doctype html><meta charset="utf-8"><title>Patch Audit media QA</title>
<style>body{margin:32px;background:#080e18;color:white;font:16px sans-serif}video{display:block;width:calc(100vw - 64px);max-width:1920px;height:auto}</style>
<video controls playsinline preload="auto"></video><script>
const names=['patch-audit-full.mp4','patch-audit-full-captioned.mp4','patch-audit-60s.mp4','patch-audit-60s-captioned.mp4'];
const q=new URLSearchParams(location.search),name=q.get('file');
if(!names.includes(name))throw Error('Unknown QA asset');
document.querySelector('video').src=(q.has('public')?'https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/':'../finished/')+name;
</script>''')
    handler=functools.partial(Quiet,directory=str(WORK))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',18888),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    rows=[]
    try:
      async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        context=await browser.new_context(viewport={'width':1984,'height':1200})
        names=[n for n in FILES if kind=='all' or ('full' if 'full' in n else 'short')==kind]
        for name in names:
          page=await context.new_page()
          suffix='&public=1' if public else ''
          await page.goto(f'http://127.0.0.1:18888/qa/player.html?file={name}{suffix}')
          await page.wait_for_function('document.querySelector("video").error||document.querySelector("video").readyState>=2',timeout=120000)
          assert not await page.locator('video').evaluate('v=>v.error?.message??null')
          async def stats():
            return await page.locator('video').evaluate('(v)=>({time:v.currentTime,duration:v.duration,width:v.videoWidth,height:v.videoHeight,frames:v.webkitDecodedFrameCount,audioBytes:v.webkitAudioDecodedByteCount??null,error:v.error?.message??null,ended:v.ended})')
          await page.locator('video').evaluate('v=>v.play()')
          await asyncio.sleep(2)
          first=await stats();assert first['time']>.8 and first['frames']>10 and not first['error'],first
          assert first['width']==1920 and first['height']==1080
          film_kind='full' if 'full' in name else 'short'
          timeline=json.loads((Path(__file__).with_name(film_kind+'-timeline.json')).read_text())
          target=next(u['at']+3 for u in timeline if u['source'] in ('empty','public')) if 'captioned' in name else first['duration']/2
          await page.locator('video').evaluate('(v,t)=>{v.pause();v.currentTime=t}',target)
          await page.wait_for_function('(t)=>Math.abs(document.querySelector("video").currentTime-t)<.1&&!document.querySelector("video").seeking',arg=target)
          tag=('public-' if public else 'local-')+name.removesuffix('.mp4')
          await page.locator('video').screenshot(path=str(qa/(tag+'-desktop.png')))
          await page.set_viewport_size({'width':1024,'height':660})
          await asyncio.sleep(.3)
          await page.locator('video').screenshot(path=str(qa/(tag+'-small.png')))
          await page.locator('video').evaluate('v=>{v.currentTime=v.duration-1.2;v.play()}')
          await page.wait_for_function('document.querySelector("video").ended',timeout=15000)
          last=await stats();assert not last['error'],last
          if last['audioBytes'] is not None:assert last['audioBytes']>0,last
          rows.append({'file':name,'public':public,'initial_playback':first,'ending_playback':last,'desktop':f'{tag}-desktop.png','small':f'{tag}-small.png','authenticated':False})
          print('played',name,'public' if public else 'local',flush=True)
          await page.close()
        await context.close();await browser.close()
    finally:
      server.shutdown();server.server_close()
    (qa/(('public-playback' if public else 'local-playback')+('' if kind=='all' else '-'+kind)+'.json')).write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--public',action='store_true');ap.add_argument('--kind',choices=['full','short','all'],default='all');a=ap.parse_args()
    asyncio.run(main(a.public,a.kind))
