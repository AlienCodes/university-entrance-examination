"""Coordinate existing editorial checkpoints and native, verified media for books 10–1."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
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

def missing_editions(ids):
    from early_editor import key_for
    notes=inventory(NOTES);masters=inventory(STAGE)
    missing=[]
    with tempfile.TemporaryDirectory() as td:
        for pid in ids:
            fingerprint=key_for(PROJECT,pid)
            teaching=notes.get(fingerprint+'-reviewed.zip');receipt=masters.get(pid+'-receipt.json')
            if teaching and receipt and teaching.get('digest') and receipt.get('digest'):
                with zipfile.ZipFile(fetch(teaching,td)) as z:proof=json.loads(z.read('content-review.json'))
                record=load(fetch(receipt,td))
                master=masters.get(pid+'-'+record['material_sha256'][:16]+'.zip')
                if (proof['checked'] and proof['key']==fingerprint and record['lesson']==pid
                    and record['content_sha256']==proof['text_sha256'] and master and master.get('digest')):
                    continue
            missing.append(pid)
    return missing

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
    samples=spec.get('samples',[spec.get('sample',ids[0])])
    if not samples or len(set(samples))!=len(samples) or not set(samples)<=set(ids):raise ValueError('Missing or repeated sample')
    if spec.get('only_missing'):
        outstanding=set(missing_editions(ids))
        print(f'{len(outstanding)} of {len(ids)} lessons still need this paper and glossary edition.')
        ids=[pid for pid in ids if pid in outstanding or pid in samples]
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        print('current_tools='+('true' if spec.get('only_missing') else 'false'),file=out)
        print('samples='+json.dumps(samples),file=out)
        print('lessons='+json.dumps([i for i in all_ids if i in ids and i not in samples]),file=out)

def wait_previous():
    for rid in load(SPEC).get('after_runs',[]):
        while True:
            p=subprocess.run(['gh','run','view',str(int(rid)),'--json','status','--jq','.status'],text=True,stdout=subprocess.PIPE,check=True)
            if p.stdout.strip()=='completed':break
            time.sleep(50)

def divide_pool(lessons,busy,active_lessons):
    early_limit=max(0,20-busy);late_limit=20-early_limit
    if not busy:return lessons,[],20,1
    if not early_limit:return [],lessons,1,20
    # Give the two groups proportional work once the older jobs finish.
    # Leave passages whose first vocabulary draft is still running to the later group.
    goal=(len(lessons)*early_limit+19)//20
    immediate=[p for p in lessons if p not in active_lessons][:goal]
    selected=set(immediate)
    return immediate,[p for p in lessons if p not in selected],early_limit,late_limit

def admit():
    lessons=json.loads(os.environ['IELTS_REMAINING'])
    active=[];busy=0
    for rid in load(SPEC).get('after_runs',[]):
        prior=json.loads(subprocess.check_output(['gh','run','view',str(int(rid)),'--json','status,jobs']))
        if prior['status']=='completed':continue
        drafts=[j for j in prior['jobs'] if re.search(r'\(C\d+T\dP\d\)',j['name'])]
        if not drafts:
            busy=20;continue
        for job in drafts:
            if job['status']!='completed':
                busy+=1;active.append(re.search(r'C\d+T\dP\d',job['name'])[0])
    lanes=divide_pool(lessons,min(20,busy),set(active))
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        for field,value in zip(('immediate','deferred','immediate_limit','deferred_limit'),lanes):
            print(field+'='+json.dumps(value),file=out)
    print(f'{busy} earlier lesson jobs active. Starting up to {min(len(lanes[0]),lanes[2])} more now; up to 20 after that group finishes.')

def sync_notes():
    from lesson import PID,save
    import hashlib
    branch='codex/ielts-academic-reading'
    subprocess.run(['git','fetch','--quiet','--no-tags','--filter=blob:none','--depth=1','origin',branch],check=True)
    revision=subprocess.check_output(['git','rev-parse','FETCH_HEAD'],text=True).strip()
    def at_revision(path):
        return subprocess.check_output(['git','show',revision+':'+path.relative_to(REPO).as_posix()])
    summary=json.loads(at_revision(PROJECT/'审校/第10至1册正文与选词核对.json'))
    evidence=next(r for r in summary['lessons'] if r['lesson']==PID)
    paper_path=PROJECT/'原稿'/(PID+'.json');prep_path=PROJECT/'备课'/(PID+'.json')
    paper_data=at_revision(paper_path);prep_data=at_revision(prep_path)
    if (hashlib.sha256(paper_data).hexdigest(),hashlib.sha256(prep_data).hexdigest())!=(evidence['source_sha256'],evidence['vocabulary_prep_sha256']):
        raise ValueError('Paper or vocabulary source differs from the stored print collation for '+PID)
    paper=json.loads(paper_data);prep=json.loads(prep_data)
    sentences=[s for group in paper['paragraphs'] for s in group]
    if (paper['id']!=PID or prep['lesson']!=PID or not paper['source_status'].startswith('已逐篇') or
            not sentences or sentences!=[r['en'] for r in prep['rows']]):
        raise ValueError('The corrected source and teaching vocabulary do not refer to the same printed lesson')
    current_paper=load(paper_path)
    if current_paper.get('edition_scope') and current_paper['paragraphs']!=paper['paragraphs']:
        raise ValueError('An edited excerpt needs its own reviewed revision')
    if paper_path.read_bytes()!=paper_data:paper_path.write_bytes(paper_data)
    if prep_path.read_bytes()!=prep_data:prep_path.write_bytes(prep_data)
    for filename in ('早期册语境校订.json','逐篇语境重点-10至1.json'):
        path=PROJECT/'审校'/filename
        current=load(path)
        remote=json.loads(at_revision(path))
        if current.get(PID)==remote.get(PID):continue
        entry=remote.get(PID)
        if entry is None:
            current.pop(PID,None)
        else:
            anchors=((int(n),v['en']) for n,v in entry.items()) if isinstance(entry,dict) else ((v['sentence'],v['scope_en']) for v in entry)
            if not all(1<=n<=len(sentences) and sentences[n-1]==en for n,en in anchors):
                raise ValueError('New paper annotations refer to a different printed edition of '+PID)
            current[PID]=entry
        save(path,current)
    if os.getenv('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'],'a') as out:print('IELTS_NOTES_REVISION='+revision,file=out)

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
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['plan','wait','admit','sync-notes','cached','diagnosis']);a=ap.parse_args()
    if a.stage=='plan':plan()
    elif a.stage=='wait':wait_previous()
    elif a.stage=='admit':admit()
    elif a.stage=='sync-notes':sync_notes()
    elif a.stage=='cached':print(str(cached()).lower())
    else:diagnostics()
