"""Download verified release masters and build portable book archives below the GitHub file limit."""
import argparse
import csv
import hashlib
import fnmatch
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from editions import COLLECTIONS, PILOT_TAG, books, lesson_ids, production_group
from lesson import PROJECT
from material import current_key,legacy_inputs_match,verify_original
from release_assets import fetch,inventory

LIMIT = 1_850_000_000
SCREEN_REPORTS = ('分屏核对.json','visual-review.json')


def hash_file(file):
    digest=hashlib.sha256()
    for chunk in iter(lambda: file.read(8<<20),b''):
        digest.update(chunk)
    return digest.hexdigest()


def sha(path):
    with path.open('rb') as stream:return hash_file(stream)


def get(tag,name,folder):
    assets=inventory(tag)
    matches=[a for n,a in assets.items() if fnmatch.fnmatchcase(n,name)]
    if len(matches)!=1:raise ValueError(f'{tag}: expected one {name}, found {len(matches)}')
    return fetch(matches[0],folder)


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
        for name in SCREEN_REPORTS:
            shutil.copyfile(PROJECT/'篇目'/pid/name,folder/name)
        row=dict(lesson=pid,title='The kākāpō',title_zh='鸮鹦鹉',content_sha256=content['text_sha256'],
                 video_sha256=sha(video),pdf_sha256=sha(pdf),pages=rep['pdf']['pages'],video_seconds=rep['duration'])
    else:
        key=current_key(PROJECT,pid)
        versioned=f'{pid}-{key[:16]}.zip'
        archive=get(cache,versioned if versioned in inventory(cache) else pid+'.zip',folder)
        with zipfile.ZipFile(archive) as media:
            embedded=json.loads(media.read('verification.json'))['receipt']
            if 'material_sha256' in embedded:
                if embedded['material_sha256']!=key:raise ValueError(f'{pid}: incorrect content version')
            elif not legacy_inputs_match(media,PROJECT,pid):
                raise ValueError(f'{pid}: an earlier glossary or split in release archive')
            for name in (pid+'.mp4',pid+'.pdf','verification.json'):
                with media.open(name) as f,(folder/name).open('wb') as dest:shutil.copyfileobj(f,dest,1<<20)
            for name in SCREEN_REPORTS:
                (folder/name).write_bytes(media.read('source/'+name))
        archive.unlink();video=folder/(pid+'.mp4');pdf=folder/(pid+'.pdf');rep=read(folder/'verification.json');row=rep['receipt']
        if row['lesson']!=pid or row['content_sha256']!=read(PROJECT/'篇目'/pid/'content-review.json')['text_sha256']:
            raise ValueError(f'{pid}: package is obsolete or mismatched')
    if (not rep['ok'] or not all(c['ok'] for c in rep['checks']) or not rep['ending']['desktop_html5_playback']['ended']
            or row['video_sha256']!=sha(video) or row['pdf_sha256']!=sha(pdf)
            or pdf.stat().st_size>20_000_000 or row['pages']!=rep['pdf']['pages']):
        raise ValueError(f'{pid}: failed media verification')
    return video,pdf,row


def master_assets(book,cache):
    originals=inventory(cache)
    result={}
    for pid in lesson_ids([book]):
        if pid=='C20T1P1':
            pilot=inventory(PILOT_TAG)
            files=[asset for name,asset in pilot.items() if name.endswith('.mp4') or name in ('Reading-notes.pdf','verification.json')]
            if len(files)!=3:raise ValueError('Incomplete pilot release')
        else:
            version=f'{pid}-{current_key(PROJECT,pid)[:16]}.zip'
            files=[originals[version] if version in originals else originals[pid+'.zip']]
        result[pid]={asset['name']:asset['digest'] for asset in files}
        if not all(d and d.startswith('sha256:') for d in result[pid].values()):
            raise ValueError(f'{pid}: missing GitHub master digest')
    return result


def reusable_book(book,part,out):
    cache='ielts-academic-cache-'+production_group(book)
    asset=inventory(cache).get(f'book-{book}-index.json')
    if not asset:return False
    index=read(fetch(asset,out))
    rows=index['lessons']
    if index['book']!=book or [r['lesson'] for r in rows]!=lesson_ids([book]):return False
    if index.get('master_assets')!=master_assets(book,cache):return False
    if any(row.get('material_sha256')!=current_key(PROJECT,row['lesson']) for row in rows):return False
    remote=inventory('ielts-academic-reading-'+part)
    packs=index['archives']
    if {r['archive'] for r in rows}!={f['name'] for f in packs}:return False
    return all(a['name'] in remote and remote[a['name']]['size']==a['bytes']
               and remote[a['name']]['digest']=='sha256:'+a['sha256'] for a in packs)


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
                    reports=[folder/name for name in ('verification.json',*SCREEN_REPORTS)]
                    newsize=sum(f.stat().st_size for f in (video,pdf,*reports))
                    if writer is None or current_size+newsize+1_000_000>LIMIT:
                        if writer is not None:writer.close()
                        path=out/f'Cambridge-IELTS-{book}-Academic-{len(packs)+1:02}.zip'
                        writer=zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED,allowZip64=True);packs.append(path);current_size=0
                    source=read(PROJECT/'原稿'/(pid+'.json'))
                    row['printed_test']=source.get('printed_test',test)
                    row['material_sha256']=current_key(PROJECT,pid)
                    prefix=f"Test {row['printed_test']}/Passage {passage}/{pid}"
                    writer.write(video,prefix+'.mp4');writer.write(pdf,prefix+'.pdf');current_size+=newsize
                    for report in reports:
                        writer.write(report,f'核验/{pid}/{report.name}',compress_type=zipfile.ZIP_DEFLATED)
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
    return dict(book=book,lessons=rows,master_assets=master_assets(book,cache),archives=[dict(name=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in packs])


def book_sources(part,catalog,out):
    file=out/f'Cambridge-IELTS-{part}-Editable.zip'
    with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
        for row in catalog:
            pid=row['lesson']
            verify_original(PROJECT,pid)
            original=PROJECT/'原稿'/(pid+'.json')
            folder=PROJECT/'篇目'/pid
            source_label='Word来源.json' if int(pid[1:pid.index('T')])==21 else '纸本来源.json'
            archive.write(original,f'{pid}/{source_label}')
            for name in ['双语精读.tsv','篇目信息.json','分屏.json','content-review.json']:
                source=folder/name
                if not source.is_file() and pid=='C20T1P1' and name=='分屏.json':
                    source=PROJECT/'tools/分屏.json'
                archive.write(source,pid+'/'+name)
            if sha(folder/'双语精读.tsv')!=row['content_sha256']:raise ValueError('Edited source differs from packaged video: '+pid)
        archive.write(PROJECT/'精读选词规范.md','精读选词规范.md')
        if 21 in books(part):
            word_dir=PROJECT/'来源'/'第21册'
            word=word_dir/'21.docx'
            handoff=read(word_dir/'篇目索引.json')
            if handoff['upload_sha256']!=sha(word):
                raise ValueError('Wrong original Word file')
            archive.write(word,'第21册Word来源/21.docx')
            archive.write(word_dir/'篇目索引.json','第21册Word来源/篇目索引.json')
            for pid in lesson_ids([21]):
                evidence=word_dir/'核对'/(pid+'.json')
                if read(evidence)['source_sha256']!=sha(word):raise ValueError(pid)
                archive.write(evidence,'第21册Word来源/核对/'+evidence.name)
        if '20-11' in COLLECTIONS[part]:
            audit=PROJECT/'审校'
            archive.write(audit/'纸本页码.json','纸本核对/纸本页码.json')
            for report in sorted(audit.glob('*.json')):
                if report.stem.startswith('C') and report.stem[1:].isdigit() and int(report.stem[1:]) not in books(part):continue
                if report.name!='纸本页码.json':
                    archive.write(report,'审校/'+report.name)
            for page in sorted((audit/'sources').glob('C*/T*P*/source-pages.json')):
                if int(page.parent.parent.name[1:]) not in books(part):continue
                archive.write(page,'纸本核对/'+str(page.relative_to(audit)))
            for scan in sorted((audit/'书影').glob('*.png')):
                archive.write(scan,'审校/书影/'+scan.name)
    with zipfile.ZipFile(file) as archive:
        if archive.testzip() is not None:raise ValueError('Invalid editable source archive')
    return file


def publish(part,tag,out):
    volumes=books(part)
    catalog=[];assets=[]
    for b in volumes:
        stage='ielts-academic-cache-'+production_group(b)
        name=f'book-{b}-index.json';get(stage,name,out);idx=read(out/name)
        assert idx['book']==b and {x['lesson'] for x in idx['lessons']}=={f'C{b}T{t}P{p}' for t in range(1,5) for p in range(1,4)}
        catalog+=idx['lessons'];assets+=idx['archives']
    expected=lesson_ids(volumes)
    if [x['lesson'] for x in catalog]!=expected:
        raise ValueError(f'Expected the complete {len(expected)}-passage collection in book order')
    remote=inventory(tag)
    for a in assets:
        r=remote[a['name']]
        if r['state']!='uploaded' or r['size']!=a['bytes'] or r['digest']!='sha256:'+a['sha256']:raise ValueError(a['name'])
    editable=book_sources(part,catalog,out)
    assets.append(dict(name=editable.name,sha256=sha(editable),bytes=editable.stat().st_size))
    covers = [
        PROJECT / '封面' / f'Cambridge-IELTS-{part}-{ratio}.jpg'
        for ratio in ('16x9', '4x3')
    ]
    cover_index=[dict(name=f.name,sha256=sha(f),bytes=f.stat().st_size) for f in covers]
    (out/'manifest.json').write_text(json.dumps(dict(part=part,source_commit=os.environ.get('IELTS_SOURCE_REV',os.environ.get('GITHUB_SHA')),lessons=catalog,archives=assets,covers=cover_index),ensure_ascii=False,indent=1)+'\n')
    table=out/'contents.csv'
    with table.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['篇目','原书Test','英文标题','中文标题','秒','讲义页数','PDF字节','下载包','包内路径'])
        for r in catalog:writer.writerow([r['lesson'],r['printed_test'],r['title'],r['title_zh'],r['video_seconds'],r['pages'],r['pdf_bytes'],r['archive'],r['path']])
    sums=out/'SHA256SUMS';sums.write_text(''.join(f"{a['sha256']}  {a['name']}\n" for a in assets+cover_index)+''.join(f'{sha(f)}  {f.name}\n' for f in (table,out/'manifest.json')))
    supplemental=[table,out/'manifest.json',sums,editable,*covers]
    subprocess.run(['gh','release','upload',tag,*map(str,supplemental),'--clobber'],check=True)
    inventory.cache_clear()
    with tempfile.TemporaryDirectory(dir=out) as d:
        for f in supplemental:
            get(tag,f.name,Path(d))
            if sha(Path(d)/f.name)!=sha(f):raise ValueError(f.name)
    notes=f'剑桥雅思学术阅读第 {volumes[0]} 至 {volumes[-1]} 册，共 {len(catalog)} 篇。按册下载 ZIP，每篇包含 4K 精读视频和直接从视频截帧的手机讲义，每份 PDF 不超过 20 MB。每册 ZIP 的“核验”目录保存了各篇的成片、画面及换屏时间记录。contents.csv 列出每篇标题、纸本 Test 编号、时长、页数和下载包。Editable.zip 收录全部逐篇可编辑译稿、词汇、分屏和原稿核对记录。'
    options=['--target',os.environ['IELTS_SOURCE_REV']] if 'IELTS_SOURCE_REV' in os.environ else []
    subprocess.run(['gh','release','edit',tag,'--draft=false','--latest=false',*options,'--notes',notes],check=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['book','reuse','publish']);ap.add_argument('out',type=Path)
    ap.add_argument('--part',required=True,choices=COLLECTIONS);ap.add_argument('--book',type=int);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if args.stage in ('book','reuse') and args.book not in books(args.part):ap.error('Book outside this collection')
    if args.stage=='reuse':
        print(str(reusable_book(args.book,args.part,args.out)).lower())
    elif args.stage=='book':
        report=build_book(args.book,'ielts-academic-cache-'+production_group(args.book),args.out)
        (args.out/f'book-{args.book}-index.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
    else:publish(args.part,'ielts-academic-reading-'+args.part,args.out)
