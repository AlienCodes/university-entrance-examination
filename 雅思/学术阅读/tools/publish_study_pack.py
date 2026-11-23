"""Publish a checked study archive and verify the public asset using GitHub's returned digest."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

REPO = 'AlienCodes/university-entrance-examination'
TAG = 'ielts-academic-study-21-14'
TITLE = '剑桥雅思 21–14 学术阅读 · 96 篇配套讲义'


def gh(*args, check=True):
    return subprocess.run(['gh', *args], text=True, capture_output=True, check=check)


def view(tag=TAG):
    res = gh('release','view',tag,'--repo',REPO,'--json','apiUrl',check=False)
    if res.returncode == 0:
        record = json.loads(gh('api',json.loads(res.stdout)['apiUrl']).stdout)
        return dict(isDraft=record['draft'],isPrerelease=record['prerelease'],url=record['html_url'],assets=record['assets'])
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
    books=receipt['books']
    illustrated=books==list(range(13,5,-1))
    if not illustrated and books!=list(range(21,13,-1)):
        raise ValueError('Unknown study edition')
    tag='ielts-academic-study-13-6-by-video' if illustrated else TAG
    title='剑桥雅思 13–6 学术阅读 · 96 篇配套讲义（每篇 3 份 PDF）' if illustrated else TITLE
    if (receipt['passages'],receipt['questions'],receipt['files']) != (96,1280,288) or receipt['zip_name'] != archive.name:
        raise ValueError('Incomplete or mismatched archive receipt')
    with archive.open('rb') as stream:
        if archive.stat().st_size!=receipt['zip_bytes'] or hashlib.file_digest(stream,'sha256').hexdigest()!=receipt['zip_sha256']:
            raise ValueError('Local ZIP differs from the verified teaching pack')
    files = [f"{row['folder']}/{doc['name']}" for row in receipt['contents'] for doc in row['files']]
    with zipfile.ZipFile(archive) as zipped:
        if zipped.namelist() != files or len(set(files)) != 288:
            raise ValueError('Local ZIP does not contain exactly the 288 listed PDFs')
    release = view(tag)
    if release is None:
        illustration_note='每篇首页收入同篇视频插图，逐题说明题干、原文证据、推导和答案。' if illustrated else '原书题号、答案、原文定位与解题过程。'
        desc = f"""剑桥雅思第 {books[0]} 至 {books[-1]} 册学术阅读，共 32 套、96 篇、1,280 题。点击下方 ZIP 一次下载全套 PDF。

压缩包按册号、Test 和 Passage 分为 96 个文件夹，每篇含三份文件。

- **逐题解析.pdf**　{illustration_note}
- **长难句与写作句式.pdf**　每篇细读 3 个原句，并配写作场景、英文例句和中文译文。
- **视频逐屏讲义.pdf**　与对应精读视频配套的原始画面讲义。

第一篇为「{receipt['contents'][0]['folder']}」，最后一篇为「{receipt['contents'][-1]['folder']}」。

下载包的 SHA-256 为 `{receipt['zip_sha256']}`。
"""
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp)/'release.md'
            note.write_text(desc)
            gh('release','create',tag,'--repo',REPO,'--target',target,'--title',title,'--notes-file',str(note),'--draft')
        release = view(tag)
    if release is None:
        raise RuntimeError('Created release cannot be found')
    if not any(a['name']==archive.name for a in release['assets']):
        if not release['isDraft']:
            raise ValueError('A different public release already exists at this tag')
        gh('release','upload',tag,str(archive),'--repo',REPO)
    release = view(tag)
    check_asset(release,archive,receipt)
    if release['isDraft']:
        gh('release','edit',tag,'--repo',REPO,'--draft=false','--prerelease=false','--latest=false')
    public = view(tag)
    if public['isDraft'] or public['isPrerelease']:
        raise ValueError('Final public study release is not visible')
    asset=check_asset(public,archive,receipt)
    if illustrated:
        if len(public['assets'])!=1:
            raise ValueError('Expected one PDF archive in the illustrated study release')
        for attempt in range(4):
            try:
                link=asset['browser_download_url']
                request=Request(link,headers={'Accept-Encoding':'identity','User-Agent':'IELTS-study-handout-check'})
                digest=hashlib.sha256()
                size=0
                with urlopen(request,timeout=120) as remote:
                    for block in iter(lambda:remote.read(4<<20),b''):
                        size+=len(block)
                        digest.update(block)
                if (size,digest.hexdigest())!=(receipt['zip_bytes'],receipt['zip_sha256']):
                    raise ValueError('Public study ZIP differs from the verified teaching archive')
                break
            except OSError:
                if attempt==3:raise
                time.sleep(2**attempt)
        proof=dict(release=public['url'],download=link,bytes=size,sha256=digest.hexdigest(),folders=96,pdfs=288)
        receipt_path.with_suffix('.public.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print(public['url'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path)
    ap.add_argument('receipt',type=Path)
    ap.add_argument('target', help='Commit containing the checked source, teaching notes and asset manifest')
    args=ap.parse_args()
    publish(args.archive,args.receipt,args.target)
