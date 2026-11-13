"""仅将theme已逐项确认的5条人工语义表回存母稿manual_splits。
不导入自动候选，不碰2009或2024，不修改EN/译文/词注/任何原声时间。
"""
import copy,hashlib,importlib.util,json
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
paths=['核验/正文局部音证/2018-裁决.json','核验/2018长句分屏译文调整.json','核验/正文异文复核/2023-B1-人工分屏候选.json'];sources={x:json.loads((B/x).read_text()) for x in paths};rows=[]
for i,r in enumerate(sources[paths[0]]['manual_splits']):rows.append({'id':r['unit'],'en':r['en'],'at':r['candidate']['at'],'zh':r['candidate']['zh'],'source':paths[0],'pointer':f'/manual_splits/{i}'})
r=sources[paths[1]];rows.append({'id':r['unit'],'en':r['en_anchor'],'at':r['candidate']['at'],'zh':r['candidate']['zh'],'source':paths[1],'pointer':'/candidate'})
r=sources[paths[2]];rows.append({'id':r['id'],'en':r['en'],'at':r['candidate']['at'],'zh':r['candidate']['zh'],'source':paths[2],'pointer':'/candidate'})
assert len(rows)==5 and {r['id'] for r in rows}=={'2018-A','2018-B1','2018-B2','2023-B1'}
proof={'scope':'reading_theme明确确认的人工语义表，仅2018四条与2023-B1一条；几何复跑0问题，不将自动候选当人工表，不代替原音切屏核验。',
       'sources':[{'file':x,'sha256':sha(B/x)} for x in paths], 'records':copy.deepcopy(rows)}
proof_path=B/'核验/人工语义分屏来源快照.json';proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');proof_sha=sha(proof_path)
spec=importlib.util.spec_from_file_location('split_contract',B/'tools/精听数据.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
flat=[];files=[]
for year in [2018,2023]:
 p=B/f'译注草稿/{year}.json';raw=p.read_bytes();d=json.loads(raw);old=copy.deepcopy(d);before=sha(p)
 for r in rows:
  if not r['id'].startswith(str(year)):continue
  u=next(u for u in d['units'] if u['id']==r['id']);ss=[s for s in u['sentences'] if s['en']==r['en']];assert len(ss)==1,(r['id'],'完整EN锚失效或不唯一')
  assert ''.join(r['zh'])==ss[0]['zh'],(r['id'],'中文没有原样拼回最新母稿，禁止套旧计划')
  ats=r['at'] if isinstance(r['at'],list) else [r['at']]
  assert all(r['en'].count(a)==1 for a in ats),(r['id'],'切点锚不唯一')
  record={k:copy.deepcopy(r[k]) for k in ['en','at','zh']}
  record.update({'evidence':r['source']+' '+r['pointer']+'；人工语义已核且几何复跑0问题，换屏另核实际词首/停顿。',
       'evidence_ref':'核验/人工语义分屏来源快照.json','evidence_sha256':proof_sha,'original_source_ref':r['source'],'original_source_sha256':sha(B/r['source']),'original_source_pointer':r['pointer'],
       'approval_scope':'仅人工语义/几何分屏计划，不含任何音频时刻或生产批准。'})
  existing=u.setdefault('manual_splits',[]);matches=[x for x in existing if x['en']==r['en']]
  if matches:
   assert len(matches)==1 and all(matches[0][k]==record[k] for k in ['at','zh']),(r['id'],'已有同EN不同人工计划，必须人工处理冲突')
   existing[existing.index(matches[0])]=record
  else:existing.append(record)
  plans=contract.resolve_manual_splits(u);n=next(i for i,s in enumerate(u['sentences'],1) if s['en']==r['en']);assert plans[str(n)]['at']==r['at'] and plans[str(n)]['zh']==r['zh']
  flat.append({'id':r['id'],**record})
 # 除manual_splits外所有对象必须完全相同，涵盖EN、ZH、w、音频及原声词时。
 stripped=copy.deepcopy(d);oldstripped=copy.deepcopy(old)
 for obj in [stripped,oldstripped]:
  for u in obj['units']:u.pop('manual_splits',None)
 assert stripped==oldstripped,(year,'意外修改分屏以外字段')
 assert p.read_bytes()==raw,(year,'母稿并发变化，拒绝覆盖')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');files.append({'year':year,'file':str(p.relative_to(B)),'before_sha256':before,'after_sha256':sha(p),'manual_count':sum(len(u.get('manual_splits',[])) for u in d['units'])})
manifest={'split_records':flat,'scope':'5条已人工语义核过的计划已写母稿unit.manual_splits；按完整EN唯一定位，不按ordinal；不修改EN或任何原声时间。','mother_files':files,'protected_scope':'2009及2024均未读写；未采纳其余自动候选。','plan_count':len(flat),'evidence_snapshot':'核验/人工语义分屏来源快照.json','evidence_sha256':proof_sha}
out=B/'核验/人工语义分屏回存清单.json';out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('已回存',len(flat),'条人工语义计划：',[(x['id'],len(x['at']) if isinstance(x['at'],list) else 1) for x in flat]);print('flat manifest',out)
