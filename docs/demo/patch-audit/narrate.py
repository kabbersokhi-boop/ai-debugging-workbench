"""Local, free narration. No provider requests or product dependencies."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '2')
import numpy as np
import onnxruntime as ort
import soundfile as sf
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'artifacts/demo-production'
STORY = json.loads((Path(__file__).with_name('story.json')).read_text())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audition', action='store_true')
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(WORK / 'tools/kokoro-v1.0.onnx'), options, providers=['CPUExecutionProvider'])
    voice = Kokoro.from_session(session, str(WORK / 'tools/voices-v1.0.bin'))
    out = WORK / 'narration'
    out.mkdir(exist_ok=True)
    units = STORY['full'] + STORY['short']
    if args.audition:
        units = [STORY['full'][0], STORY['full'][13], STORY['full'][14]]
    if args.only:
        units = [u for u in units if u['id'] in args.only]
    metadata = {}
    for unit in units:
        chunks, lines, cursor = [], [], 0.0
        # Sentence synthesis yields exact sentence caption boundaries, without forced alignment guesses.
        for text in unit['lines']:
            audio, rate = voice.create(text, voice=STORY['voice'], speed=STORY['speed'], lang='en-us')
            gap = np.zeros(round(rate * .28), dtype=np.float32)
            lines.append({'text': text, 'start': cursor, 'end': cursor + len(audio) / rate})
            cursor += (len(audio) + len(gap)) / rate
            chunks.extend([audio, gap])
        joined = np.concatenate(chunks)
        sf.write(out / (unit['id'] + '.wav'), joined, rate, subtype='PCM_16')
        metadata[unit['id']] = {'duration': len(joined) / rate, 'lines': lines}
        (out / (unit['id'] + '.json')).write_text(json.dumps(metadata[unit['id']], indent=2) + '\n')
        print(unit['id'], round(len(joined)/rate, 2), flush=True)
    (out / ('audition.json' if args.audition else 'timings.json')).write_text(json.dumps(metadata, indent=2) + '\n')

if __name__ == '__main__':
    main()
