"""Finished-cut transcript, shot list, thumbnail and public asset checksum manifest."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from render import f, WHITE, MUTED, GREEN, AMBER, BLUE, HERE, WORK, OUT

def tc(t):return f'{int(t)//60}:{int(t)%60:02}'

def main():
 s=json.loads((HERE/'story.json').read_text())
 for kind,name in [('full','Full end-to-end film'),('short','60-second highlight')]:
  timeline=json.loads((HERE/(kind+'-timeline.json')).read_text());units={u['id']:u for u in s[kind]}
  transcript=['# Patch Audit · '+name,'','Narration synthesized locally with Kokoro-82M (`af_heart`). No new coding-model generation.','']
  shots=['# '+name+' · finished shot list','','| Time | Shot | Actual source | Playback |','| --- | --- | --- | --- |']
  for shot in timeline:
   u=units[shot['id']]
   transcript.extend(['## '+tc(shot['at'])+' · '+u['title'],'',' '.join(u['lines']),''])
   shots.append(f"| {tc(shot['at'])}–{tc(shot['at']+shot['duration'])} | {shot['title']} | {shot['origin']}: `{shot['source']}` | {shot['playback_speed']:.2f}× |")
  (HERE/(kind+'-transcript.md')).write_text('\n'.join(transcript))
  (HERE/(kind+'-shot-list.md')).write_text('\n'.join(shots)+'\n')
  prefix='patch-audit-full' if kind=='full' else 'patch-audit-60s'
  for suffix in ('transcript','shot-list'):
   p=HERE/(kind+'-'+suffix+'.md');(OUT/(prefix+'-'+suffix+'.md')).write_bytes(p.read_bytes())
 # This composition uses a real fresh-audit capture; no status text is substituted.
 im=Image.new('RGB',(1920,1080),'#080e18');d=ImageDraw.Draw(im)
 d.rounded_rectangle((72,64,338,112),radius=8,fill='#1b2940')
 d.text((96,73),'PATCH AUDIT',font=f(23,True),fill=BLUE)
 d.text((96,187),'155 tests',font=f(112,True),fill=WHITE)
 d.text((96,322),'passed.',font=f(112,True),fill=GREEN)
 d.text((96,491),'The repair was',font=f(56,True),fill=WHITE)
 d.text((96,566),'still incomplete.',font=f(56,True),fill=AMBER)
 d.line((96,697,725,697),fill='#3b4b67',width=2)
 d.text((96,738),'Selected ordinary upstream suite.',font=f(25),fill=MUTED)
 d.text((96,783),'One genuine incomplete repair.',font=f(25),fill=MUTED)
 d.text((96,906),'REVIEW → EXECUTE → INSPECT',font=f(23,True),fill=BLUE)
 raw=Image.open(WORK/'raw/hook.png').convert('RGB')
 # Keep both actual phase cards together. Crop their real source region, without changing labels.
 card=raw.crop((65,177,1380,535));card=card.resize((1016,277))
 panel=Image.new('RGB',(1060,670),'#111b2a');pd=ImageDraw.Draw(panel)
 pd.text((28,28),'ACTUAL FRESH LOCAL AUDIT',font=f(20,True),fill=MUTED)
 pd.text((28,86),'Independent evidence',font=f(40,True),fill=WHITE)
 pd.text((28,144),'The standalone copy was missed.',font=f(25),fill=AMBER)
 panel.paste(card,(22,210))
 pd.text((28,540),'Expected length 0. Observed length 1.',font=f(24,True),fill=WHITE)
 pd.text((28,590),'Keys and items were empty.',font=f(24),fill=MUTED)
 im.paste(panel,(810,202));d=ImageDraw.Draw(im)
 d.rounded_rectangle((810,202,1870,872),radius=12,outline='#44577b',width=2)
 d.text((830,926),'REAL CODE. REAL EXECUTION. INSPECTABLE EVIDENCE.',font=f(21,True),fill=MUTED)
 im.save(HERE/'thumbnail.png',optimize=True)
 (OUT/'patch-audit-thumbnail.png').write_bytes((HERE/'thumbnail.png').read_bytes())
 manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='patch-audit-demo.sha256')
 (OUT/'patch-audit-demo.sha256').write_text(manifest)
 print('Supporting material complete')

if __name__=='__main__':main()
