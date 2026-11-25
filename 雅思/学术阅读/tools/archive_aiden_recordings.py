"""Keep the exact working recordings referenced by a production checkpoint on GitHub Releases."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from release_assets import fetch, inventory


TAG = 'ielts-academic-aiden-cache-13-6'


def check_recordings(path, lesson):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('snapshot.json'))
        if manifest['lesson'] != lesson or not manifest['takes'] or archive.testzip() is not None:
            raise ValueError(f'{lesson}: incomplete recording archive')
        for key, digest in manifest['takes'].items():
            if not re.fullmatch('[0-9a-f]{64}', key):
                raise ValueError(f'{lesson}: unexpected recording key')
            member = 'aiden-takes/' + key
            report = json.loads(archive.read(member + '.json'))
            with archive.open(member + '.flac') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != digest or actual != report['sha256'] or report['policy'] != manifest['policy']:
                raise ValueError(f'{lesson}: the audio differs from its recognition record')
        return len(manifest['takes'])


def check_public_download(url, row):
    for attempt in range(4):
        try:
            request = Request(url + '?verify=' + row['sha256'] + '-' + str(attempt),
                              headers={'User-Agent': 'IELTS-recording-archive', 'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=90) as response:
                digest = hashlib.sha256()
                size = 0
                while block := response.read(1 << 20):
                    digest.update(block)
                    size += len(block)
            if (size, digest.hexdigest()) != (row['bytes'], row['sha256']):
                raise ValueError(f"{row['lesson']}: public recording checksum mismatch")
            return
        except HTTPError as error:
            if error.code not in (404, 429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def preserve(row, repository, assets):
    lesson = row['lesson']
    name = row['archive']
    digest = row['sha256']
    if (not re.fullmatch(r'C(?:[6-9]|1[0-3])T[1-4]P[1-3]', lesson)
            or not re.fullmatch('[0-9a-f]{64}', digest) or name != f'{lesson}-takes-{digest[:20]}.zip'):
        raise ValueError('Invalid archive identity')
    public = f'https://github.com/{repository}/releases/download/{TAG}/{name}'
    if name in assets:
        saved = assets[name]
        if (saved['size'], saved['digest']) != (row['bytes'], 'sha256:' + digest):
            raise ValueError(f'{lesson}: conflicting archive on the release')
        check_public_download(public, row)
        return
    source = dict(name=name, url=f"repos/{repository}/releases/assets/{row['asset_id']}",
                  size=row['bytes'], digest='sha256:' + digest)
    with tempfile.TemporaryDirectory() as folder:
        path = fetch(source, folder)
        count = check_recordings(path, lesson)
        upload = subprocess.run(['gh', 'release', 'upload', TAG, str(path), '--repo', repository],
                                capture_output=True, text=True)
        # A lost upload response can still leave the complete file online.
        # A matching public download also handles another run saving this same asset.
        try:
            check_public_download(public, row)
        except (HTTPError, URLError, TimeoutError, ValueError):
            upload.check_returncode()
            raise
    print(f'{lesson}: {count} recordings, publicly verified {digest}', flush=True)


def main(plan):
    repository = os.environ['GITHUB_REPOSITORY']
    rows = json.loads(Path(plan).read_text())['lessons']
    if len({row['lesson'] for row in rows}) != len(rows):
        raise ValueError('Duplicate lessons in the recording archive')
    assets = inventory(TAG, repository)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [pool.submit(preserve, row, repository, assets) for row in rows]
        for result in results:
            result.result()


if __name__ == '__main__':
    main(sys.argv[1])
