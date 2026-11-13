#!/usr/bin/env python3
"""按明确音证清单采纳真实局部ASR；只生成独立候选，不动主ASR/原音。"""
import argparse
import hashlib
import json
from pathlib import Path

B=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifests',type=Path,nargs='+');args=p.parse_args();groups={}
    for path in args.manifests:
        obj=json.loads(path.read_text('utf-8'));groups.setdefault(obj['year'],[]).append((path,obj))
    for year,manifests in groups.items():
        prep=json.loads((B/f'预处理/{year}/原音准备.json').read_text('utf-8'));out=B/f'核验/补词锚/{year}';patches=[]
        for manifest,obj in manifests:
            assert obj['canonical_source_sha256']==prep['canonical']['sha256'],'局部采纳清单来自不同音源'
            for item in obj['patches']:
                assert item.get('decision','').strip(),'须有明确的双模型/人工音证裁决，不能自动采纳未核ASR'
                evidence=(B/item['evidence_ref']).resolve();assert evidence.is_relative_to(B.resolve())
                assert sha(evidence)==item['evidence_sha256'],'局部ASR证据哈希不符'
                data=json.loads(evidence.read_text('utf-8'))
                for key in item['pointer'].strip('/').split('/'):
                    data=data[int(key)] if isinstance(data,list) else data[key]
                words=data;a,z=item['window'];assert words and 0<=a<z<=prep['canonical']['duration']+.1
                assert all(a-.1<=w[1]<w[2]<=z+.1 for w in words)
                assert all(x[1]<=y[1] for x,y in zip(words,words[1:]))
                patches.append({**item,'words':words,'manifest':manifest.name,'manifest_sha256':sha(manifest)})
        patches.sort(key=lambda x:x['window'][0]);assert all(x['window'][1]<=y['window'][0] for x,y in zip(patches,patches[1:])),'采纳窗口重叠，须由音证审校者先选完整窗口'
        requested={o.get('base_asr_ref') for _,o in manifests if o.get('base_asr_ref')}
        assert len(requested)<=1,'同年采纳清单不能要求不同基础ASR'
        baseline=(B/next(iter(requested))).resolve() if requested else next((x for x in (out/'优选识别.json',out/'识别.json',B/f'预处理/{year}/识别.json') if x.exists()))
        assert baseline.is_relative_to(B.resolve())
        for _,o in manifests:
            if o.get('base_asr_sha256'):assert sha(baseline)==o['base_asr_sha256']
        original=json.loads(baseline.read_text('utf-8'));base_sha=sha(baseline);combined=original
        removed_all=set();additions=[]
        for item in patches:
            a,z=item['window']
            indices=item.get('replace_original_asr_indices')
            if indices is not None:
                assert indices==list(range(indices[0],indices[-1]+1)) and 0<=indices[0]<=indices[-1]<len(original)
                removed=[(i,original[i]) for i in indices]
            else:removed=[(i,w) for i,w in enumerate(original) if a<=w[1]<z]
            assert not removed_all.intersection(i for i,_ in removed),'两个采纳片段争抢同一原ASR词'
            item['removed_previous_indices']=[i for i,_ in removed];item['removed_previous_words']=[w for _,w in removed]
            removed_all.update(i for i,_ in removed);additions.extend(item['words'])
        combined=[w for i,w in enumerate(original) if i not in removed_all]+additions;combined.sort(key=lambda w:(w[1],w[2]))
        assert sha(baseline)==base_sha,'处理时基础候选被并发改变，拒绝旧候选'
        save(out/'已核局部识别.json',combined)
        save(out/'已核局部采纳记录.json',{'year':year,'canonical_source_sha256':prep['canonical']['sha256'],
            'baseline':str(baseline.relative_to(B)),'baseline_sha256':base_sha,'patches':patches,
            'status':'仅按已明确音证裁决恢复真实局部词锚；母稿/主ASR/原音未改，非成品批准。'})
        save(out/'已核局部ASR核验.json',{'year':year,'canonical_sha256':prep['canonical']['sha256'],
            'source_unchanged':True,'word_end_estimate_seconds':.08,'script_sha256':sha(__file__),
            'evidence':f'核验/补词锚/{year}/已核局部采纳记录.json','evidence_sha256':sha(out/'已核局部采纳记录.json'),
            'status':'已核局部逐词识别合并候选，最终字幕/音轨/画面审校尚须登记。',
            'outputs':{'识别.json':{'sha256':sha(out/'已核局部识别.json')}}})
        print(json.dumps({'year':year,'patches':len(patches),'words':len(combined)},ensure_ascii=False))


if __name__=='__main__':main()
