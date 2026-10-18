"""Audio QA and caption alignment against the final, known narration.

ASR supplies timing evidence only; it never supplies product claims or replaces the
approved transcript. Unmatched words are interpolated between matched audio anchors.
"""
import difflib
import hashlib
import json
import re
import textwrap
from pathlib import Path
from faster_whisper import WhisperModel

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'artifacts/demo-production'
STORY=json.loads(Path(__file__).with_name('story.json').read_text())

def tokens(text):
    text=text.lower().replace('155','one hundred and fifty five').replace('15','fifteen')
    return re.findall(r'[a-z0-9]+',text)

def main():
    model=WhisperModel('base.en',device='cpu',compute_type='int8',cpu_threads=2,download_root=str(WORK/'tools/asr'))
    out=WORK/'alignment'; out.mkdir(exist_ok=True)
    summary={}
    for unit in STORY['full']+STORY['short']:
        uid=unit['id']
        metadata=json.loads((WORK/'narration'/(uid+'.json')).read_text())
        path=out/(uid+'.json')
        audio_hash=hashlib.sha256((WORK/'narration'/(uid+'.wav')).read_bytes()).hexdigest()
        cached=json.loads(path.read_text()) if path.exists() else {}
        if cached.get('audio_sha256')==audio_hash:
            spoken=cached['spoken_words'];transcript=[cached['asr_text']]
        else:
            if path.exists():
                path.rename(path.with_name(uid+'-prior-'+cached.get('audio_sha256','unbound')[:12]+'.json'))
            segments,info=model.transcribe(str(WORK/'narration'/(uid+'.wav')),language='en',beam_size=5,word_timestamps=True,vad_filter=False)
            spoken=[]; transcript=[]
            for segment in segments:
                transcript.append(segment.text)
                for word in segment.words:
                    for token in tokens(word.word):
                        spoken.append({'word':token,'start':word.start,'end':word.end,'probability':word.probability})
        expected=tokens(' '.join(unit['lines']))
        matcher=difflib.SequenceMatcher(None,expected,[w['word'] for w in spoken],autojunk=False)
        anchors={}
        for block in matcher.get_matching_blocks():
            for j in range(block.size):anchors[block.a+j]=spoken[block.b+j]
        coverage=len(anchors)/len(expected)
        if coverage<.82:raise ValueError(f'Audio transcription requires review: {uid}: {coverage:.3f}')
        groups=[]; token_offset=0
        for line in metadata['lines']:
            # About 64 characters / 2 lines, with no omitted narration.
            words=line['text'].replace('one hundred and fifty-five','155').split(); chunks=[]; chunk=[]
            for word in words:
                if chunk and (len(' '.join(chunk+[word]))>66 or len(textwrap.wrap(' '.join(chunk+[word]),width=40))>2):
                    chunks.append(' '.join(chunk));chunk=[]
                chunk.append(word)
            if chunk:chunks.append(' '.join(chunk))
            counts=[len(tokens(c)) for c in chunks]
            total=sum(counts); consumed=0
            for text,count in zip(chunks,counts):
                first=token_offset+consumed; last=first+count-1
                a=anchors.get(first); b=anchors.get(last)
                start=a['start'] if a else line['start']+(line['end']-line['start'])*consumed/total
                end=b['end'] if b else line['start']+(line['end']-line['start'])*(consumed+count)/total
                start=max(line['start'],start-.06); end=min(line['end']+.06,end+.08)
                if groups:start=max(start,groups[-1]['end']+.01)
                groups.append({'text':text,'start':start,'end':max(start+.4,end)})
                consumed+=count
            token_offset+=total
        data={'id':uid,'caption_version':'numeric-v2','audio_sha256':audio_hash,'asr_text':''.join(transcript).strip(),'matched_word_fraction':coverage,'spoken_words':spoken,'captions':groups,'sentence_timings':metadata['lines']}
        path.write_text(json.dumps(data,indent=2)+'\n')
        summary[uid]=data
        print(uid,round(coverage,3),flush=True)
    (out/'all.json').write_text(json.dumps(summary,indent=2)+'\n')

if __name__=='__main__': main()
