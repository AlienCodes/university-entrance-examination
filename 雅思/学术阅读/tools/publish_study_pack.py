"""Publish a checked study archive and verify the public asset using GitHub's returned digest."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

REPO = 'AlienCodes/university-entrance-examination'
TAG = 'ielts-academic-study-21-14'
TITLE = '剑桥雅思 21–14 学术阅读 · 96 篇配套讲义'


def gh(*args, check=True):
    return subprocess.run(['gh', *args], text=True, capture_output=True, check=check)


def view():
    res = gh('release','view',TAG,'--repo',REPO,'--json','apiUrl',check=False)
    if res.returncode == 0:
        record = json.loads(gh('api',json.loads(res.stdout)['apiUrl']).stdout)
        return dict(isDraft=record['draft'],url=record['html_url'],assets=record['assets'])
    if 'release not found' in res.stderr.lower() or '404' in res.stderr:
        return None
    raise RuntimeError(res.stderr)


def check_asset(release, archive, receipt):
    candidates = [a for a in release['assets'] if a['name'] == archive.name]
    if len(candidates) != 1:
        raise ValueError('Expected exactly one release archive')
    asset = candidates[0]
    if asset['size'] != archive.stat().st_size or asset.get('digest') != 'sha256:' + receipt['zip_sha256']:
        raise ValueError('GitHub release asset differs from the checked ZIP')
    return asset


def publish(archive, receipt_path, target):
    receipt = json.loads(receipt_path.read_text())
    if (receipt['passages'],receipt['questions'],receipt['files']) != (96,1280,288) or receipt['zip_name'] != archive.name:
        raise ValueError('Incomplete or mismatched archive receipt')
    with archive.open('rb') as stream:
        if archive.stat().st_size!=receipt['zip_bytes'] or hashlib.file_digest(stream,'sha256').hexdigest()!=receipt['zip_sha256']:
            raise ValueError('Local ZIP differs from the verified teaching pack')
    files = [f"{row['folder']}/{doc['name']}" for row in receipt['contents'] for doc in row['files']]
    with zipfile.ZipFile(archive) as zipped:
        if zipped.namelist() != files or len(set(files)) != 288:
            raise ValueError('Local ZIP does not contain exactly the 288 listed PDFs')
    release = view()
    if release is None:
        desc = f"""剑桥雅思 21 至 14 册学术阅读，共 32 套、96 篇、1,280 题。点击下方 ZIP 一次下载全套 PDF。

压缩包按册号、Test 和 Passage 分为 96 个文件夹，每篇含三份文件。

- **逐题解析.pdf**　原书题号、答案、原文定位与解题过程。
- **长难句与写作句式.pdf**　每篇细读 3 个原句，并配写作场景、英文例句和中文译文。
- **视频逐屏讲义.pdf**　与对应精读视频配套的原始画面讲义。

第一篇为「21-1-1 戴维斯姐妹」，最后一篇为「14-4-3 评估海洋垃圾的威胁」。

下载包的 SHA-256 为 `{receipt['zip_sha256']}`。
"""
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp)/'release.md'
            note.write_text(desc)
            gh('release','create',TAG,'--repo',REPO,'--target',target,'--title',TITLE,'--notes-file',str(note),'--draft')
        release = view()
    if release is None:
        raise RuntimeError('Created release cannot be found')
    if not any(a['name']==archive.name for a in release['assets']):
        if not release['isDraft']:
            raise ValueError('A different public release already exists at this tag')
        gh('release','upload',TAG,str(archive),'--repo',REPO)
    release = view()
    check_asset(release,archive,receipt)
    if release['isDraft']:
        gh('release','edit',TAG,'--repo',REPO,'--draft=false')
    public = view()
    if public['isDraft']:
        raise ValueError('Release is still a draft')
    check_asset(public,archive,receipt)
    print(public['url'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path)
    ap.add_argument('receipt',type=Path)
    ap.add_argument('target', help='Commit containing the checked source, teaching notes and asset manifest')
    args=ap.parse_args()
    publish(args.archive,args.receipt,args.target)
