"""Publish the six checked Aiden readings requested for viewing before the full series."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from aiden_batch import cached
from aiden_preview import public_download
from aiden_profile import IDENTITY, PAUSE_POLICY, PROFILE
from collect_edition import sha
from lesson import PROJECT, save
from named_video_zip import inspect_archive
from release_assets import fetch, inventory


LESSONS = ('C12T1P2', 'C12T1P3', 'C11T1P1', 'C11T3P3', 'C11T4P1', 'C9T3P1')
STAGE = 'ielts-academic-aiden-cache-13-6'
TAG = 'ielts-academic-aiden-six-preview'
FILENAME = 'Cambridge-IELTS-Aiden-6-Videos.zip'
TITLE = '剑桥雅思学术阅读 · Aiden 英文朗读 · 6 篇完整精读视频'


def checked_video(pid, folder, archive, masters):
    receipt = json.loads(fetch(masters[pid + '-receipt.json'], folder).read_bytes())
    paper = json.loads((PROJECT / '原稿' / (pid + '.json')).read_bytes())
    if not cached(pid, '13-6'):
        raise ValueError(f'{pid}: the video differs from the current checked edition')
    asset = masters[f"{pid}-{receipt['material_sha256'][:16]}.zip"]
    path = folder / asset['name']
    if not path.exists():
        fetch(asset, folder)
    if path.stat().st_size != asset['size'] or asset['digest'] != 'sha256:' + sha(path):
        raise ValueError(f'{pid}: master size or SHA-256 differs')
    with zipfile.ZipFile(path) as source:
        report = json.loads(source.read('verification.json'))
        voice = json.loads(source.read('source/narration.json'))
        meta = json.loads(source.read('source/篇目信息.json'))
        text = source.read('source/双语精读.tsv')
        paragraphs = [[s.split('\t')[0] for s in group.splitlines()]
                      for group in text.decode().strip().split('\n\n')]
        if (report['receipt'] != receipt or paragraphs != paper['paragraphs']
                or hashlib.sha256(text).hexdigest() != receipt['content_sha256']
                or receipt['title'] != paper['title'] or receipt['title_zh'] != meta['title_zh']):
            raise ValueError(f'{pid}: the title, paper or receipt differs from the master')
        audio = receipt['audio_sha256']
        video = receipt['video_sha256']
        expected = [(n, i) for n in range(1, sum(map(len, paragraphs)) + 1)
                    for i in range(1, len(voice['sentences'][f'{pid}:{n}']['phrases']) + 1)]
        if (receipt['narrator'] != IDENTITY or receipt['speaker'] != 'Aiden'
                or receipt['pause_policy'] != PAUSE_POLICY or voice['profile'] != PROFILE
                or not voice['certificate']['passed'] or voice['certificate']['mp3_sha256'] != audio
                or audio != receipt['encoded_reference_sha256'] or audio != voice['mp4_check']['reference_mp3_sha256']
                or not expected or len(expected) != receipt['verified_phrases']
                or not all(r['recognized'] and r['method'] == PAUSE_POLICY for r in voice['sentences'].values())):
            raise ValueError(f'{pid}: incomplete Aiden recording proof')
        for key, digest in [('mp3_check', audio), ('mp4_check', video)]:
            check = voice[key]
            if (not check['passed'] or check['policy'] != PAUSE_POLICY or check['sha256'] != digest
                    or check['phrases'] != len(expected)
                    or [(r['sentence'], r['phrase']) for r in check['checks']] != expected):
                raise ValueError(f'{pid}: incomplete checks in {key}')
        ending = report['ending']
        if (not report['ok'] or not all(r['ok'] for r in report['checks'])
                or ending['decoded_last_three_seconds_frames'] != 90
                or not ending['desktop_html5_playback']['ended']):
            raise ValueError(f'{pid}: incomplete video playback verification')
        printed = paper.get('printed_test', paper['test'])
        filename = f"{paper['book']}-{printed}-{paper['passage']} {receipt['title_zh']}.mp4"
        if any(ch in '<>:"/\\|?*' or ord(ch)<32 for ch in filename):
            raise ValueError(f'{pid}: invalid portable filename')
        info = zipfile.ZipInfo(filename, (2026, 11, 23, 0, 0, 0))
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.file_size = receipt['video_bytes']
        with source.open(pid + '.mp4') as src, archive.open(info, 'w') as dest:
            shutil.copyfileobj(src, dest, 8 << 20)
    return dict(lesson=pid, filename=filename, bytes=receipt['video_bytes'], sha256=video,
                seconds=receipt['video_seconds'], phrases=len(expected), source=asset['name'], source_sha256=asset['digest'][7:])


def build(folder):
    folder.mkdir(parents=True, exist_ok=True)
    masters = inventory(STAGE)
    pending = folder / (FILENAME + '.partial')
    rows = []
    with zipfile.ZipFile(pending, 'w') as bundle:
        for pid in LESSONS:
            rows.append(checked_video(pid, folder / 'masters', bundle, masters))
            print(rows[-1]['filename'], flush=True)
    verified = inspect_archive(pending, rows)
    result = dict(file=FILENAME, bytes=verified['bytes'], sha256=verified['sha256'], lessons=rows)
    save(folder / 'six-preview-verification.json', result)
    pending.replace(folder / FILENAME)
    return result


def publish(folder, proof):
    notes = folder / 'release-notes.md'
    contents = '\n'.join(f"- {r['filename']}" for r in proof['lessons'])
    notes.write_text(f"下载下方 ZIP，即可一次取得 6 篇完整视频。每篇均使用 Aiden 英文朗读，配逐句翻译和语境词汇。\n\n"
                     f"{contents}\n\n整包 {proof['bytes']:,} 字节，SHA-256 为 `{proof['sha256']}`。\n")
    result = subprocess.run(['gh', 'release', 'view', TAG, '--json', 'isDraft'], capture_output=True, text=True)
    if result.returncode:
        subprocess.run(['gh', 'release', 'create', TAG, '--verify-tag', '--draft', '--latest=false',
                        '--title', TITLE, '--notes-file', str(notes)], check=True)
        draft = True
    else:
        draft = json.loads(result.stdout)['isDraft']
    def find_asset():
        inventory.cache_clear()
        return inventory(TAG).get(FILENAME)
    asset = find_asset()
    if asset is None and draft:
        subprocess.run(['gh', 'release', 'upload', TAG, str(folder / FILENAME)], check=True)
        asset = find_asset()
    if not asset or asset['size'] != proof['bytes'] or asset['digest'] != 'sha256:' + proof['sha256']:
        raise ValueError('Release asset differs from the checked ZIP')
    if draft:
        subprocess.run(['gh', 'release', 'edit', TAG, '--draft=false', '--prerelease=false', '--latest=false'], check=True)
    state = json.loads(subprocess.check_output(['gh','release','view',TAG,'--json','isDraft,isPrerelease,publishedAt']))
    if state['isDraft'] or state['isPrerelease'] or not state['publishedAt']:
        raise ValueError('The video preview has not been published')
    asset = find_asset()
    public_download(asset, dict(video_bytes=proof['bytes'], video_sha256=proof['sha256']))
    print(f"{asset['browser_download_url']}  {proof['bytes']} bytes  SHA-256 {proof['sha256']}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    result = build(args.folder)
    if args.publish:
        recorded = json.loads((PROJECT / '审校/Aiden/13-6/六篇试看核验.json').read_bytes())
        if result != recorded:
            raise ValueError('The six videos differ from the selected, independently checked collection')
        publish(args.folder, result)
