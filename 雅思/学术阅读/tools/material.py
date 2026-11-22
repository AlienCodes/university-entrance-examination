"""Fingerprint what a learner sees and hears, including per-sentence headword overrides."""
import hashlib
import json
from pathlib import Path


def verify_original(project,pid,lesson_file=None):
    original=json.loads((project/'原稿'/(pid+'.json')).read_text())
    text=(lesson_file or project/'篇目'/pid/'双语精读.tsv').read_text().strip()
    groups=[[line.split('\t',1)[0] for line in paragraph.splitlines()] for paragraph in text.split('\n\n')]
    if groups!=original['paragraphs']:
        raise ValueError(f'{pid}: English text or paragraph breaks differ from the verified academic paper')


def source_key(text, meta, split, printed_test):
    rows=[]
    for i,line in enumerate((line for line in text.splitlines() if line),1):
        en,zh,*annotations=line.split('\t')
        terms=[]
        for n,annotation in enumerate(annotations):
            form,meaning=annotation.split('|')
            head=meta.get('row_lemmas',{}).get(f'{i}.{n}',meta.get('lemmas',{}).get(form,form.lower()))
            terms.append([form,head,meaning])
        rows.append([en,zh,terms])
    display=[meta.get(k) for k in ('id','book','test','passage','title','title_zh','genre','header')]
    names=sorted(set(name for name in meta.get('zh_names',[]) if name in text))
    items=[display,printed_test,rows,split,names,meta.get('pronunciation',{}),[i for i,l in enumerate(text.splitlines()) if not l]]
    encoded=json.dumps(items,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def current_key(project,pid):
    path=project/'篇目'/pid
    original=json.loads((project/'原稿'/(pid+'.json')).read_text())
    meta=json.loads((path/'篇目信息.json').read_text())
    cuts=json.loads((path/'分屏.json').read_text()).get(pid,{}) if (path/'分屏.json').is_file() else {}
    return source_key((path/'双语精读.tsv').read_text(),meta,cuts,original.get('printed_test',original['test']))


def legacy_inputs_match(archive,project,pid):
    folder=project/'篇目'/pid
    original=json.loads((project/'原稿'/(pid+'.json')).read_text())
    printed=original.get('printed_test',original['test'])
    cuts=json.loads((folder/'分屏.json').read_text()).get(pid,{}) if (folder/'分屏.json').is_file() else {}
    actual=json.loads(archive.read('source/分屏核对.json'))['cuts']
    planned={(int(n),part): (anchor,zh) for n,split in cuts.items() for part,(anchor,zh) in enumerate(zip(split['at'],split['zh'][1:]),2)}
    if len(planned)!=len(actual):return False
    for row in actual:
        point=planned.get((row['sentence'],row['part']))
        if point is None or not row['en'].startswith(point[0]) or row['zh']!=point[1]:return False
    old_text=archive.read('source/双语精读.tsv').decode()
    old_meta=json.loads(archive.read('source/篇目信息.json'))
    return current_key(project,pid)==source_key(old_text,old_meta,cuts,printed)
