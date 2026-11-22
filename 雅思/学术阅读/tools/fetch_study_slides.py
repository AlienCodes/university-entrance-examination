"""Retrieve the exact published video-frame PDFs without downloading their companion MP4s."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import zipfile

import fitz

PROJECT = Path(__file__).resolve().parents[1]


class ReleaseFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.cache = b''
        self.offset = 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        bases = (0, self.position, self.size)
        self.position = bases[whence] + offset
        if self.position < 0:
            raise OSError('Negative seek')
        return self.position

    def read(self, n=-1):
        start = self.position
        end = self.size if n < 0 else min(start + n, self.size)
        if end <= start:
            return b''
        if not (self.offset <= start and end <= self.offset + len(self.cache)):
            offset = max(0, self.size - 131072) if self.size - start < 131072 else start
            limit = min(self.size, max(end, offset + 8192))
            headers = {'Range': f'bytes={offset}-{limit-1}', 'Accept-Encoding': 'identity', 'User-Agent': 'IELTS-study-pdf'}
            request = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {offset}-{limit-1}/{self.size}':
                    raise OSError('Release host did not serve requested byte range')
                data = response.read()
            if len(data) != limit - offset:
                raise OSError('Incomplete byte range')
            self.cache, self.offset = data, offset
        self.position = end
        return self.cache[start-self.offset:end-self.offset]


def retrieve(entry, folder):
    filename = folder / (entry['lesson'] + '.pdf')
    expected = entry['sha256']
    if filename.exists():
        with filename.open('rb') as infile:
            if filename.stat().st_size == entry['bytes'] and hashlib.file_digest(infile, 'sha256').hexdigest() == expected:
                return
    for attempt in range(4):
        try:
            if 'member' in entry:
                with zipfile.ZipFile(ReleaseFile(entry['release_asset'], entry['release_bytes'])) as archive:
                    data = archive.read(entry['member'])
            else:
                with urllib.request.urlopen(entry['release_asset'], timeout=90) as response:
                    data = response.read()
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"{entry['lesson']}: original slide PDF digest differs")
            with fitz.open(stream=data, filetype='pdf') as doc:
                if len(doc) != entry['pages']:
                    raise ValueError(f"{entry['lesson']}: original slide count differs")
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as output:
                output.write(data)
                tmp = Path(output.name)
            os.replace(tmp, filename)
            return
        except (OSError, zipfile.BadZipFile):
            if attempt == 3:
                raise
            time.sleep(2**attempt)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    ap.add_argument('ids', nargs='*')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = json.loads((PROJECT / '配套讲义/逐屏讲义源文件.json').read_text())
    ids = set(args.ids)
    if ids - {e['lesson'] for e in sources}:
        ap.error('Unknown passage ID')
    selected = [e for e in sources if not ids or e['lesson'] in ids]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda e: retrieve(e, args.output), selected))
    print('Verified', len(selected), 'original slide PDFs')
