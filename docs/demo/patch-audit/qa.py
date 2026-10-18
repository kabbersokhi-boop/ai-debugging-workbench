"""Decode every frame, inspect stream/audio metadata, export scene/boundary samples.

Machine checks support—not replace—visual review. Contact sheets and full-resolution
key frames are retained in the reproduction archive. No model credentials are used.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'artifacts/demo-production'
HERE=Path(__file__).resolve().parent
QA=WORK/'qa'
OUT=WORK/'finished'

def probe(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def ffmpeg(*args):
 return subprocess.run(['ffmpeg','-hide_banner',*map(str,args)],capture_output=True,text=True,check=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['full','short','all'],default='all');ap.add_argument('--frames-only',action='store_true',help='Export caption/scene review material without claiming stream validation');args=ap.parse_args()
 wanted={'full','short'} if args.kind=='all' else {args.kind}
 QA.mkdir(exist_ok=True)
 report={'files':{},'captions':{},'samples':[]}
 paths=[p for p in sorted(OUT.glob('*.mp4')) if ('full' if 'full' in p.name else 'short') in wanted]
 assert len(paths)==2*len(wanted),'Missing final video variant'
 for path in ([] if args.frames_only else paths):
  info=probe(path); v=next(s for s in info['streams'] if s['codec_type']=='video');a=next(s for s in info['streams'] if s['codec_type']=='audio')
  duration=float(info['format']['duration'])
  assert v['codec_name']=='h264' and v['pix_fmt']=='yuv420p'
  assert (v['width'],v['height'],v['r_frame_rate'])==(1920,1080,'30/1')
  assert a['codec_name']=='aac' and a['sample_rate']=='48000' and a['channels']==2
  assert (240<=duration<=360) if 'full' in path.name else (45<=duration<=75)
  decoded=ffmpeg('-v','error','-threads','2','-i',path,'-f','null','-')
  assert not decoded.stderr.strip(),decoded.stderr
  black=ffmpeg('-threads','2','-i',path,'-vf','blackdetect=d=0.15:pic_th=0.995:pix_th=0.015','-an','-f','null','-')
  black_events=[line for line in black.stderr.splitlines() if 'black_start:' in line]
  assert not black_events,black_events
  stats_path=QA/(path.stem+'-viewport-stats.txt')
  ffmpeg('-v','error','-threads','2','-i',path,'-vf',f'crop=1700:764:110:168,signalstats,metadata=print:file={stats_path}','-an','-f','null','-')
  viewport=[];current=None
  for line in stats_path.read_text().splitlines():
   if line.startswith('frame:'):
    if current:viewport.append(current)
    current={'seconds':float(line.split('pts_time:')[1])}
   elif current is not None and line.startswith('lavfi.signalstats.'):
    key,value=line.removeprefix('lavfi.signalstats.').split('=',1)
    if key in ('YMIN','YMAX','YLOW','YAVG'):current[key]=float(value)
  if current:viewport.append(current)
  blank=[v for v in viewport if v['YMAX']-v['YMIN']<8 or v['YLOW']>230]
  assert not blank,('Blank browser viewport requires visual review',path.name,blank[:8])
  loud=ffmpeg('-i',path,'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-')
  log=loud.stderr;loudness=json.JSONDecoder().raw_decode(log[log.rfind('{'):])[0]
  assert -17<=float(loudness['input_i'])<=-15
  assert float(loudness['input_tp'])<=-1
  report['files'][path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'duration_seconds':duration,'video':{k:v.get(k) for k in ('codec_name','profile','pix_fmt','width','height','r_frame_rate','nb_frames')},'audio':{k:a.get(k) for k in ('codec_name','sample_rate','channels')},'full_decode':'passed','black_intervals':black_events,'viewport_frames_checked':len(viewport),'blank_viewport_frames':blank,'loudness':loudness}
  print('validated',path.name,duration,flush=True)
 for kind,prefix in [('full','patch-audit-full'),('short','patch-audit-60s')]:
  if kind not in wanted:continue
  timeline=json.loads((HERE/(kind+'-timeline.json')).read_text())
  story=json.loads((HERE/'story.json').read_text())[kind]
  srt=(HERE/(prefix+'.srt')).read_text();blocks=srt.strip().split('\n\n')
  # A legal line break after a hyphen is layout, not a missing narration word.
  displayed=' '.join(re.sub(r'(?<=-)\n(?=\w)', '', '\n'.join(b.splitlines()[2:])) for b in blocks)
  expected=' '.join(t for u in story for t in u['lines']).replace('one hundred and fifty-five','155')
  assert re.sub(r'\s+',' ',displayed)==re.sub(r'\s+',' ',expected),'Incomplete captions'
  assert (HERE/(prefix+'.vtt')).read_text().startswith('WEBVTT\n')
  samples=[]
  for i,item in enumerate(timeline):
   samples.append((item['at']+min(5,item['duration']/2),item['id']+'-content'))
   if item['source']=='empty':
    close=4.5 if kind=='full' else 3.0
    samples.extend([(item['at']+close-1/30,'evidence-zoom-before'),(item['at']+close+1/30,'evidence-zoom-after')])
   if i:
    samples.extend([(item['at']-1/30,item['id']+'-before-cut'),(item['at']+1/30,item['id']+'-after-cut')])
  end=timeline[-1]['at']+timeline[-1]['duration']
  samples.append((end-.12,'ending'))
  tiles=[]
  for i,(at,label) in enumerate(samples):
   frame=QA/f'{kind}-{i:03}-{label}.png'
   ffmpeg('-loglevel','error','-y','-ss',at,'-i',OUT/(prefix+'-captioned.mp4'),'-frames:v','1',frame)
   with Image.open(frame) as im:
    tile=Image.new('RGB',(480,298),'#080e18');tile.paste(im.resize((480,270)),(0,28))
   ImageDraw.Draw(tile).text((8,6),f'{at:06.2f}s  {label}',font=ImageFont.truetype(subprocess.check_output(['fc-match','-f','%{file}','DejaVu Sans'],text=True),13),fill='#edf2fb')
   tiles.append(tile)
   report['samples'].append({'kind':kind,'seconds':at,'label':label,'file':frame.name})
  for start in range(0,len(tiles),16):
   batch=tiles[start:start+16];sheet=Image.new('RGB',(1920,298*((len(batch)+3)//4)),'#080e18')
   for j,tile in enumerate(batch):sheet.paste(tile,((j%4)*480,(j//4)*298))
   sheet.save(QA/f'{kind}-contact-{start//16:02}.jpg',quality=91)
  report['captions'][kind]={'complete_transcript_match':True,'cues':len(blocks),'last_film_frame_seconds':end,'samples':len(samples)}
 (QA/('frame-review.json' if args.frames_only else 'media-qa.json' if args.kind=='all' else 'media-qa-'+args.kind+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 print('All media checks completed',flush=True)

if __name__=='__main__':main()
