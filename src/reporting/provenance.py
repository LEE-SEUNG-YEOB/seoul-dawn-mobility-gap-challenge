"""Artifact checksums for integrity checks after an interrupted execution."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def output_files(root):
    for folder in ['outputs/final', 'reports']:
        for p in sorted((root / folder).rglob('*')):
            if p.is_file() and 'qa-local' not in p.parts and p.name != 'artifact_manifest.json':
                yield p


def write_manifest(root):
    records = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
                'sha256': digest(p)} for p in output_files(root)]
    target = root / 'outputs/final/artifact_manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'status': 'complete', 'files': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


def verify_manifest(root):
    manifest = json.loads((root / 'outputs/final/artifact_manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'complete':
        raise ValueError('Incomplete artifact manifest')
    for item in manifest['files']:
        p = root / item['path']
        if not p.is_file() or p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
            raise ValueError('Artifact changed or incomplete: ' + item['path'])
    return len(manifest['files'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    root = Path('.')
    if args.write:
        write_manifest(root)
    print(f'Verified {verify_manifest(root)} artifacts')
