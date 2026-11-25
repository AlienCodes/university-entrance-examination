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
from contextlib import nullcontext
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


def check_public_download(url, row, *, index_audio=False):
    for attempt in range(4):
        try:
            request = Request(url + '?verify=' + row['sha256'] + '-' + str(attempt),
                              headers={'User-Agent': 'IELTS-recording-archive', 'Accept-Encoding': 'identity'})
            with (tempfile.TemporaryFile() if index_audio else nullcontext(None)) as copy, urlopen(request, timeout=90) as response:
                digest = hashlib.sha256()
                size = 0
                while block := response.read(1 << 20):
                    digest.update(block)
                    size += len(block)
                    if copy is not None:
                        copy.write(block)
                if (size, digest.hexdigest()) != (row['bytes'], row['sha256']):
                    raise ValueError(f"{row['lesson']}: public recording checksum mismatch")
                if copy is not None:
                    with zipfile.ZipFile(copy) as saved:
                        return {(key, hashlib.sha256(saved.read(key)).hexdigest())
                                for key in saved.namelist() if key.endswith('.flac')}
                return set()
        except HTTPError as error:
            if error.code not in (404, 429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def preserve(row, repository, assets, index_audio=False):
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
        return check_public_download(public, row, index_audio=index_audio)
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
            members = check_public_download(public, row, index_audio=index_audio)
        except (HTTPError, URLError, TimeoutError, ValueError):
            upload.check_returncode()
            raise
    print(f'{lesson}: {count} recordings, publicly verified {digest}', flush=True)
    return members


def preserve_job_notes(run, records, repository, audio_index):
    """Save the expiring job logs and any raw takes missing from durable snapshots."""
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        output = folder / f'aiden-pause-{run}-job-evidence.zip'
        index = []
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as package:
            for item in records:
                lesson = item['lesson']
                info = json.loads(subprocess.check_output(['gh','api',f"repos/{repository}/actions/artifacts/{item['id']}"]))
                if (info['workflow_run']['id'] != run or info['digest'] != 'sha256:'+item['sha256']
                        or info['size_in_bytes'] != item['bytes'] or lesson not in audio_index
                        or not re.fullmatch(r'aiden-'+re.escape(lesson)+r'-checks-\d+',info['name'])):
                    raise ValueError(f'{lesson}: job recording archive changed')
                local = folder/'job.zip'
                with local.open('wb') as stream:
                    subprocess.run(['gh','api',f"repos/{repository}/actions/artifacts/{item['id']}/zip"], stdout=stream, check=True)
                with local.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']:
                        raise ValueError(f'{lesson}: wrong job artifact bytes')
                retained = reused = 0
                with zipfile.ZipFile(local) as job:
                    for member in job.infolist():
                        name = member.filename
                        if member.is_dir():
                            continue
                        if name.startswith('/') or '..' in Path(name).parts:
                            raise ValueError('Invalid artifact member')
                        content = job.read(member)
                        if (name,hashlib.sha256(content).hexdigest()) in audio_index[lesson]:
                            reused += 1
                            continue
                        package.writestr(zipfile.ZipInfo(lesson+'/'+name),content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=4)
                        retained += 1
                index.append(dict(lesson=lesson, artifact=item['id'], artifact_sha256=item['sha256'],
                                  saved_members=retained, flac_already_in_snapshots=reused))
            package.writestr(zipfile.ZipInfo('index.json'),json.dumps(index,indent=1),compress_type=zipfile.ZIP_DEFLATED)
        with output.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        output=output.rename(folder/f'aiden-pause-{run}-{digest[:20]}.zip')
        inventory.cache_clear()
        existing=inventory(TAG,repository).get(output.name)
        if not existing:
            subprocess.run(['gh','release','upload',TAG,str(output),'--repo',repository],check=True)
        check_public_download(f'https://github.com/{repository}/releases/download/{TAG}/{output.name}',
                              dict(lesson='job evidence',bytes=output.stat().st_size,sha256=digest))
        print(f'{output.name}: preserved and verified {len(index)} job archives',flush=True)


def main(plan):
    repository = os.environ['GITHUB_REPOSITORY']
    manifest = json.loads(Path(plan).read_text())
    primary = manifest['lessons']
    if len({row['lesson'] for row in primary}) != len(primary):
        raise ValueError('Duplicate lessons in the recording archive')
    rows = primary + manifest.get('other_snapshots', [])
    if len({row['archive'] for row in rows}) != len(rows):
        raise ValueError('Duplicate recording snapshot in the archive plan')
    assets = inventory(TAG, repository)
    jobs = manifest.get('job_artifacts', [])
    expected = {item['lesson'] for item in jobs}
    audio_index = {lesson:set() for lesson in expected}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [pool.submit(preserve, row, repository, assets, row['lesson'] in expected) for row in rows]
        for row,result in zip(rows,results):
            members=result.result()
            if row['lesson'] in expected:
                audio_index[row['lesson']].update(members)
    if jobs:
        preserve_job_notes(manifest['production_run'],jobs,repository,audio_index)


if __name__ == '__main__':
    main(sys.argv[1])
