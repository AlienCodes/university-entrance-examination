"""按完整当前EN将人工逐屏语义方案合到2010—2015译注母稿。

仅增加/精确替换manual_splits、指定保义调序中文、真实内容词注。绝不改EN/录音时间。
默认只核，--apply才写；已合当前方案可幂等重跑。无句号序号定位回退。
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path
BATCH=Path(__file__).resolve().parents[1]
AUDIT=BATCH/'核验/2010-2015-长句分屏语义预审.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def check_sp(s):
 spans=[]
 for w in s['w']:
  assert w['h'].strip() and w['m'].strip()
  for a,b in w['sp']:
   assert 0<=a<b<=len(s['en']) and s['en'][a:b].strip()
   assert a==0 or not(s['en'][a-1].isalnum() and s['en'][a].isalnum())
   assert b==len(s['en']) or not(s['en'][b-1].isalnum() and s['en'][b].isalnum())
   assert all(b<=x or a>=y for x,y in spans),(s['en'],w,spans)
   spans.append((a,b))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 audit=json.loads(AUDIT.read_text());records=audit['records'];assert len(records)==95
 files={};report=[]
 for year in range(2010,2016):
  p=BATCH/f'译注草稿/{year}.json';obj=json.loads(p.read_text());files[year]=(p,obj,sha(p))
 for r in records:
  year=int(r['unit'][:4]);p,obj,before=files[year]
  units=[u for u in obj['units'] if u['id']==r['unit']];assert len(units)==1;u=units[0]
  matches=[s for s in u['sentences'] if s['en']==r['en']];assert len(matches)==1,(r['unit'],r['en']);s=matches[0]
  assert s.get('role')!='question','Question只能由考试负责人同步'
  assert s['zh'] in [r['current_zh'],r['new_whole_zh']],(r['unit'],s['zh'],r['current_zh'])
  new_notes=[]
  for w in r['add_vocab']:
   if w not in s['w']:
    assert not any(any(a<y and b>x for x,y in v['sp']) for a,b in w['sp'] for v in s['w']),(r['unit'],w)
    s['w'].append(copy.deepcopy(w));new_notes.append(w)
  s['zh']=r['new_whole_zh'];check_sp(s)
  at=r['at'];ats=[at] if isinstance(at,str) else at
  cuts=[0]+[s['en'].index(x) if s['en'].count(x)==1 else -1 for x in ats]+[len(s['en'])]
  assert -1 not in cuts and cuts==sorted(cuts) and len(set(cuts))==len(cuts)
  assert ''.join(r['zh'])==s['zh'] and len(r['zh'])==len(cuts)-1
  for a,b in zip(cuts,cuts[1:]):
   assert any(a<=x<y<=b for w in s['w'] for x,y in w['sp']),(r['unit'],s['en'][a:b])
   assert not any(x<b and y>a and not (a<=x<y<=b) for w in s['w'] for x,y in w['sp'])
  entry={'en':s['en'],'at':at,'zh':r['zh'],'evidence':'核验/2010-2015-长句分屏语义预审.json；逐屏中英/词注人工语义审查，换屏另核真实词首与原音guard；不得伪称纯静音。'}
  same=[j for j,v in enumerate(u.get('manual_splits',[])) if v['en']==s['en']];assert len(same)<=1
  if same:u['manual_splits'][same[0]]=entry
  else:u.setdefault('manual_splits',[]).append(entry)
  report.append({'unit':u['id'],'en':s['en'],'at':at,'zh':r['zh'],'whole_zh_change':r['whole_zh_change'],'old_whole_zh':r['current_zh'] if r['whole_zh_change'] else None,'decision':r['decision'],'added_notes':new_notes,'reanchor':r['reanchor']})
 for meta in audit.get('metadata_updates',[]):
  year=int(meta['unit'][:4]);u=next(u for u in files[year][1]['units'] if u['id']==meta['unit'])
  u['names']=list(dict.fromkeys(u.get('names',[])+meta.get('names',[])))
 output={'status':'checked','apply':args.apply,'audit_sha256':sha(AUDIT),'records':report,'files':[],'en_and_audio_time_unchanged':True}
 for year,(p,obj,before) in files.items():
  # 复读最新母稿防并发：任一字节变化即中断，不覆盖其他代理写入。
  assert sha(p)==before,('母稿并发变化',p)
 if args.apply:
  for year,(p,obj,before) in files.items():
   dump(p,obj);output['files'].append({'year':year,'file':str(p.relative_to(BATCH)),'before_sha256':before,'after_sha256':sha(p)})
  output['status']='applied';dump(BATCH/'核验/2010-2015-语义分屏落稿核验.json',output)
 print(json.dumps({'status':output['status'],'records':len(report),'units':len({r['unit'] for r in report}),'whole_zh_reorders':sum(r['whole_zh_change'] for r in report),'added_notes':sum(len(r['added_notes']) for r in report),'en_and_audio_time_unchanged':True},ensure_ascii=False))
if __name__=='__main__':main()
