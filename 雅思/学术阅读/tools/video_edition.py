"""Publish the verified MP4s in reading order, individually and as video-only book ZIPs."""
import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from collect_edition import get, hash_file, read, sha, unpack_lesson
from editions import books, lesson_ids, production_group
from lesson import PROJECT, save
from material import current_key
from release_assets import fetch, inventory

PART = '21-11'
TAG = 'ielts-academic-reading-21-11-videos'
VOLUMES = books(PART)
LESSONS = lesson_ids(VOLUMES)


def stage(book):
    return 'ielts-academic-cache-' + production_group(book)


def index_name(book):
    return f'video-only-{PART}-book-{book}.json'


def archive_name(book):
    return f'Book-{VOLUMES.index(book) + 1:02d}-Cambridge-IELTS-{book}-MP4.zip'


def position(pid):
    source = read(PROJECT / '原稿' / (pid + '.json'))
    number = LESSONS.index(pid) + 1
    book, test, passage = source['book'], source.get('printed_test', source['test']), source['passage']
    return number, book, test, passage


def video_name(pid):
    number, book, test, passage = position(pid)
    return f'{number:03d}-C{book}-T{test}-P{passage}.mp4'


def matches(asset, entry):
    return asset and asset['size'] == entry['bytes'] and asset['digest'] == 'sha256:' + entry['sha256']


def upload(path, entry, remote):
    if not matches(remote.get(path.name), entry):
        subprocess.run(['gh', 'release', 'upload', TAG, str(path), '--clobber'], check=True)


def build(book, out):
    ids = lesson_ids([book])
    remote = inventory(TAG)
    package = out / archive_name(book)
    videos = []
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_STORED) as archive:
        for pid in ids:
            with tempfile.TemporaryDirectory(dir=out) as tmp:
                folder = Path(tmp)
                video, _, receipt = unpack_lesson(pid, stage(book), folder)
                name = video_name(pid)
                target = folder / name
                video.rename(target)
                entry = dict(lesson=pid, name=name, title=receipt['title_zh'],
                             material_sha256=current_key(PROJECT, pid), sha256=receipt['video_sha256'],
                             bytes=target.stat().st_size, seconds=receipt['video_seconds'])
                # Fixed member metadata keeps a resumed upload identical to the first run.
                member = zipfile.ZipInfo(name)
                member.external_attr = 0o100644 << 16
                with target.open('rb') as src, archive.open(member, 'w') as dest:
                    shutil.copyfileobj(src, dest, 4 << 20)
                upload(target, entry, remote)
                videos.append(entry)
    pack = dict(name=package.name, bytes=package.stat().st_size, sha256=sha(package))
    if pack['bytes'] >= 2**31:
        raise ValueError(f'{package.name} exceeds the GitHub single-asset limit')
    upload(package, pack, remote)
    inventory.cache_clear()
    uploaded = inventory(TAG)
    for entry in [*videos, pack]:
        if not matches(uploaded.get(entry['name']), entry):
            raise ValueError('Uploaded digest mismatch for ' + entry['name'])
    # Read back the hosted ZIP and check every MP4 against its verified production master.
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        returned = fetch(uploaded[pack['name']], Path(tmp))
        with zipfile.ZipFile(returned) as archive:
            if archive.namelist() != [video_name(pid) for pid in ids]:
                raise ValueError('Unexpected files or order in ' + pack['name'])
            for entry in videos:
                with archive.open(entry['name']) as src:
                    if hash_file(src) != entry['sha256']:
                        raise ValueError('Pack member differs from master for ' + entry['lesson'])
    report = out / index_name(book)
    save(report, dict(book=book, videos=videos, archive=pack))
    subprocess.run(['gh', 'release', 'upload', stage(book), str(report), '--clobber'], check=True)


def download_url(name):
    return f'https://github.com/{os.environ["GH_REPO"]}/releases/download/{TAG}/{name}'


def release_notes(indices):
    lines = ['132 篇 4K 学术阅读精读视频，按第 21 册到第 11 册排列。每篇可以单独下载，每册 ZIP 含该册顺序排列的 12 个 MP4。']
    for index in indices:
        book, pack = index['book'], index['archive']['name']
        lines.extend(['', f'## 第 {book} 册', '', f'[整册视频下载（12 篇）]({download_url(pack)})', ''])
        for row in index['videos']:
            n, _, test, passage = position(row['lesson'])
            title = row['title'].replace('[', '［').replace(']', '］')
            lines.append(f'- [{n:03d} · Test {test} · Passage {passage}　{title}]({download_url(row["name"])})')
    return '\n'.join(lines) + '\n'


def publish(out):
    remote = inventory(TAG)
    indices, expected = [], {}
    for book in VOLUMES:
        index = read(get(stage(book), index_name(book), out))
        videos, archive = index['videos'], index['archive']
        if index['book'] != book or [v['lesson'] for v in videos] != lesson_ids([book]) or archive['name'] != archive_name(book):
            raise ValueError(f'Wrong book or reading order for book {book}')
        for v in videos:
            pid = v['lesson']
            if v['name'] != video_name(pid) or v['material_sha256'] != current_key(PROJECT, pid):
                raise ValueError('Wrong video version or ordinal for ' + pid)
        for entry in [*videos, archive]:
            expected[entry['name']] = entry
        indices.append(index)
    if set(remote) != set(expected) or len(expected) != len(LESSONS) + len(VOLUMES):
        raise ValueError('Official release must contain exactly the numbered MP4s and video-only book ZIPs')
    for name, entry in expected.items():
        if not matches(remote[name], entry):
            raise ValueError('Incorrect official asset: ' + name)
    commit = os.environ['GITHUB_SHA']
    record = out / f'video-only-{PART}-manifest.json'
    save(record, dict(tag=TAG, source_commit=commit, books=indices))
    subprocess.run(['gh', 'release', 'upload', stage(21), str(record), '--clobber'], check=True)
    notes = out / 'release-notes.md'
    notes.write_text(release_notes(indices), encoding='utf-8')
    subprocess.run(['gh', 'release', 'edit', TAG, '--target', commit, '--draft=false', '--latest=false',
                    '--title', '剑桥雅思学术阅读精读视频 · 第21～11册（132篇）', '--notes-file', str(notes)], check=True)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('action', choices=('book', 'publish'))
    cli.add_argument('out', type=Path)
    cli.add_argument('--book', type=int, choices=VOLUMES)
    args = cli.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.action == 'book':
        if args.book is None:
            cli.error('book requires --book')
        build(args.book, args.out)
    else:
        publish(args.out)
