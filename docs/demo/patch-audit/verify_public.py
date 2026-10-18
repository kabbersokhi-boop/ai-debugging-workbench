"""Verify anonymous release downloads against local bytes; never use an auth token."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'artifacts/demo-production'
OUT = WORK / 'finished'
BASE = 'https://github.com/kabbersokhi-boop/ai-debugging-workbench/releases/download/v1.1.0/'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Also verify published support/archive/checksum assets')
    args = parser.parse_args()
    names = sorted(p.name for p in OUT.iterdir() if p.is_file() and (args.all or p.suffix == '.mp4'))
    rows = []
    for name in names:
        path = OUT / name
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        url = BASE + name
        request = urllib.request.Request(url, headers={'User-Agent': 'Patch-Audit-media-QA'})
        digest = hashlib.sha256()
        length = 0
        with urllib.request.urlopen(request, timeout=120) as response:
            status = response.status
            assert status == 200, (name, status)
            while block := response.read(1024 * 1024):
                digest.update(block)
                length += len(block)
        assert length == path.stat().st_size and digest.hexdigest() == expected, name
        row = {'name': name, 'url': url, 'anonymous': True, 'status': status,
               'bytes': length, 'sha256': expected}
        if path.suffix == '.mp4':
            request = urllib.request.Request(url, headers={'User-Agent': 'Patch-Audit-media-QA', 'Range': 'bytes=0-31'})
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
                assert response.status == 206 and body == path.read_bytes()[:32], name
                row['range_status'] = response.status
                row['content_range'] = response.headers['Content-Range']
        rows.append(row)
        print('anonymous bytes verified', name, length, flush=True)
    filename = 'public-assets-final.json' if args.all else 'public-assets.json'
    (WORK / 'qa' / filename).write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
