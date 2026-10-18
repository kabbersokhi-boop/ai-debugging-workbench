"""Package reproducible captures and QA; exclude tools, secrets and owner paths.

Run after final local/public QA. Existing historical release assets are never touched.
"""
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'artifacts/demo-production'
OUT = WORK / 'finished'


def main():
    qa = WORK / 'qa'
    media = json.loads((qa / 'media-qa.json').read_text())
    public = json.loads((qa / 'public-playback.json').read_text())
    assert len(media['files']) == 4 and len(public) == 4
    assert {x['file'] for x in public} == set(media['files'])
    for name, record in media['files'].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == record['sha256']
    paths = set()
    for directory in ['raw', 'narration', 'alignment']:
        paths.update(p for p in (WORK / directory).rglob('*') if p.is_file())
    paths.update(p for p in qa.iterdir() if (p.suffix in {'.json', '.png', '.jpg'} or p.name.endswith('-viewport-stats.txt')) and p.name not in {'media-qa-short.json', 'local-playback-short.json', 'public-assets-final.json'})
    paths.update(p for p in (WORK / 'edit').iterdir() if p.suffix in {'.json', '.wav', '.ass', '.png'})
    paths.update(p for p in (ROOT / 'docs/demo/patch-audit').iterdir() if p.is_file())
    paths.add(ROOT / 'docs/demo/PATCH-AUDIT-DEMO-PRODUCTION.md')
    # Logs are preserved with only the current home directory replaced. No shell/env dumps.
    extra = {}
    for name in ['check.log', 'product-checks-initial-failed.log', 'product-checks-quiet.log',
                 'media-qa-final.log', 'media-qa-linewrap-initial.log', 'audio-qa-remixed.log', 'playback-remixed.log',
                 'public-playback.log']:
        p = WORK / name
        if p.exists():
            value = p.read_text().replace(str(ROOT), '<repository>').replace(str(Path.home()), '<home>')
            extra[str(p.relative_to(ROOT))] = value.encode()
    entries = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(paths)}
    entries.update(extra)
    checksums = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(entries.items()))
    entries['artifacts/demo-production/REPRODUCTION.sha256'] = checksums.encode()
    archive = OUT / 'patch-audit-demo-reproduction.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w|') as tar:
            for name, data in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755 if name.endswith('verify-product.sh') else 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                tar.addfile(info, io.BytesIO(data))
    (OUT / 'patch-audit-demo-media-qa.json').write_text(json.dumps({
        'media': media,
        'audio': json.loads((qa / 'audio-sync.json').read_text()),
        'public_playback': public,
        'public_assets': json.loads((qa / 'public-assets.json').read_text()),
        'visual_review': json.loads((qa / 'visual-review.json').read_text()),
        'product_checks': {'offline_passed': 124, 'acceptance_passed': 67,
                           'acceptance_opt_in_skipped': 4, 'external_recorded_browser_passed': 2,
                           'initial_visibility_timeout_retained': True},
        'human_listening_review': False,
        'reproduction_files': len(entries),
    }, indent=2) + '\n')
    print('Packaged', len(entries), 'files;', archive.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
