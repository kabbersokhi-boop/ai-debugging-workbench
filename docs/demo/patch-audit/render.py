"""Reproduce the finished edit from authentic captured footage and local narration.

Execution waits are explicitly labeled when accelerated. Editorial zoom, titles and source labels are
separate from the product. Captions use local ASR timing plus the exact narration.
"""
import argparse
import hashlib
from datetime import datetime
import json
import math
import subprocess
import textwrap
from pathlib import Path
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'artifacts/demo-production'
STORY=json.loads((HERE/'story.json').read_text())
OUT=WORK/'finished'
BUILD=WORK/'edit'
FONT=subprocess.check_output(['fc-match','-f','%{file}','Open Sans'],text=True)
BOLD=subprocess.check_output(['fc-match','-f','%{file}','Open Sans:style=Bold'],text=True)
MONO=subprocess.check_output(['fc-match','-f','%{file}','DejaVu Sans Mono'],text=True)
BG='#080e18'; WHITE='#edf2fb'; MUTED='#acbbd1'; BLUE='#a9b9ff'; AMBER='#f4bd81'; GREEN='#9ce7c3'

def run(args):
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)

def f(size,bold=False,mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT,size)

def overlay(unit,index,total):
    im=Image.new('RGBA',(1920,1080),(0,0,0,0)); d=ImageDraw.Draw(im)
    color=AMBER if unit['id'] in ('hook','contrast','missed','cause','empty','scope','short_hook','short_missed','short_empty') else GREEN if unit['id'] in ('pass','short_pass','complete','complete_diff') else BLUE
    d.text((96,24),unit['chapter'],font=f(20,True),fill=color)
    title=unit['title']; size=38
    while d.textlength(title,font=f(size,True))>1600:size-=1
    d.text((96,58),title,font=f(size,True),fill=WHITE)
    d.text((98,118),unit['mode'],font=f(17,True),fill=MUTED)
    d.text((1794,28),'PA',font=f(28,True),fill=BLUE)
    d.rounded_rectangle((91,149,1828,951),radius=8,outline='#3a4862',width=2)
    d.line((96,962,1824,962),fill='#223049',width=3)
    d.line((96,962,96+int(1728*(index+1)/total),962),fill=color,width=3)
    # The clean version has branding and generous empty caption space.
    d.text((98,1044),'PATCH AUDIT  /  EXACT CHANGE → INDEPENDENT EVIDENCE',font=f(14,True),fill='#8293af')
    d.text((1718,1044),f'{index+1:02} / {total:02}',font=f(14,mono=True),fill='#8293af')
    if unit['id'] in ('close','short_close'):
        d.rounded_rectangle((160,575,1760,914),radius=18,fill=(8,14,24,244),outline='#53688e',width=2)
        d.text((210,610),'EXPLORE PATCH AUDIT',font=f(25,True),fill=GREEN)
        d.text((210,663),'ai-debugging-workbench-recorded.vercel.app',font=f(34,True),fill=WHITE)
        d.text((210,720),'Historical evidence · no public execution · no credentials',font=f(24),fill=MUTED)
        d.text((210,800),'github.com/kabbersokhi-boop/ai-debugging-workbench',font=f(25),fill=BLUE)
        d.text((210,848),'Fresh patch auditing runs locally on approved task environments.',font=f(21),fill=MUTED)
    path=BUILD/(unit['id']+'-overlay.png');im.save(path);return path

def stamp(seconds,comma=False):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02}{"," if comma else "."}{ms:03}'

def captions(kind,timeline):
    entries=[]
    for item in timeline:
        alignment=json.loads((WORK/'alignment'/(item['id']+'.json')).read_text())
        for caption in alignment['captions']:
            start=item['at']+.35+caption['start'];end=item['at']+.35+caption['end']
            entries.append((start,end,'\n'.join(textwrap.wrap(caption['text'],width=40,break_long_words=False))))
    srt='\n\n'.join(f'{i+1}\n{stamp(a,True)} --> {stamp(b,True)}\n{t}' for i,(a,b,t) in enumerate(entries))+'\n'
    vtt='WEBVTT\n\n'+'\n\n'.join(f'{stamp(a)} --> {stamp(b)}\n{t}' for a,b,t in entries)+'\n'
    prefix='patch-audit-full' if kind=='full' else 'patch-audit-60s'
    for ext,content in [('srt',srt),('vtt',vtt)]:
        (HERE/(prefix+'.'+ext)).write_text(content)
        (OUT/(prefix+'.'+ext)).write_text(content)
    assert len(entries)>10
    for i,(a,b,t) in enumerate(entries):
        assert a<b and len(t.splitlines())<=2,(i,t)
        if i:assert a>=entries[i-1][1],(i,a,entries[i-1])
    ass='[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Caption,Open Sans,34,&H00FBF2ED,&H00FBF2ED,&H00180E08,&H00180E08,0,0,0,0,100,100,0,0,3,6,0,2,96,96,40,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    def ass_time(t):
        return stamp(t)[1:-1]
    for a,b,text in entries:
        ass+=f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Caption,,0,0,0,,'+text.replace('\n',r'\N')+'\n'
    ass_path=BUILD/(prefix+'.ass');ass_path.write_text(ass)
    return ass_path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['full','short'],default='full');ap.add_argument('--assemble-only',action='store_true');ap.add_argument('--refresh-clips',nargs='*',default=[]);ap.add_argument('--audio-only',action='store_true');args=ap.parse_args()
    if args.audio_only:
        if args.refresh_clips:ap.error('--audio-only cannot change visual clips')
        args.assemble_only=True
    OUT.mkdir(exist_ok=True);BUILD.mkdir(exist_ok=True)
    capture_path=WORK/'raw/capture-with-closeups.json'
    if not capture_path.exists():capture_path=WORK/'raw/capture.json'
    capture=json.loads(capture_path.read_text())
    shots={}
    for origin in capture.get('camera_origins',['local','public']):
        for shot in json.loads((WORK/'raw'/(origin+'-shots.json')).read_text())['shots']:shots[shot['id']]=shot
    units=STORY[args.kind]
    timeline=[];audios=[];at=0.0;rate=24000
    for index,unit in enumerate(units):
        source=unit.get('source',unit['id']);shot=shots[source]
        audio,sr=sf.read(WORK/'narration'/(unit['id']+'.wav'),dtype='float32');assert sr==rate
        duration=math.ceil((len(audio)/rate+1.1)*30)/30
        available=shot['end']-shot['start']
        if duration>available+.3:raise ValueError(f'Recording too short for {unit["id"]}: {duration} > {available}')
        # Short edit uses the same original recordings. Skip initial navigation on evidence closeups.
        shift=min(2.0,max(0,available-duration-.15)) if args.kind=='short' and source in ('review','empty','identity') else 0
        start=shot['start']+shift
        speed=available/duration if source in ('start','pass_run') else 1.0
        if speed > 1.01:
            unit=unit | {'mode':f'LOCAL · {speed:.2f}× PLAYBACK · {available:.1f}s RAW SEGMENT RETAINED'}
        item={'id':unit['id'],'source':source,'origin':shot['origin'],'source_start':start,'duration':duration,'playback_speed':speed,'source_duration':duration*speed,'at':at,'title':unit['title']}
        timeline.append(item)
        lead=np.zeros(round(rate*.35),dtype=np.float32)
        tail=np.zeros(round(duration*rate)-len(lead)-len(audio),dtype=np.float32)
        audios.extend([lead,audio,tail])
        at+=duration
        layer=overlay(unit,index,len(units))
        clip=BUILD/(unit['id']+'.mp4')
        input_identity={'renderer':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'unit':unit,'shot':item,'source_sha256':hashlib.sha256((WORK/capture[shot['origin']+'_video']).read_bytes()).hexdigest(),'overlay_sha256':hashlib.sha256(layer.read_bytes()).hexdigest()}
        identity_path=clip.with_suffix('.render.json')
        reusable=clip.exists() and identity_path.exists() and json.loads(identity_path.read_text())==input_identity
        if unit['id'] in args.refresh_clips:reusable=False
        elif args.assemble_only:
            previous=json.loads(identity_path.read_text())
            # Resume after an audio/subtitle-only edit; all encoded visual inputs must still match.
            reusable={k:v for k,v in previous.items() if k!='renderer'}=={k:v for k,v in input_identity.items() if k!='renderer'}
            if not reusable:raise ValueError('Visual inputs changed; rerender this clip before assembly')
        if not reusable:
            video=WORK/capture[shot['origin']+'_video']
            # A restrained 3% editorial push. Original aspect ratio preserved.
            telemetry=''
            if source in ('start','pass_run'):
                saved=capture['incomplete' if source=='start' else 'complete']['evidence']['envelope']['result']
                zero=capture['local_zero_epoch']
                for phase,label in [('ordinary','ORDINARY PHASE'),('independent','INDEPENDENT PHASE')]:
                    record=saved[phase]
                    begin=(datetime.fromisoformat(record['started_at']).timestamp()-zero-start)/speed
                    end=begin+record['duration_ms']/1000/speed
                    telemetry+=f",drawtext=fontfile={FONT}:text='CAPTURE TIMELINE / {label}':fontsize=16:fontcolor=0xa9b9ff:x=1210:y=119:enable='between(t,{max(0,begin)},{min(duration,end)})'"
            graph=(f"[0:v]setpts=(PTS-STARTPTS)/{speed},fps=30,zoompan=z='min(1+on*0.000055,1.03)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.2':d=1:s=1728x792:fps=30,setsar=1,pad=1920:1080:96:154:color=0x080e18[screen];[screen][1:v]overlay=0:0:format=auto{telemetry},format=yuv420p[v]")
            if source=='empty':
                close_at=4.5 if unit['id']=='empty' else 3.0
                # Enlarge actual expected/observed UI pixels after first showing full context.
                # No recreated JSON or substituted outcome labels; both crops are from the same frame.
                graph=(f"[0:v]setpts=(PTS-STARTPTS)/{speed},fps=30,split=3[base][exp][obs];"
                       "[base]scale=1728:792,setsar=1,pad=1920:1080:96:154:color=0x080e18[screen];"
                       "[exp]crop=550:250:72:45,scale=825:375[expected];"
                       "[obs]crop=550:250:72:293,scale=825:375[observed];"
                       f"[screen]drawbox=x=96:y=154:w=1728:h=792:color=0x080e18@0.9:t=fill:enable='gte(t,{close_at})'[dim];"
                       f"[dim][expected]overlay=110:350:enable='gte(t,{close_at})'[left];"
                       f"[left][observed]overlay=995:350:enable='gte(t,{close_at})'[both];"
                       f"[both]drawtext=fontfile={FONT}:text='EVIDENCE CLOSE-UP / ORIGINAL UI PIXELS':fontsize=20:fontcolor=0xacbbd1:x=112:y=285:enable='gte(t,{close_at})'[close];"
                       "[close][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
            run(['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','2','-ss',str(start),'-i',str(video),'-loop','1','-framerate','30','-i',str(layer),'-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-t',str(duration),'-an','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-r','30','-movflags','+faststart',str(clip)])
            identity_path.write_text(json.dumps(input_identity,indent=2)+'\n')
        print('edited',unit['id'],round(duration,2),flush=True)
    (BUILD/(args.kind+'-timeline.json')).write_text(json.dumps(timeline,indent=2)+'\n')
    (HERE/(args.kind+'-timeline.json')).write_text(json.dumps(timeline,indent=2)+'\n')
    wav=BUILD/(args.kind+'-narration.wav');sf.write(wav,np.concatenate(audios),rate,subtype='PCM_16')
    concat=BUILD/(args.kind+'-clips.txt');concat.write_text(''.join("file '"+str(BUILD/(u['id']+'.mp4'))+"'\n" for u in units))
    prefix='patch-audit-full' if args.kind=='full' else 'patch-audit-60s'
    clean=OUT/(prefix+'.mp4')
    # Two-pass EBU R128 loudness normalization; no music and no paid service.
    measured=subprocess.run(['ffmpeg','-hide_banner','-i',str(wav),'-af','pan=stereo|c0=c0|c1=c0,loudnorm=I=-16:TP=-3:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    log=measured.stderr;analysis=json.JSONDecoder().raw_decode(log[log.rfind('{'):])[0]
    (BUILD/(args.kind+'-loudness.json')).write_text(json.dumps(analysis,indent=2)+'\n')
    loud=f"pan=stereo|c0=c0|c1=c0,loudnorm=I=-16:TP=-3:LRA=7:measured_I={analysis['input_i']}:measured_TP={analysis['input_tp']}:measured_LRA={analysis['input_lra']}:measured_thresh={analysis['input_thresh']}:offset={analysis['target_offset']}:linear=false:print_format=summary,aresample=192000,alimiter=limit=0.6309573445:level=false:latency=true,aresample=48000"
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(wav),'-map','0:v','-map','1:a','-c:v','copy','-af',loud,'-ar','48000','-ac','2','-c:a','aac','-b:a','192k','-t',str(at),'-movflags','+faststart',str(clean)])
    srt=captions(args.kind,timeline)
    captioned=OUT/(prefix+'-captioned.mp4')
    if args.audio_only:
        if not captioned.exists():raise ValueError('Audio-only remux requires the existing captioned video')
        remixed=BUILD/(prefix+'-remixed.mp4')
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(captioned),'-i',str(clean),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(remixed)])
        remixed.replace(captioned)
    else:
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','2','-i',str(clean),'-vf',f"ass={srt}",'-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(captioned)])
    print(args.kind,'finished',round(at,3),'seconds',flush=True)

if __name__=='__main__':main()
