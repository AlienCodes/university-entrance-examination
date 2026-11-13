#!/usr/bin/env python3
"""英文逐句完全相同时更新译注/标题/整名，不重做或挪动任何音频词锚。"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

B = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def project_manual_splits(d,contract):
    """从母稿EN锚派生当前句号计划，旧ordinal不作为后备。"""
    if 'manual_splits' not in d:return
    previous=copy.deepcopy(d.get('splits',{}));d['splits']={}
    d['splits']=contract.resolve_manual_splits(d)
    checks=[]
    for number,plan in d['splits'].items():
        s=d['sentences'][int(number)-1]
        for at in plan['at'] if isinstance(plan['at'],list) else [plan['at']]:
            cut=s['en'].index(at)
            try:
                actual=contract.first_aligned_word(s.get('word_alignment',[]),s['en'],cut)
                checks.append({'sentence':int(number),'at':at,'real_word_anchor':True,'char':actual['char'],'start':actual['start'],'end':actual['end']})
            except AssertionError as error:
                checks.append({'sentence':int(number),'at':at,'real_word_anchor':False,'reason':str(error)})
    d['manual_split_anchor_check']={'all_cut_starts_have_real_word_anchors':all(x['real_word_anchor'] for x in checks),'cuts':checks,
        'note':'仅据实际word_alignment检查，不为缺首词跳到后词；最终仍须编译音频/停顿及在线图审。'}
    if previous!=d['splits']:d['manual_split_projection']={'rule':'母稿manual_splits完整EN唯一映射；舍弃旧ordinal差异','previous_explicit_splits':previous,'current_keys':list(d['splits'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('years',type=int,nargs='+');p.add_argument('--unit',action='append');p.add_argument('--split-record',type=Path,action='append',default=[]);args=p.parse_args()
    spec=importlib.util.spec_from_file_location('tem8_annotation_contract',B/'tools/精听数据.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
    split_records=[]
    for path in args.split_record:
        obj=json.loads(path.read_text('utf-8'))
        if isinstance(obj,dict) and obj.get('units'):
            for unit in obj['units']:
                for row in unit.get('split_records',[]):split_records.append({'id':unit['id'],'en':row['en'],**row.get('plan',row)})
        else:split_records.extend(obj.get('split_records',[]) if isinstance(obj,dict) else obj)
    for year in args.years:
        path=B/f'译注草稿/{year}.json';raw=path.read_bytes();mother=json.loads(raw)
        for source in mother['units']:
            if args.unit and source['id'] not in args.unit:continue
            dest=B/'精听数据'/f"{source['id']}.json"
            if not dest.exists():
                print(json.dumps({'id':source['id'],'state':'no_exported_input'},ensure_ascii=False));continue
            d=json.loads(dest.read_text('utf-8'));old_en=[s['en'] for s in d['sentences']];new_en=[s['en'] for s in source['sentences']]
            lock=B/'核验'/f"{source['id']}-源文审核.json"
            if lock.exists() and json.loads(lock.read_text('utf-8')).get('status')=='source-approved':
                same=(d['title']==source['title'] and d.get('names',[])==source.get('names',[]) and d.get('manual_splits',[])==source.get('manual_splits',[]) and
                      [{k:s[k] for k in ('en','zh','w')} for s in d['sentences']]==[{k:s[k] for k in ('en','zh','w')} for s in source['sentences']])
                print(json.dumps({'id':source['id'],'state':'source_approved_unchanged_preserved' if same else 'source_approved_locked_changes_require_revocation'},ensure_ascii=False));continue
            if old_en!=new_en:
                print(json.dumps({'id':source['id'],'state':'English_changed_requires_alignment_rerun'},ensure_ascii=False));continue
            before=contract.content_sha(d)
            times_before=digest([(s['start'],s['end'],s.get('word_alignment'),s.get('words')) for s in d['sentences']])
            for key in ('title','names','genre','summary','source_title','source_refs','原音核实记录','manual_splits'):
                if key in source:d[key]=copy.deepcopy(source[key])
            for target,s in zip(d['sentences'],source['sentences']):
                target['zh']=s['zh'];target['w']=copy.deepcopy(s['w'])
            applied=[]
            for row in split_records:
                if row['id']!=source['id']:continue
                matches=[i for i,s in enumerate(d['sentences'],1) if s['en']==row['en']]
                if len(matches)!=1:raise ValueError(('manual split must have unique full EN anchor',row))
                n=matches[0]
                if isinstance(row.get('zh'),list) and ''.join(row['zh'])!=d['sentences'][n-1]['zh']:
                    raise ValueError(('manual split Chinese must reconstruct current whole translation',source['id'],n))
                d.setdefault('splits',{})[str(n)]={k:copy.deepcopy(row[k]) for k in ('at','zh','无停顿') if k in row}
                applied.append({'sentence':n,'en':row['en'],'at':row['at']})
            assert times_before==digest([(s['start'],s['end'],s.get('word_alignment'),s.get('words')) for s in d['sentences']])
            project_manual_splits(d,contract)
            d['annotation_refresh']={'mother':f'译注草稿/{year}.json','mother_sha256':hashlib.sha256(raw).hexdigest(),'english_sequence_sha256':digest(new_en),'timing_fingerprint_unchanged':times_before,'previous_content_sha256':before,'manual_splits_by_exact_EN':applied,'note':'只刷新英文完全相同的译注/标题/整名；所有原音时刻、窗口和ASR绑定逐字保留。'}
            d['review']={'status':'draft','source':'译注刷新使旧审校摘要失效；须重新审核现注释/画面','content_sha256':contract.content_sha(d)}
            contract.validate(d,draft=True)
            assert path.read_bytes()==raw,'母稿并发变化，拒绝发布旧注释刷新'
            dest.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'id':source['id'],'state':'annotations_refreshed_time_anchors_unchanged','mother_sha256':d['annotation_refresh']['mother_sha256'],'words':sum(len(s['w']) for s in d['sentences'])},ensure_ascii=False))


if __name__=='__main__':main()
