"""Coordinate existing editorial checkpoints and native, verified media for books 10–1."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile

from editions import PRODUCTION_BOOKS, lesson_ids
from release_assets import fetch, inventory

STAGE='ielts-academic-cache-10-1'
NOTES='ielts-academic-editorial-10-1'
REPO=Path(__file__).resolve().parents[3]
PROJECT=REPO/'雅思/学术阅读'
SPEC=REPO/'.github/ielts-early-production.json'

def load(path):
    return json.loads(path.read_text())

def plan():
    spec=load(SPEC)
    published=load(PROJECT/'配套讲义/公开发布核验.json');filename=published['url'].rsplit('/',1)[-1]
    handouts=inventory('ielts-academic-study-21-14').get(filename,{})
    official=json.loads(subprocess.check_output(['gh','release','view','ielts-academic-study-21-14','--json','isDraft,isPrerelease,publishedAt']))
    if official['isDraft'] or official['isPrerelease'] or not official['publishedAt'] or (handouts.get('size'),handouts.get('digest'))!=(published['size'],'sha256:'+published['sha256']):
        raise ValueError('The teaching handouts must be verified and published first')
    all_ids=lesson_ids(PRODUCTION_BOOKS['10-1'])
    ids=spec.get('lessons',all_ids)
    if not ids or len(ids)!=len(set(ids)) or not set(ids)<=set(all_ids):raise ValueError('Out-of-range or duplicate lesson')
    for pid in ids:
        paper=load(PROJECT/'原稿'/(pid+'.json'));prep=load(PROJECT/'备课'/(pid+'.json'))
        if not paper['source_status'].startswith('已逐篇') or [s for g in paper['paragraphs'] for s in g]!=[r['en'] for r in prep['rows']]:
            raise ValueError(pid+' is not tied to the verified academic paper')
    sample=spec.get('sample',ids[0])
    if sample not in ids:raise ValueError('Missing sample')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        print('sample='+sample,file=out)
        print('lessons='+json.dumps([i for i in all_ids if i in ids and i!=sample]),file=out)

def wait_previous():
    for rid in load(SPEC).get('after_runs',[]):
        while True:
            p=subprocess.run(['gh','run','view',str(int(rid)),'--json','status','--jq','.status'],text=True,stdout=subprocess.PIPE,check=True)
            if p.stdout.strip()=='completed':break
            time.sleep(50)

def cached():
    from early_editor import key
    from lesson import PID
    masters=inventory(STAGE);reviewed=inventory(NOTES).get(key()+'-reviewed.zip')
    receipt=masters.get(PID+'-receipt.json')
    if not receipt or not reviewed:return False
    folder=Path(os.environ['IELTS_WORK'])/PID
    row=load(fetch(receipt,folder))
    with zipfile.ZipFile(fetch(reviewed,folder)) as z:proof=json.loads(z.read('content-review.json'))
    asset=masters.get(PID+'-'+row['material_sha256'][:16]+'.zip')
    return bool(asset and asset.get('digest') and proof['checked'] and proof['key']==key() and row['lesson']==PID and row['content_sha256']==proof['text_sha256'])

def diagnostics():
    from early_editor import key,work
    from lesson import LESSON,PID
    wp=work();name=wp/(key()+'-diagnosis.zip')
    reports=[PROJECT/'样片/review.json',LESSON/'分屏.json',LESSON/'visual-review.json',
             LESSON/'content-review.json',LESSON/'分屏核对.json',LESSON/'双语精读.tsv',wp.parent/'editor.log',
             wp.parent/'native-layout.log',wp.parent/'native-video.log',wp.parent/'native-audio.log',wp.parent/'native-package.log']
    for subdir in ('成品核查','语音复检'):
        reports+=list((PROJECT/'样片'/subdir).rglob('*.json'))
    with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_DEFLATED) as out:
        for p in reports:
            if p.is_file():
                member=str(p.relative_to(PROJECT)) if p.is_relative_to(PROJECT) else p.name
                out.writestr(member,p.read_bytes()[-1_600_000:])
        out.writestr('run.txt',os.getenv('GITHUB_RUN_ID','')+' '+PID)
    subprocess.run(['gh','release','upload',NOTES,str(name),'--clobber'],check=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['plan','wait','cached','diagnosis']);a=ap.parse_args()
    if a.stage=='plan':plan()
    elif a.stage=='wait':wait_previous()
    elif a.stage=='cached':print(str(cached()).lower())
    else:diagnostics()
