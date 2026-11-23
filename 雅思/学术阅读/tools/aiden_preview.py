"""Publish a checked complete Aiden pilot, then read back its public MP4."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

from aiden_profile import IDENTITY, PROFILE
from collect_edition import unpack_lesson
from lesson import PID, PROJECT
from release_assets import inventory


def public_download(asset, expected):
    for attempt in range(5):
        try:
            request = Request(asset['browser_download_url'], headers={'User-Agent': 'IELTS-media-verification'})
            digest = hashlib.sha256()
            count = 0
            with urlopen(request, timeout=90) as src:
                for block in iter(lambda: src.read(1 << 20), b''):
                    count += len(block)
                    digest.update(block)
            if (count, digest.hexdigest()) != (expected['video_bytes'], expected['video_sha256']):
                raise ValueError('Public download differs from the checked master')
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))


def publish(folder):
    folder.mkdir(parents=True, exist_ok=True)
    stage = 'ielts-academic-aiden-cache-' + os.environ['IELTS_AIDEN_BATCH']
    tag = 'ielts-academic-aiden-preview-' + PID.lower()
    meta = json.loads((PROJECT / '原稿' / (PID + '.json')).read_text())
    name = f"{meta['book']}-{meta.get('printed_test', meta['test'])}-{meta['passage']}"
    takes = []

    def voice_proof(_, media):
        report = json.loads(media.read('source/narration.json'))
        takes.extend(report['sentences'].values())
        if report['profile'] != PROFILE or not report['certificate']['passed']:
            raise ValueError('The voice in this master differs from the audition')

    video, _, receipt = unpack_lesson(PID, stage, folder, voice_proof)
    report = json.loads((folder / 'verification.json').read_text())
    count = sum(len(paragraph) for paragraph in meta['paragraphs'])
    if (receipt.get('narrator') != IDENTITY or len(takes) != count
            or not all(r.get('recognized') for r in takes)
            or report['ending']['decoded_last_three_seconds_frames'] != 90):
        raise ValueError('Incomplete pilot voice or playback checks')
    title = f"{name} {receipt['title_zh']}"
    label = title + '.mp4'
    file = folder / (name + '-Aiden.mp4')
    video.replace(file)
    notes = folder / 'notes.md'
    notes.write_text(f"{title}。完整 Aiden 英文朗读，配逐句翻译和语境词汇。\n\n"
                     f"全篇 {count} 句，共 {receipt['pages']} 屏。附件为可单独播放的 MP4。\n\n"
                     f"SHA-256 `{receipt['video_sha256']}`\n", encoding='utf-8')
    found = subprocess.run(['gh','release','view',tag,'--json','isDraft'], capture_output=True, text=True)
    if found.returncode:
        subprocess.run(['gh','release','create',tag,'--draft','--latest=false',
                        '--target',os.environ['GITHUB_SHA'],'--title',title+' · Aiden 完整样片',
                        '--notes-file',str(notes)], check=True)
        draft = True
    else:
        draft = json.loads(found.stdout)['isDraft']
    asset = inventory(tag).get(file.name)
    if asset is None:
        if not draft:
            raise ValueError('Missing MP4 in an already published preview')
        subprocess.run(['gh','release','upload',tag,str(file)+'#'+label], check=True)
    inventory.cache_clear()
    asset = inventory(tag)[file.name]
    if (asset['size'], asset['digest']) != (receipt['video_bytes'], 'sha256:'+receipt['video_sha256']):
        raise ValueError('Published asset differs from the validated MP4')
    if draft:
        subprocess.run(['gh','release','edit',tag,'--draft=false','--latest=false'], check=True)
        # Draft assets can have a temporary untagged URL. Read the public one after publication.
        inventory.cache_clear()
        asset = inventory(tag)[file.name]
    public_download(asset, receipt)
    print(json.dumps(dict(url=asset['browser_download_url'], bytes=asset['size'],
                          sha256=receipt['video_sha256'], seconds=receipt['video_seconds'],
                          screens=receipt['pages'], sentences=count)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    publish(parser.parse_args().folder)
