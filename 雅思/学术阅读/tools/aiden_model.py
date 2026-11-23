"""Restore the exact audition weights without repeated model-discovery requests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote

from aiden_profile import MODEL, REVISION


def matches(path, entry):
    if not path.is_file() or path.stat().st_size != entry['bytes']:
        return False
    with path.open('rb') as stream:
        if 'sha256' in entry:
            return hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256']
        digest = hashlib.sha1(f"blob {entry['bytes']}\0".encode())
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
        return digest.hexdigest() == entry['git_blob']


def restore(folder, verify_only=False):
    lock = json.loads(Path(__file__).with_name('aiden-model-lock.json').read_text())
    if (lock['model'], lock['revision']) != (MODEL, REVISION):
        raise ValueError('Model manifest does not match the approved audition')
    for entry in lock['files']:
        name = entry['path']
        path = folder / name
        if not matches(path, entry):
            if verify_only:
                raise ValueError(f'Missing or damaged model file {name}')
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(path.suffix + '.partial')
            url = f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{quote(name)}'
            subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                            '--retry', '7', '--retry-all-errors', '--retry-max-time', '1200',
                            '--connect-timeout', '25', '--speed-limit', '1024', '--speed-time', '90',
                            '--output', str(partial), url], check=True)
            if not matches(partial, entry):
                raise ValueError(f'Upstream file failed its pinned checksum: {name}')
            partial.replace(path)
        print(f"{name}: {entry['bytes']} verified bytes", flush=True)
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    restore(args.folder, args.verify_only)
