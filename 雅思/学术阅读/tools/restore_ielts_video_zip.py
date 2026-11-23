"""从正式 GitHub 发布的清单恢复整本系列的纯视频 ZIP，只需 Python 3.9 或以上。"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MANIFEST='https://github.com/AlienCodes/university-entrance-examination/releases/download/ielts-academic-reading-10-1-single-zip/reading-10-1-layout.json'
COUNTS={'restore_ielts_13-6_videos.py':('13-6',96),'restore_ielts_5-1_videos.py':('5-1',60)}
EXPECTED=120
if Path(__file__).name in COUNTS:
    edition,EXPECTED=COUNTS[Path(__file__).name]
    MANIFEST=f'https://github.com/AlienCodes/university-entrance-examination/releases/download/ielts-academic-aiden-{edition}-videos/reading-{edition}-layout.json'
CHUNK=4 << 20

def blocks(file,length):
    while length:
        buf=file.read(min(CHUNK,length))
        if not buf:raise EOFError('下载提前中断')
        yield buf
        length-=len(buf)

def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as src:
        for buf in iter(lambda:src.read(CHUNK),b''):h.update(buf)
    return h.hexdigest()

def hosted_bytes(member):
    start=member['data_offset'];n=member['bytes'];end=start+n-1
    req=Request(member['asset_url'],headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity','User-Agent':'Cambridge-reading-download'})
    with urlopen(req,timeout=120) as r:
        if r.status==206:
            actual=r.headers.get('Content-Range','').split('/')[0]
            if actual!=f'bytes {start}-{end}':raise ValueError('服务器返回的字节范围有误')
        elif r.status==200:
            for _ in blocks(r,start):pass
        else:raise ValueError('下载状态异常')
        yield from blocks(r,n)

def existing(out,row,header):
    offset=out.tell()
    if out.read(len(header))!=header:
        out.seek(offset);return False
    h=hashlib.sha256()
    try:
        for block in blocks(out,row['bytes']):h.update(block)
    except EOFError:
        out.seek(offset);return False
    if h.hexdigest()!=row['sha256']:
        out.seek(offset);return False
    return True

def restore(layout,dest):
    dest.mkdir(parents=True,exist_ok=True);result=dest/layout['file']
    if result.is_file():
        if result.stat().st_size==layout['bytes'] and file_hash(result)==layout['sha256']:return result
        raise FileExistsError(f'已有同名文件且校验值不同，请选择其他目录：{result}')
    tmp=result.with_suffix('.zip.partial')
    existing_size=tmp.stat().st_size if tmp.exists() else 0
    if shutil.disk_usage(dest).free+existing_size<layout['bytes']+32*1024*1024:raise OSError('磁盘空间不足')
    with tmp.open('r+b' if tmp.exists() else 'w+b') as out:
        reuse=True
        for i,row in enumerate(layout['members'],1):
            head=base64.b64decode(row['header'],validate=True)
            if reuse and existing(out,row,head):continue
            reuse=False;offset=out.tell()
            for attempt in range(4):
                out.seek(offset);out.truncate();out.write(head);h=hashlib.sha256()
                try:
                    for chunk in hosted_bytes(row):out.write(chunk);h.update(chunk)
                    if h.hexdigest()!=row['sha256']:raise ValueError('视频校验值有误')
                    break
                except (EOFError,HTTPError,URLError,OSError,ValueError):
                    if attempt==3:raise
                    time.sleep(2**attempt)
            print(f"{i}/{len(layout['members'])}　{row['filename']}",flush=True)
        out.write(base64.b64decode(layout['tail'],validate=True));out.truncate()
    if tmp.stat().st_size!=layout['bytes'] or file_hash(tmp)!=layout['sha256']:raise ValueError('整包大小或 SHA-256 校验失败')
    tmp.replace(result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',nargs='?',type=Path,default=Path.cwd(),help='保存目录，默认当前目录')
    parser.add_argument('--manifest',type=Path,help='可选的本地核验清单')
    args=parser.parse_args()
    if args.manifest:
        data=json.loads(args.manifest.read_text(encoding='utf-8'))
    else:
        with urlopen(Request(MANIFEST,headers={'User-Agent':'Cambridge-reading-download'}),timeout=60) as response:data=json.load(response)
    if Path(data['file']).name!=data['file'] or len(data['members'])!=EXPECTED:sys.exit('清单有误，请从正式 Release 重新获取')
    print(restore(data,args.directory))
