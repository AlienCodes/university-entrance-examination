"""Collect verified early-volume masters, preserve editable sources, and publish one ordered download."""
import argparse
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

from collect_edition import sha, unpack_lesson
from early_editor import FILES, edition_pos_conflicts, key_for, scope_gaps, screen_alignment
from early_plan import NOTES, STAGE
from editions import PRODUCTION_BOOKS, lesson_ids
from lesson import PROJECT, save
from material import current_key, verify_original
from named_video_zip import inspect_archive
from release_assets import fetch, inventory
from submit_reviewed import approved, update_book_index

IDS=lesson_ids(PRODUCTION_BOOKS['10-1'])
TAG='ielts-academic-reading-10-1-single-zip'
ZIP='Cambridge-IELTS-10-1-120-Videos.zip'
LAYOUT='reading-10-1-layout.json'
RECEIPT='reading-10-1-download.json'
TITLE='剑桥雅思学术阅读第10至1册 · 120篇精读视频整包'
BRANCH='codex/ielts-academic-reading'
INDEX=PROJECT/'审校/第10至1册视频成品核验.json'
DOWNLOAD_SCRIPT=PROJECT/'tools/restore_ielts_video_zip.py'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def official():
    cp=subprocess.run(['gh','release','view',TAG,'--json','isDraft,isPrerelease,url'],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if cp.returncode:return None
    r=json.loads(cp.stdout)
    return r if not r['isDraft'] and not r['isPrerelease'] else None

def reviewed_assets():
    editorial=inventory(NOTES);masters=inventory(STAGE)
    missing=[];available={}
    for pid in IDS:
        name=key_for(PROJECT,pid)+'-reviewed.zip'
        receipt=masters.get(pid+'-receipt.json')
        if name in editorial and receipt and editorial[name].get('digest') and receipt.get('digest'):
            available[pid]=(editorial[name],receipt)
        else:missing.append(pid)
    return available,missing

def ingest(out):
    available,missing=reviewed_assets()
    if missing:raise ValueError('Waiting for reviewed video masters: '+', '.join(missing))
    masters=inventory(STAGE);rows=[];boundaries={}
    with tempfile.TemporaryDirectory(dir=out) as td:
        tmp=Path(td)
        for pid,(teaching,receipt) in available.items():
            folder=PROJECT/'篇目'/pid;folder.mkdir(exist_ok=True,parents=True)
            with zipfile.ZipFile(fetch(teaching,tmp)) as z:
                if set(z.namelist())!=set(FILES):raise ValueError(pid+' has inconsistent editable files')
                for f in FILES:(folder/f).write_bytes(z.read(f))
            proof=approved(folder);verify_original(PROJECT,pid)
            text=[line.split('\t') for line in (folder/FILES[0]).read_text().splitlines() if line]
            boundaries[pid]=screen_alignment(text,read(folder/FILES[2])[pid])
            if boundaries[pid]['flags']:raise ValueError(pid+' has a bilingual boundary to review: '+str(boundaries[pid]['flags']))
            conflicts=edition_pos_conflicts(text,read(PROJECT/'备课'/(pid+'.json')))
            if conflicts:raise ValueError(pid+' has a word class to review: '+str(conflicts))
            scope=[(i,missing) for i,row in enumerate(text,1) if (missing:=scope_gaps(row[0],row[1]))]
            if scope:raise ValueError(pid+' has a qualifier to review: '+str(scope))
            if proof['key']!=key_for(PROJECT,pid) or proof['reading_units']!=proof['translation_review']['sentences_checked']:raise ValueError(pid+' has incomplete editorial coverage')
            receipt_data=read(fetch(receipt,tmp));paper=read(PROJECT/'原稿'/(pid+'.json'))
            key=current_key(PROJECT,pid);source=pid+'-'+key[:16]+'.zip'
            if (receipt_data['lesson'],receipt_data['material_sha256'],receipt_data['content_sha256'],receipt_data['title_zh'],receipt_data['title'])!=(pid,key,proof['text_sha256'],paper['title_zh'],paper['title']):
                raise ValueError(pid+' has unaligned teaching/print/video editions')
            asset=masters.get(source)
            if not asset or not asset.get('digest','').startswith('sha256:'):raise ValueError('Missing immutable master '+pid)
            name=f"{paper['book']}-{paper.get('printed_test',paper['test'])}-{paper['passage']} {paper['title_zh']}.mp4"
            if any(ord(ch)<32 or ch in '<>:"/\\|?*' for ch in name):raise ValueError('Unsupported filename '+name)
            rows.append(dict(lesson=pid,filename=name,source=source,sha256=receipt_data['video_sha256'],bytes=receipt_data['video_bytes'],
                        seconds=receipt_data['video_seconds'],screens=receipt_data['pages'],material_sha256=key,source_sha256=asset['digest'][7:],
                        asset_url=asset['browser_download_url'],units=proof['reading_units'],terms=proof['vocabulary_entries']))
    if [r['lesson'] for r in rows]!=IDS or len(set(unicodedata.normalize('NFC',r['filename']).casefold() for r in rows))!=len(IDS):raise ValueError('Invalid book order or duplicate names')
    for book in PRODUCTION_BOOKS['10-1']:update_book_index(book)
    save(PROJECT/'审校/第10至1册分屏对读复核.json',boundaries)
    save(out/'rows.json',rows)
    return rows

def master_offset(file,archive,pid):
    info=archive.getinfo(pid+'.mp4')
    if info.compress_type!=zipfile.ZIP_STORED or info.flag_bits&9:raise ValueError('Master MP4 cannot be recovered byte for byte')
    with file.open('rb') as src:
        src.seek(info.header_offset);head=src.read(30)
        if not head.startswith(b'PK\x03\x04'):raise ValueError('Missing master ZIP header')
        name_size,extra_size=struct.unpack_from('<HH',head,26)
        if src.read(name_size)!=(pid+'.mp4').encode('ascii'):raise ValueError('Wrong source member')
    return info.header_offset+30+name_size+extra_size

def pack(out):
    rows=ingest(out)
    needed=sum(r['bytes'] for r in rows)+3*max(r['bytes'] for r in rows)+(256<<20)
    if shutil.disk_usage(out).free<needed:raise OSError(f'Not enough temporary space for {needed} bytes')
    pending=out/(ZIP+'.partial')
    with zipfile.ZipFile(pending,'w',allowZip64=True) as target:
        for i,row in enumerate(rows,1):
            pid=row['lesson']
            with tempfile.TemporaryDirectory(dir=out) as td:
                tmp=Path(td)
                def inspect(file,archive):
                    row['data_offset']=master_offset(file,archive,pid)
                    for name in FILES:
                        if archive.read('source/'+name)!=(PROJECT/'篇目'/pid/name).read_bytes():raise ValueError(pid+' signed source differs from media')
                video,pdf,receipt=unpack_lesson(pid,STAGE,tmp,inspect)
                if row['sha256']!=receipt['video_sha256'] or video.stat().st_size!=row['bytes']:raise ValueError('Master differs from the verified remote receipt')
                report=read(tmp/'verification.json');ending=report['ending']
                if (ending['decoded_last_three_seconds_frames']!=90 or not ending['desktop_html5_playback']['ended']
                     or report['pdf']['pages']!=row['screens']):raise ValueError('Incomplete tail or screen certificate '+pid)
                for filename in ('分屏核对.json','visual-review.json'):
                    shutil.copyfile(tmp/filename,PROJECT/'篇目'/pid/filename)
                row['verification_report_sha256']=sha(tmp/'verification.json')
                row['native_checks']=len(report['checks'])
                member=zipfile.ZipInfo(row['filename'],(2026,11,23,0,0,0));member.file_size=row['bytes'];member.create_system=3;member.external_attr=0o100644<<16
                with video.open('rb') as src,target.open(member,'w') as dest:shutil.copyfileobj(src,dest,8<<20)
            if i%12==0:print(f'{i}/{len(rows)} confirmed and packed',flush=True)
    report=inspect_archive(pending,rows)
    report.update(file=ZIP,source_release=STAGE)
    for piece,row in zip(report['members'],rows,strict=True):
        piece.update({n:row[n] for n in ('asset_url','source_sha256','data_offset','lesson')})
    save(out/LAYOUT,report);pending.replace(out/ZIP)
    save(INDEX,dict(books=list(PRODUCTION_BOOKS['10-1']),videos=len(rows),reading_units=sum(r['units'] for r in rows),
                    vocabulary_occurrences=sum(r['terms'] for r in rows),screens=sum(r['screens'] for r in rows),file=ZIP,bytes=report['bytes'],
                    sha256=report['sha256'],review_scope='Print reference, translations, vocabulary, native screen layout, audio, MP4 tail and complete ZIP members.',lessons=rows))
    print(f'{ZIP}: {report["bytes"]} bytes, SHA-256 {report["sha256"]}',flush=True)

def streamed_download(endpoint,expected):
    for delay in (0,2,5):
        if delay:time.sleep(delay)
        h=hashlib.sha256();n=0
        with subprocess.Popen(['gh','api',endpoint],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as cp:
            for b in iter(lambda:cp.stdout.read(8<<20),b''):n+=len(b);h.update(b)
            result=cp.wait()
        if result==0 and n==expected['bytes'] and h.hexdigest()==expected['sha256']:return
    raise ValueError('Hosted full download does not reproduce the checked ZIP')

def check_asset(tag,path):
    inventory.cache_clear();a=inventory(tag).get(path.name,{})
    if a.get('size')!=path.stat().st_size or a.get('digest')!='sha256:'+sha(path):raise ValueError('Release asset verification failed: '+path.name)

def publish(out):
    info=read(out/LAYOUT);repo=os.environ['GH_REPO']
    aid=int(os.environ['ARTIFACT_ID'])
    item=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/artifacts/{aid}']))
    if item['expired'] or (item['name'],item['size_in_bytes'],item['digest'])!=(ZIP,info['bytes'],'sha256:'+info['sha256']):raise ValueError('Incorrect hosted archive metadata')
    streamed_download(f'repos/{repo}/actions/artifacts/{aid}/zip',info)
    # The raw artifact is a convenient large-file link. Independently retained per-lesson
    # master assets and the byte-level recipe keep this same ZIP reproducible permanently.
    url=f"https://github.com/{repo}/actions/runs/{item['workflow_run']['id']}/artifacts/{aid}"
    base=f'https://github.com/{repo}/releases/download/{TAG}'
    receipt=dict(tag=TAG,file=ZIP,bytes=info['bytes'],sha256=info['sha256'],count=len(info['members']),url=url,expires_at=item['expires_at'],
                 hosted_download_verified=True,layout_url=base+'/'+LAYOUT,layout_sha256=sha(out/LAYOUT),recovery_url=base+'/'+DOWNLOAD_SCRIPT.name,
                 recovery_sha256=sha(DOWNLOAD_SCRIPT),source_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    save(out/RECEIPT,receipt)
    notes=out/'notes.md'
    notes.write_text(f"## [一次下载全部 120 篇精读视频]({url})\n\n"
        f"登录 GitHub 后点击即可下载一个 ZIP（{info['bytes']/1e9:.2f} GB）。打开后是 120 个 MP4，按剑桥雅思第 10 册到第 1 册排列，各册按原书 Test 和 Passage 顺序。第一篇是 `{info['members'][0]['filename']}`。\n\n"
        "第 3 册 Test 1 Passage 1 和第 1 册 Test 1 Passage 1 为历史与科学内容节选，文件名内标有「节选」。\n\n"
        "两处原书表述需要结合史实阅读。9-2-2 原文把圣赫勒拿岛写作位于南太平洋，岛屿实际位于南大西洋。[地理资料](https://www.britannica.com/place/Saint-Helena-island-South-Atlantic-Ocean)\n\n"
        "5-1-1 沿用上传试卷印出的 1764 和 1775。约翰逊签订词典合同的实际年份为 1746，词典于 1755 年出版。[合同记载](https://en.wikipedia.org/wiki/Samuel_Johnson#A_Dictionary_of_the_English_Language) · [出版资料](https://www.britannica.com/topic/A-Dictionary-of-the-English-Language-by-Johnson)\n\n"
        f"文件大小为 {info['bytes']:,} 字节，SHA-256 为 `{info['sha256']}`。一键下载链接有效至 {item['expires_at'][:10]}（UTC）。\n\n"
        f"也可随时[下载恢复程序]({base}/{DOWNLOAD_SCRIPT.name})，使用 Python 运行 `python {DOWNLOAD_SCRIPT.name}`。程序从逐篇母版恢复同一个 ZIP，支持中断后继续，并核对每个文件和整个 ZIP 的 SHA-256。\n",encoding='utf-8')
    if not subprocess.run(['gh','release','view',TAG],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        if official():raise ValueError('This edition has already been published; check its receipt before replacing it')
    else:
        subprocess.run(['gh','release','create',TAG,'--draft','--target',receipt['source_revision'],'--title',TITLE,'--notes-file',str(notes)],check=True)
    files=[out/LAYOUT,DOWNLOAD_SCRIPT,out/RECEIPT]
    if info['bytes']<2**31:files.append(out/ZIP)
    subprocess.run(['gh','release','upload',TAG,*map(str,files),'--clobber'],check=True)
    for f in files:check_asset(TAG,f)
    subprocess.run(['gh','release','edit',TAG,'--draft=false','--prerelease=false','--latest=false','--title',TITLE,'--notes-file',str(notes)],check=True)
    if not official():raise ValueError('Final release is not public')
    for f in files:check_asset(TAG,f)
    save(PROJECT/'审校/第10至1册视频发布核验.json',receipt)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['ready','pack','publish','published']);ap.add_argument('out',type=Path);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    if a.action=='ready':
        available,missing=reviewed_assets();print(json.dumps(dict(ready=not missing,verified=len(available),missing=missing)))
    elif a.action=='published':print(str(bool(official())).lower())
    elif a.action=='pack':pack(a.out)
    else:publish(a.out)
