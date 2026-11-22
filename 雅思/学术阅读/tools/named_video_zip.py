"""Build the one-file, Chinese-named video collection and verify its GitHub-hosted download."""
import argparse
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import unicodedata
import zipfile

from collect_edition import sha
from lesson import PROJECT, save
from release_assets import fetch, inventory
from video_edition import LESSONS, TAG as SOURCE_TAG, position, video_name

ZIP_NAME = 'Cambridge-IELTS-21-11-132-Videos.zip'
RELEASE = 'ielts-academic-reading-21-11-single-zip'
CACHE = 'ielts-academic-cache-21'
LAYOUT = 'named-videos-21-11-zip64-layout.json'
TITLE = '剑桥雅思学术阅读第21～11册 · 132篇纯视频中文命名单一整包'
INDEX = PROJECT / '审校' / '第21至11册纯视频文件名.tsv'


def ledger():
    with INDEX.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if [r['lesson'] for r in rows] != LESSONS:
        raise ValueError('Expected all 132 distinct lessons in printed reading order')
    seen = set()
    for row in rows:
        pid = row['lesson']
        _, book, test, passage = position(pid)
        meta = json.loads((PROJECT / '篇目' / pid / '篇目信息.json').read_text())
        source = json.loads((PROJECT / '原稿' / (pid + '.json')).read_text())
        title = meta.get('title_zh') or source['title_zh']
        filename = row['filename']
        key = unicodedata.normalize('NFC', filename).casefold()
        if (filename != f'{book}-{test}-{passage} {title}.mp4' or key in seen
                or row['source'] != video_name(pid) or any(ord(ch) < 32 or ch in '<>:"/\\|?*' for ch in filename)):
            raise ValueError(f'{pid}: invalid or duplicate filename {filename!r}')
        seen.add(key)
        row['bytes'] = int(row['bytes'])
    return rows


def source_file(asset, folder):
    for attempt in range(3):
        try:
            return fetch(asset, folder)
        except (OSError, ValueError, subprocess.CalledProcessError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def inspect_archive(path, rows):
    # Store only ZIP headers and directory metadata alongside the already permanent MP4s.
    # This lossless layout preserves every archive byte even after a delivery link expires.
    parts = []
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as archive, path.open('rb') as raw:
        if archive.namelist() != [r['filename'] for r in rows]:
            raise ValueError('Unexpected ZIP order or member')
        previous_end = 0
        for row, info in zip(rows, archive.infolist(), strict=True):
            if (info.compress_type != zipfile.ZIP_STORED or info.file_size != row['bytes']
                    or info.flag_bits & 8 or info.header_offset != previous_end):
                raise ValueError(f'Invalid member {info.filename}')
            raw.seek(info.header_offset)
            local = raw.read(30)
            if not local.startswith(b'PK\x03\x04'):
                raise ValueError('Invalid local ZIP header')
            filename_length, extra_length = struct.unpack_from('<HH', local, 26)
            header = local + raw.read(filename_length + extra_length)
            digest.update(header)
            content = hashlib.sha256()
            with archive.open(info) as stream:
                for chunk in iter(lambda: stream.read(8 << 20), b''):
                    digest.update(chunk)
                    content.update(chunk)
            if content.hexdigest() != row['sha256']:
                raise ValueError(f'{info.filename}: video differs from published master')
            previous_end = raw.tell() + info.file_size
            parts.append({'filename': row['filename'], 'source': row['source'], 'bytes': row['bytes'],
                          'sha256': row['sha256'], 'header': base64.b64encode(header).decode('ascii')})
        raw.seek(previous_end)
        tail = raw.read()
        digest.update(tail)
    actual = sha(path)
    if digest.hexdigest() != actual:
        raise ValueError('The preserved layout did not reproduce the complete ZIP byte for byte')
    return dict(file=ZIP_NAME, bytes=path.stat().st_size, sha256=actual, source_release=SOURCE_TAG,
                members=parts, tail=base64.b64encode(tail).decode('ascii'))


def build(out):
    rows = ledger()
    assets = inventory(SOURCE_TAG)
    for row in rows:
        asset = assets[row['source']]
        if asset['size'] != row['bytes'] or asset['digest'] != 'sha256:' + row['sha256']:
            raise ValueError('Wrong production master for ' + row['lesson'])
    needed = sum(r['bytes'] for r in rows) + max(r['bytes'] for r in rows) + (128 << 20)
    if shutil.disk_usage(out).free < needed:
        raise OSError(f'The runner requires {needed} free bytes for the combined ZIP')
    result = out / ZIP_NAME
    partial = result.with_suffix('.partial')
    with tempfile.TemporaryDirectory(dir=out) as temp, zipfile.ZipFile(partial, 'w', allowZip64=True) as archive:
        for i, row in enumerate(rows, 1):
            video = source_file(assets[row['source']], Path(temp))
            member = zipfile.ZipInfo(row['filename'], (2026, 11, 22, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            member.file_size = row['bytes']
            with video.open('rb') as source, archive.open(member, 'w') as target:
                shutil.copyfileobj(source, target, 8 << 20)
            video.unlink()
            if i % 12 == 0:
                print(f'{i}/{len(rows)} videos packed', flush=True)
    report = inspect_archive(partial, rows)
    save(out / LAYOUT, report)
    partial.replace(result)
    print(f'{ZIP_NAME}: {report["bytes"]} bytes, SHA-256 {report["sha256"]}', flush=True)


def verify_remote(report, item, repo):
    if (item['expired'] or item['name'] != ZIP_NAME or item['size_in_bytes'] != report['bytes']
            or item['digest'] != 'sha256:' + report['sha256']):
        raise ValueError(f'Incorrect GitHub download metadata for artifact {item["id"]}')
    endpoint = f'repos/{repo}/actions/artifacts/{item["id"]}/zip'
    # Stream the actual hosted download back without retaining a second 14 GB file.
    for attempt in range(3):
        check = hashlib.sha256()
        size = 0
        with subprocess.Popen(['gh', 'api', endpoint], stdout=subprocess.PIPE) as process:
            for chunk in iter(lambda: process.stdout.read(8 << 20), b''):
                check.update(chunk)
                size += len(chunk)
            status = process.wait()
        if status == 0 and size == report['bytes'] and check.hexdigest() == report['sha256']:
            return
        if attempt < 2:
            time.sleep(3 ** attempt)
    raise ValueError(f'Hosted ZIP did not match source: status {status}, received {size}, digest {check.hexdigest()}')


def publish(out):
    repo = os.environ['GH_REPO']
    report = json.loads((out / LAYOUT).read_text())
    item = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/actions/artifacts/{os.environ["ARTIFACT_ID"]}']))
    verify_remote(report, item, repo)
    subprocess.run(['gh', 'release', 'upload', CACHE, str(out / LAYOUT), '--clobber'], check=True)
    inventory.cache_clear()
    if inventory(CACHE)[LAYOUT]['digest'] != 'sha256:' + sha(out / LAYOUT):
        raise ValueError('Permanent recovery layout failed verification')
    url = f'https://github.com/{repo}/actions/runs/{item["workflow_run"]["id"]}/artifacts/{item["id"]}'
    expiry = item['expires_at']
    receipt = dict(tag=RELEASE, file=ZIP_NAME, bytes=report['bytes'], sha256=report['sha256'],
                   count=len(report['members']), url=url, expires_at=expiry, hosted_download_verified=True)
    save(out / 'named-videos-21-11-download.json', receipt)
    subprocess.run(['gh', 'release', 'upload', CACHE, str(out / 'named-videos-21-11-download.json'), '--clobber'], check=True)
    notes = (f'## [一次下载全部 132 篇视频（14.39 GB，单个 ZIP）]({url})\n\n'
             '请先登录 GitHub，再点击上方链接。打开 ZIP 即可看到 132 个 MP4，按第 21 册至第 11 册和各册篇目顺序写入。\n\n'
             '文件名采用「册号-原书 Test 编号-篇号 中文篇名.mp4」。第一篇为 `21-1-1 戴维斯姐妹.mp4`，'
             '第二篇为 `21-1-2 我们为什么需要安静.mp4`。第 12 册沿用纸本 Test 5～8。\n\n'
             f'整包共 {report["bytes"]:,} 字节，SHA-256 为 `{report["sha256"]}`。'
             f' GitHub Actions 整包下载链接有效至 {expiry[:10]}（UTC）。\n')
    notes_file = out / 'release-notes.md'
    notes_file.write_text(notes, encoding='utf-8')
    if subprocess.run(['gh', 'release', 'view', RELEASE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.run(['gh', 'release', 'create', RELEASE, '--draft', '--target', os.environ['GITHUB_SHA'],
                        '--title', TITLE, '--notes-file', str(notes_file)], check=True)
    subprocess.run(['gh', 'release', 'edit', RELEASE, '--draft=false', '--latest=false',
                    '--title', TITLE, '--notes-file', str(notes_file)], check=True)
    print(url, expiry, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'publish'])
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (build if args.action == 'build' else publish)(args.out)
