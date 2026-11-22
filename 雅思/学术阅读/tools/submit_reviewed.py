"""Archive sealed lesson materials and send changed screen editions to GitHub Actions."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from material import current_key,verify_original
from release_assets import inventory

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / '雅思/学术阅读'
READER = '雅思/学术阅读/tools/audio_lesson.py'
INPUTS = {
    'text_sha256':'双语精读.tsv',
    'metadata_sha256':'篇目信息.json',
    'split_sha256':'分屏.json',
}
FILES = [*INPUTS.values(),'content-review.json']


def read(path):
    return json.loads(path.read_text())


def command(*args):
    return subprocess.check_output(args,cwd=REPO,text=True)


def approved(source):
    proof=read(source/'content-review.json')
    if proof.get('mobile_layout',{}).get('issues')!=0 or not proof.get('checked'):
        raise ValueError(f'Unresolved editorial or visual review for {source.name}')
    for key,name in INPUTS.items():
        file=source/name
        if not file.is_file() or (key in proof and hashlib.sha256(file.read_bytes()).hexdigest()!=proof[key]):
            raise ValueError(f'{source.name}: {name} differs from the review')
    return proof


def audio_for(folder,assets,readers):
    sentences=[line.split('\t')[0] for line in (folder/'双语精读.tsv').read_text().splitlines() if line]
    pronunciation=read(folder/'篇目信息.json').get('pronunciation',{})
    for code in readers:
        inputs=json.dumps([sentences,pronunciation,code],ensure_ascii=False).encode()
        key=hashlib.sha256(inputs).hexdigest()[:16]
        name=f'{folder.name}-audio-{key}.zip'
        if name in assets:
            return name
    return None


def update_book_index(book):
    ids=[f'C{book}T{test}P{passage}' for test in range(1,5) for passage in range(1,4)]
    if not all((PROJECT/'篇目'/pid/'content-review.json').is_file() for pid in ids):
        return None
    rows=[]
    for pid in ids:
        folder=PROJECT/'篇目'/pid
        file=folder/'双语精读.tsv'
        proof=read(folder/'content-review.json')
        text_hash=hashlib.sha256(file.read_bytes()).hexdigest()
        if text_hash!=proof['text_sha256']:
            raise ValueError('Unsealed lesson in editorial index: '+pid)
        lines=[line.split('\t') for line in file.read_text().splitlines() if line]
        rows.append(dict(lesson=pid,title=read(folder/'篇目信息.json')['title'],
                         material_sha256=current_key(PROJECT,pid),translation_sha256=text_hash,
                         reading_units=len(lines),annotations=sum(len(line)-2 for line in lines),
                         evidence=f'篇目/{pid}/content-review.json'))
    index=PROJECT/'审校'/f'C{book}.json'
    contents=json.dumps(dict(book=book,lessons=rows),ensure_ascii=False,indent=1)+'\n'
    if index.is_file() and index.read_text()==contents:
        return None
    index.parent.mkdir(exist_ok=True)
    index.write_text(contents)
    return index


def submit(approved_folder,ids,part):
    if len(ids)!=len(set(ids)):
        raise ValueError('A lesson was requested twice')
    first,last=map(int,part.split('-'))
    for pid in ids:
        valid=re.fullmatch(r'C(\d+)T[1-4]P[1-3]',pid)
        if not valid or not last<=int(valid[1])<=first:
            raise ValueError(f'{pid} is outside the selected books')
        approved(approved_folder/pid)
        verify_original(PROJECT,pid,approved_folder/pid/'双语精读.tsv')

    tag='ielts-academic-cache-'+part
    revising=any((PROJECT/'篇目'/pid/'content-review.json').exists() for pid in ids)
    assets=set(inventory(tag)) if revising else set()
    history=command('git','log','-n','25','--format=%H','--',READER).splitlines() if revising else []
    readers=[command('git','show',rev+':'+READER) for rev in history]
    changed=[]
    queue=[]
    audio={}
    for pid in ids:
        source=approved_folder/pid
        target=PROJECT/'篇目'/pid
        if all((target/name).is_file() and (target/name).read_bytes()==(source/name).read_bytes() for name in FILES):
            continue
        old_key=current_key(PROJECT,pid) if (target/'content-review.json').is_file() else None
        target.mkdir(exist_ok=True)
        for name in FILES:
            shutil.copyfile(source/name,target/name)
        changed.append(target)
        if old_key==current_key(PROJECT,pid):
            continue
        queue.append(pid)
        if old_key:
            asset=audio_for(target,assets,readers)
            if asset:
                audio[pid]=asset
    if queue:
        file=REPO/'.github/ielts-series-render.json'
        plan=read(file)
        plan.update(part=part,lessons=queue,audio_assets=audio,revision=int(plan['revision'])+1)
        file.write_text(json.dumps(plan,ensure_ascii=False)+'\n')
        changed.append(file)
    if changed:
        for book in sorted({int(pid[1:pid.index('T')]) for pid in ids}):
            index=update_book_index(book)
            if index is not None:
                changed.append(index)
        files=[str(path.relative_to(REPO)) for path in changed]
        command('git','add','--',*files)
        command('git','commit','-qm','归档已核准的精读教材：'+', '.join(ids),'--',*files)
        command('git','push','origin','HEAD')
    print(json.dumps({'submitted':queue,'certified_audio':audio},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('approved_folder',type=Path)
    parser.add_argument('ids',nargs='+')
    parser.add_argument('--part',choices=['20-11','10-1'],default='20-11')
    args=parser.parse_args()
    gate=Path(command('git','rev-parse','--path-format=absolute','--git-path','ielts-submit.lock').strip())
    with gate.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        submit(args.approved_folder,args.ids,args.part)
