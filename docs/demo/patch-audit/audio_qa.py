"""Check actual encoded narration against the final edit's uncompressed audio.

Per-shot waveform correlation tests synchronization after AAC encode/mux. This is
machine audio QA, not a claim that a human listened to the voice.
"""
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'artifacts/demo-production'

def decode(path):
    data=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','24000','-f','f32le','-'])
    return np.frombuffer(data,dtype='<f4')

def main():
    report={}
    for kind,prefix in [('full','patch-audit-full'),('short','patch-audit-60s')]:
        reference=decode(WORK/'edit'/(kind+'-narration.wav'))
        encoded=decode(WORK/'finished'/(prefix+'.mp4'))
        burned=decode(WORK/'finished'/(prefix+'-captioned.mp4'))
        assert np.array_equal(encoded,burned),'Caption export altered audio'
        assert np.isfinite(encoded).all() and float(np.max(np.abs(encoded))) < 1.0, 'Encoded samples clip or are nonfinite'
        timeline=json.loads((WORK/'edit'/(kind+'-timeline.json')).read_text())
        last=timeline[-1]
        narration=json.loads((WORK/'narration'/(last['id']+'.json')).read_text())
        spoken_end=last['at']+.35+narration['lines'][-1]['end']
        # Also correlate the final spoken second, separately from the first second of each shot.
        positions=[(shot['id'],shot['at']+.9) for shot in timeline]+[('final-spoken-second',spoken_end-1.0)]
        measurements=[]
        for label,position in positions:
            # A voiced second inside each shot; search +/-100ms, about0.625ms precision.
            begin=round(position*24000)
            ref=reference[begin:begin+24000:15].astype(np.float64)
            ref-=ref.mean();ref_norm=np.linalg.norm(ref)
            candidates=[]
            for shift in range(-160,161):
                actual=begin+shift*15
                window=encoded[actual:actual+24000:15].astype(np.float64)
                if len(window)!=len(ref):continue
                window-=window.mean()
                denom=ref_norm*np.linalg.norm(window)
                candidates.append((float(np.dot(ref,window)/denom) if denom else 0,shift/1600))
            correlation,offset=max(candidates)
            assert correlation>.85 and abs(offset)<=.04,(label,correlation,offset)
            measurements.append({'shot':label,'correlation':correlation,'encoded_offset_seconds':offset})
        report[kind]={'clean_and_captioned_decoded_audio_identical':True,'decoded_absolute_peak':float(np.max(np.abs(encoded))),'full_scale_samples':int(np.count_nonzero(np.abs(encoded)>=1.0)),'correlation_by_shot':measurements,'maximum_absolute_offset_seconds':max(abs(x['encoded_offset_seconds']) for x in measurements),'spoken_narration_end_seconds':spoken_end,'encoded_audio_end_seconds':len(encoded)/24000,'trailing_padding_difference_seconds':(len(reference)-len(encoded))/24000,'narration_not_truncated':len(encoded)/24000>=spoken_end+.5,'final_200ms_rms':float(np.sqrt(np.mean(encoded[-4800:]**2))),'decoded_audio_sha256':hashlib.sha256(encoded.tobytes()).hexdigest()}
        assert report[kind]['narration_not_truncated']
        print('audio synchronized',kind,report[kind]['maximum_absolute_offset_seconds'],flush=True)
    (WORK/'qa/audio-sync.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
