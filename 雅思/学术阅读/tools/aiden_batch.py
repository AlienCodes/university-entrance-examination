"""Select the two Bilibili series and admit only matching Aiden recordings."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from aiden_profile import IDENTITY, PAUSE_POLICY, verified_subject_terms
from editions import lesson_ids
from material import current_key, verify_original
from release_assets import fetch, inventory

ROOT=Path(__file__).resolve().parents[1]
BATCHES={'13-6':range(13,5,-1),'5-1':range(5,0,-1)}

def cached(pid,batch,include_illustration=False):
    # A worker can replace its per-lesson receipt while another worker reads the
    # edition. A new asset ID must be evaluated with its own digest and film.
    try:
        return cached_from_inventory(pid, batch, include_illustration)
    except subprocess.CalledProcessError as exc:
        if 'HTTP 404' not in str(exc.stderr):
            raise
        inventory.cache_clear()
        return cached_from_inventory(pid, batch, include_illustration)


def cached_from_inventory(pid,batch,include_illustration):
    stage='ielts-academic-aiden-cache-'+batch
    masters=inventory(stage); receipt=masters.get(pid+'-receipt.json')
    if not receipt or not receipt.get('digest'): return False
    with tempfile.TemporaryDirectory() as tmp:
        data=json.loads(fetch(receipt,tmp).read_text())
        if (not verified_subject_terms(pid,data) or data.get('narrator')!=IDENTITY or data.get('lesson')!=pid or data.get('speaker')!='Aiden'
                or data.get('pause_policy')!=PAUSE_POLICY or not data.get('verified_phrases')
                or not data.get('audio_sha256') or data.get('encoded_reference_sha256')!=data['audio_sha256']):
            return False
        if int(pid[1:pid.index('T')])<=10:
            from early_editor import key_for
            from early_plan import NOTES, valid_master
            key=key_for(ROOT,pid); teaching=inventory(NOTES).get(key+'-reviewed.zip')
            core_ok=bool(teaching and teaching.get('digest') and valid_master(pid,key,teaching,data,masters,tmp))
        else:
            key=current_key(ROOT,pid)
            asset=masters.get(f'{pid}-{key[:16]}.zip')
            core_ok=bool(data.get('material_sha256')==key and asset and asset.get('digest'))
        if not core_ok or not include_illustration or batch!='13-6':
            return core_ok
        from illustration_stage import cached_movie
        return bool(cached_movie(pid,data,masters,tmp))

def plan(batch):
    ids=lesson_ids(BATCHES[batch])
    if not len(set(ids))==len(ids)==(96 if batch=='13-6' else 60):raise ValueError('Invalid series size')
    for pid in ids:
        s=json.loads((ROOT/'原稿'/(pid+'.json')).read_text())
        if s['id']!=pid or not s['paragraphs']:raise ValueError('Missing paper '+pid)
    stage='ielts-academic-aiden-cache-'+batch
    try:
        inventory(stage)
    except subprocess.CalledProcessError as exc:
        if "http 404" not in (exc.stderr or "").lower():
            raise
        subprocess.run(['gh','release','create',stage,'--target',os.environ['GITHUB_SHA'],'--prerelease','--latest=false',
            '--title',f'剑桥雅思 {batch} · Aiden 逐篇制作存档','--notes','存放本批次核验通过的精读音轨、视频和恢复记录。'],check=True)
    outstanding=[pid for pid in ids if not cached(pid,batch,include_illustration=True)]
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:
        print('batch='+batch,file=out)
        print('pilot='+ids[0],file=out)
        print('remaining='+json.dumps([p for p in outstanding if p!=ids[0]]),file=out)
    print(f'{len(ids)-len(outstanding)} verified, {len(outstanding)} outstanding',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['plan','cached']);p.add_argument('batch',choices=BATCHES);p.add_argument('--lesson')
    p.add_argument('--with-illustration',action='store_true')
    a=p.parse_args()
    if os.getenv('IELTS_NARRATOR')!='Aiden':raise ValueError('Wrong narrator for this series')
    if a.mode=='plan':plan(a.batch)
    else:
        if a.lesson not in lesson_ids(BATCHES[a.batch]):raise ValueError('Outside series: '+str(a.lesson))
        print(str(cached(a.lesson,a.batch,include_illustration=a.with_illustration)).lower())
