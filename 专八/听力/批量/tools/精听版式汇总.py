"""汇集版式候选，全部用英文整句锚/源快照摘要，避免formal新增造成序号错位。
这里只产生待审候选，不能把无音频的布局报告当正式审核或发布许可。
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from 精听数据 import dump,sha
D=Path(__file__).resolve().parents[1]


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('roots',type=Path,nargs='+');ap.add_argument('--out',type=Path,default=D/'核验/精听版式预检');a=ap.parse_args();chosen={}
 for root in a.roots:
  for report in root.glob('*/版式预检.json'):chosen[report.parent.name]=report
 units=[]
 for pid,path in sorted(chosen.items()):
  result=json.loads(path.read_text());snapshot=path.parent/'source.json';d=json.loads(snapshot.read_text());sentences=d['sentences'];anchored=[]
  for k,f in result.get('split_findings',{}).items():
   s=sentences[int(k)-1]
   original=[x for x in result.get('original_problems',[]) if re.match(r'第 '+re.escape(str(k))+r' 句(?:$| )',x['label'])]
   sizing=any(any('一屏放不下或字太小' in message or '字号过小' in message for message in x['problems']) for x in original)
   if original and not sizing:continue  # 纯词注/字体出界不能靠拆短题干解决，保留在layout_problems交编辑修释义。
   item={'en':s['en'],'zh':s['zh'],'ordinal_hint':int(k),**f}
   if f.get('candidate'):
    plan=f['candidate'];ats=plan['at'] if isinstance(plan['at'],list) else [plan['at']];cuts=[0,*[s['en'].index(x) for x in ats],len(s['en'])]
    zs=[s['zh']]*(len(cuts)-1) if plan['zh']=='整句' else plan['zh'];missing=[]
    for i,(x,y) in enumerate(zip(cuts,cuts[1:]),1):
     if not any(x<=w['sp'][0][0]<y for w in s['w']):missing.append({'part':i,'en':s['en'][x:y],'zh':zs[i-1]})
    item['need_contextual_vocabulary']=missing
   anchored.append(item)
  directory=a.out/pid;directory.mkdir(exist_ok=True,parents=True)
  dump(directory/'source.json',d);dump(directory/'版式预检.json',result)
  record={'id':pid,'layout_only':True,'not_audio_approved':True,'source_sha256':sha(snapshot),
          'source_content_sha256':hashlib.sha256(json.dumps([(s['en'],s['zh'],s['w']) for s in sentences],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
          'apply_rule':'必须按en整句完全一致匹配；ordinal_hint只供阅读定位；新增formal后不可按旧编号直接覆盖。',
          'proposed_display_title':result.get('proposed_display_title'),'proposed_names':result.get('proposed_names',[]),
          'candidates':anchored,'layout_problems':result.get('final_problems',[]),'error':result.get('error'),
          'word_type_suggestions':[{'en':s['en'],'h':w['h'],'old':w['t'],'proposed':'word'} for s in sentences for w in s['w'] if w['t']=='phr' and ' ' not in w['h']]}
  dump(directory/'分屏英文锚点候选.json',record)
  units.append({'id':pid,'ok':result.get('ok',False),'screens':len(result.get('shots',[])),
                'split_sentences':len(anchored),'need_words':sum(len(x.get('need_contextual_vocabulary',[])) for x in anchored),
                'problems':len(result.get('final_problems',[])),'error':result.get('error'),
                'report':str((directory/'分屏英文锚点候选.json').relative_to(a.out))})
 dump(a.out/'汇总.json',{'layout_only':True,'not_production_review':True,'expected_units':45,'completed_units':len(units),
                        'source_snapshot_warning':'源快照可能早于formal及最终ASR修复；这里只做提早发现版式问题。最终输入必须重新prepare/stills与原音核验。',
                        'units':units})
 print('已归档',len(units),'单元；候选仍需语义/原声/正式冻结后核验。')


if __name__=='__main__':main()
