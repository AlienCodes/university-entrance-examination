"""Publish a checked complete Aiden pilot, then read back its public MP4."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen

from aiden_profile import IDENTITY, PAUSE_POLICY, PROFILE
from collect_edition import unpack_lesson
from lesson import PID, PROJECT
from release_assets import inventory

OLD_VIDEO = 'ad99d8d38def3319524bcb91865981d2d593d84f0e4f849715b26bc1f5cae6c8'
OLD_MASTER = 'C13T1P1-aeae0eef0460a54f.zip'
OLD_MASTER_SHA = '373f52a9fb66b37ec9f0630c300b9ead132459f71853961797ef5b0cea012d4e'

def public_download(asset, expected):
    for attempt in range(5):
        try:
            url = asset['browser_download_url']
            if attempt:
                url += '?v=' + expected['video_sha256'][:12]
            request = Request(url, headers={'User-Agent': 'IELTS-media-verification', 'Cache-Control': 'no-cache'})
            digest = hashlib.sha256()
            count = 0
            with urlopen(request, timeout=90) as src:
                for block in iter(lambda: src.read(1 << 20), b''):
                    count += len(block)
                    digest.update(block)
            if (count, digest.hexdigest()) != (expected['video_bytes'], expected['video_sha256']):
                raise ValueError('Public download differs from the checked master')
            return
        except (OSError, ValueError):
            if attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))


def repair_original_link(tag, stage, file, label, receipt, notes):
    inventory.cache_clear()
    asset = inventory(tag).get(file.name)
    if asset and asset.get('digest') == 'sha256:' + receipt['video_sha256']:
        public_download(asset, receipt)
        return
    backup = inventory(stage).get(OLD_MASTER, {})
    if (asset and asset.get('digest') != 'sha256:' + OLD_VIDEO) or backup.get('digest') != 'sha256:' + OLD_MASTER_SHA:
        raise ValueError('Original release no longer matches the archived incident')
    subprocess.run(['gh', 'release', 'upload', tag, str(file)+'#'+label, '--clobber'], check=True)
    inventory.cache_clear()
    asset = inventory(tag)[file.name]
    if (asset['size'],asset['digest']) != (receipt['video_bytes'],'sha256:'+receipt['video_sha256']):
        raise ValueError('The repaired original URL points to a different file')
    public_download(asset, receipt)
    subprocess.run(['gh', 'release', 'edit', tag, '--notes-file', str(notes)], check=True)


def publish(folder):
    folder.mkdir(parents=True, exist_ok=True)
    stage = 'ielts-academic-aiden-cache-' + os.environ['IELTS_AIDEN_BATCH']
    legacy = 'ielts-academic-aiden-preview-' + PID.lower()
    tag = legacy + '-r2'
    meta = json.loads((PROJECT / '原稿' / (PID + '.json')).read_text())
    name = f"{meta['book']}-{meta.get('printed_test', meta['test'])}-{meta['passage']}"
    takes = []
    recorded = {}

    def voice_proof(_, media):
        report = json.loads(media.read('source/narration.json'))
        takes.extend(report['sentences'].values())
        recorded.update(report['mp4_check'])
        if report['profile'] != PROFILE or not report['certificate']['passed']:
            raise ValueError('The voice in this master differs from the audition')

    video, _, receipt = unpack_lesson(PID, stage, folder, voice_proof)
    report = json.loads((folder / 'verification.json').read_text())
    count = sum(len(paragraph) for paragraph in meta['paragraphs'])
    phrase_count = sum(len(t.get('phrases', [])) for t in takes)
    if (receipt.get('narrator') != IDENTITY or len(takes) != count or not phrase_count
            or not all(r.get('recognized') and r.get('method') == PAUSE_POLICY for r in takes)
            or receipt.get('pause_policy') != PAUSE_POLICY or recorded['policy'] != PAUSE_POLICY
            or recorded['passed'] is not True or recorded['sha256'] != receipt['video_sha256']
            or receipt['verified_phrases'] != phrase_count or recorded['phrases'] != phrase_count
            or report['ending']['decoded_last_three_seconds_frames'] != 90):
        raise ValueError('Incomplete pilot voice or playback checks')
    if PID == 'C13T1P1':
        parts = [p for p in recorded['checks'] if p['sentence'] == 3]
        if (len(parts) < 2 or 'export sectors' not in parts[0]['text'].lower()
                or re.findall(r"[a-z]+", parts[0]['second_heard'].lower())[-1:] != ['sectors']
                or re.findall(r"[a-z]+", parts[1]['second_heard'].lower())[:1] != ['which']):
            raise ValueError('The independent AAC replay must hear the intact sectors before the pause and which after it')
    title = f"{name} {receipt['title_zh']}"
    label = title + '.mp4'
    file = folder / (name + '-Aiden.mp4')
    video.replace(file)
    notes = folder / 'notes.md'
    notes.write_text(f"{title}。完整 Aiden 英文朗读，配逐句翻译和语境词汇。\n\n"
                     f"全篇 {count} 句，共 {receipt['pages']} 屏。第 3 句 export sectors 已修复。"
                     f"已从成片核对全部 {phrase_count} 个意群及片尾。\n\n"
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
        subprocess.run(['gh','release','edit',tag,'--draft=false','--latest=false','--notes-file',str(notes)], check=True)
        # Draft assets can have a temporary untagged URL. Read the public one after publication.
        inventory.cache_clear()
        asset = inventory(tag)[file.name]
    public_download(asset, receipt)
    if PID == 'C13T1P1':
        repair_original_link(legacy, stage, file, label, receipt, notes)
    print(json.dumps(dict(url=asset['browser_download_url'], bytes=asset['size'],
                          sha256=receipt['video_sha256'], seconds=receipt['video_seconds'],
                          screens=receipt['pages'], sentences=count)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    publish(parser.parse_args().folder)
