"""Download verified release masters and build portable book archives below the GitHub file limit."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from lesson import PROJECT

LIMIT = 1_850_000_000
PILOT_TAG = 'ielts-academic-20-test-1-passage-1-pilot'


def hash_file(file):
    digest=hashlib.sha256()
    for chunk in iter(lambda: file.read(8<<20),b''):
        digest.update(chunk)
    return digest.hexdigest()


def sha(path):
    with path.open('rb') as stream:return hash_file(stream)


def get(tag,name,folder):
    subprocess.run(['gh','release','download',tag,'-p',name,'-D',str(folder),'--clobber'],check=True)


def read(path):
    return json.loads(path.read_text())


def unpack_lesson(pid,cache,folder):
    if pid=='C20T1P1':
        get(PILOT_TAG,'*.mp4',folder)
        for f in ('Reading-notes.pdf','verification.json','SHA256SUMS'):get(PILOT_TAG,f,folder)
        subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=folder,check=True)
        video,=folder.glob('*.mp4');pdf=folder/'Reading-notes.pdf';rep=read(folder/'verification.json')
        content=read(PROJECT/'篇目'/pid/'content-review.json')
        if 'translation_review' not in content or rep['pdf']['bytes']>20_000_000:
            raise ValueError('The published pilot must include the revised teaching material')
        if rep['指纹']!=read(PROJECT/'篇目'/pid/'visual-review.json')['fingerprint']:
            raise ValueError('Pilot release does not correspond to its latest approved visual review')
        row=dict(lesson=pid,title='The kākāpō',title_zh='鸮鹦鹉',content_sha256=content['text_sha256'],
                 video_sha256=sha(video),pdf_sha256=sha(pdf),pages=rep['pdf']['pages'],video_seconds=rep['duration'])
    else:
        get(cache,pid+'.zip',folder)
        archive=folder/(pid+'.zip')
        with zipfile.ZipFile(archive) as media:
            for name in (pid+'.mp4',pid+'.pdf','verification.json'):
                with media.open(name) as f,(folder/name).open('wb') as dest:shutil.copyfileobj(f,dest,1<<20)
        archive.unlink();video=folder/(pid+'.mp4');pdf=folder/(pid+'.pdf');rep=read(folder/'verification.json');row=rep['receipt']
        if row['lesson']!=pid or row['content_sha256']!=read(PROJECT/'篇目'/pid/'content-review.json')['text_sha256']:
            raise ValueError(f'{pid}: package is obsolete or mismatched')
    if (not rep['ok'] or not all(c['ok'] for c in rep['checks']) or not rep['ending']['desktop_html5_playback']['ended']
            or row['video_sha256']!=sha(video) or row['pdf_sha256']!=sha(pdf)
            or pdf.stat().st_size>20_000_000 or row['pages']!=rep['pdf']['pages']):
        raise ValueError(f'{pid}: failed media verification')
    return video,pdf,row


def build_book(book,cache,out):
    out.mkdir(parents=True,exist_ok=True)
    rows=[];packs=[];current_size=0;writer=None
    with tempfile.TemporaryDirectory(dir=out) as td:
        td=Path(td)
        try:
            for test in range(1,5):
                for passage in range(1,4):
                    pid=f'C{book}T{test}P{passage}';folder=td/pid;folder.mkdir()
                    video,pdf,row=unpack_lesson(pid,cache,folder)
                    newsize=video.stat().st_size+pdf.stat().st_size
                    if writer is None or current_size+newsize+1_000_000>LIMIT:
                        if writer is not None:writer.close()
                        path=out/f'Cambridge-IELTS-{book}-Academic-{len(packs)+1:02}.zip'
                        writer=zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED,allowZip64=True);packs.append(path);current_size=0
                    source=read(PROJECT/'原稿'/(pid+'.json'))
                    row['printed_test']=source.get('printed_test',test)
                    prefix=f"Test {row['printed_test']}/Passage {passage}/{pid}"
                    writer.write(video,prefix+'.mp4');writer.write(pdf,prefix+'.pdf');current_size+=newsize
                    row=dict(row,archive=packs[-1].name,path=prefix,video_bytes=video.stat().st_size,pdf_bytes=pdf.stat().st_size)
                    rows.append(row);shutil.rmtree(folder)
        finally:
            if writer is not None:writer.close()
    for p in packs:
        if p.stat().st_size>LIMIT:raise ValueError(f'Oversized release file {p}')
        with zipfile.ZipFile(p) as archive:
            for r in [x for x in rows if x['archive']==p.name]:
                for ext,field in [('mp4','video_sha256'),('pdf','pdf_sha256')]:
                    with archive.open(r['path']+'.'+ext) as st:
                        if hash_file(st)!=r[field]:raise ValueError(f"Incorrect packed media {r['lesson']}")
    return dict(book=book,lessons=rows,archives=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in packs])


def publish(part,tag,stage,out):
    books=list(range(20,10,-1)) if part=='20-11' else list(range(10,0,-1))
    catalog=[];assets=[]
    for b in books:
        name=f'book-{b}-index.json';get(stage,name,out);idx=read(out/name)
        assert idx['book']==b and {x['lesson'] for x in idx['lessons']}=={f'C{b}T{t}P{p}' for t in range(1,5) for p in range(1,4)}
        catalog+=idx['lessons'];assets+=idx['archives']
    if len({x['lesson'] for x in catalog})!=120:raise ValueError('Expected exactly 120 distinct academic passages')
    release_id=subprocess.check_output(['gh','release','view',tag,'--json','databaseId','--jq','.databaseId'],text=True).strip()
    info=json.loads(subprocess.check_output(['gh','api',f'repos/{os.environ["GH_REPO"]}/releases/{release_id}']))
    remote={x['name']:x for x in info['assets']}
    for a in assets:
        r=remote[a['name']]
        if r['state']!='uploaded' or r['size']!=a['bytes'] or r['digest']!='sha256:'+a['sha256']:raise ValueError(a['name'])
    (out/'manifest.json').write_text(json.dumps(dict(part=part,lessons=catalog,archives=assets),ensure_ascii=False,indent=1)+'\n')
    table=out/'contents.csv'
    with table.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['篇目','原书Test','英文标题','中文标题','秒','讲义页数','PDF字节','下载包','包内路径'])
        for r in catalog:writer.writerow([r['lesson'],r['printed_test'],r['title'],r['title_zh'],r['video_seconds'],r['pages'],r['pdf_bytes'],r['archive'],r['path']])
    sums=out/'SHA256SUMS';sums.write_text(''.join(f"{a['sha256']}  {a['name']}\n" for a in assets)+''.join(f'{sha(f)}  {f.name}\n' for f in (table,out/'manifest.json')))
    subprocess.run(['gh','release','upload',tag,str(table),str(out/'manifest.json'),str(sums),'--clobber'],check=True)
    with tempfile.TemporaryDirectory(dir=out) as d:
        for f in (table,out/'manifest.json',sums):
            get(tag,f.name,Path(d))
            if sha(Path(d)/f.name)!=sha(f):raise ValueError(f.name)
    notes=f'剑桥雅思学术阅读第 {books[0]} 至 {books[-1]} 册，共 120 篇。按册下载 ZIP，每篇包含 4K 精读视频和直接从视频截帧的手机讲义，每份 PDF 小于 20 MB。contents.csv 列出每篇标题、时长、页数和下载包。'
    subprocess.run(['gh','release','edit',tag,'--draft=false','--latest=false','--notes',notes],check=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['book','publish']);ap.add_argument('out',type=Path)
    ap.add_argument('--part',required=True,choices=['20-11','10-1']);ap.add_argument('--book',type=int);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if args.stage=='book':
        report=build_book(args.book,'ielts-academic-cache-'+args.part,args.out)
        (args.out/f'book-{args.book}-index.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
    else:publish(args.part,'ielts-academic-reading-'+args.part,'ielts-academic-cache-'+args.part,args.out)
