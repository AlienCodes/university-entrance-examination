"""登记root已核定的2015/2021疑词音证；不重建整稿、不覆盖已合入正式说明。"""
import json,re,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(y):
 p=B/f'核验/疑文复识别/{y}.json';return {'file':str(p.relative_to(B)),'sha256':sha(p)}
def add(unit,query,decision,evidence):
 entries=unit.setdefault('audio_adjudications',[])
 entries[:]=[x for x in entries if x['query']!=query]
 entries.append({'query':query,'decision':decision,'evidence':evidence,'status':'依root裁决登记，不冒称机器转写无误'})
for year in [2015,2021]:
 p=B/f'译注草稿/{year}.json';old=p.read_text();d=json.loads(old);u={x['id'].split('-')[-1]:x for x in d['units']};r=ref(year)
 if year==2015:
  add(u['A'],'da da DA','保留原页节奏拟声；root独立Whisper190—215s确识Dada多次，是真实节奏模仿，不能因为主ASR漏识而删声。',[{**r,'query':'da da DA','window':[190,215]}, {'root_adjudication':'原音确有节奏模仿，保留。'}])
  add(u['B2'],'Why some','原页、主ASR与独立Whisper1330.26—1340.9s均无do；保持真实Why some，不擅改英语语法。',[{**r,'query':'Why some','window':[1330.26,1340.9]}])
  for key in ['A','B2']:
   previous=u[key].get('待核',[])
   assert all(('da da' in x or '节奏' in x or '第9题' in x or 'Why some' in x) for x in previous),previous
   u[key]['已解决待核']=list(dict.fromkeys(u[key].get('已解决待核',[])+previous));u[key]['待核']=[]
 else:
  add(u['A'],'civil rights of the 1960s','解析、主ASR、独立Whisper469.12—480.96s均没有movement；按实际表达保留，不增词。',[{**r,'query':'civil rights of the 1960s','window':[469.12,480.96]}])
  add(u['B2'],'divided into sections','独立Whisper1287.22—1298.66s与主ASR均明确into sections；排除解析误印in dissections。',[{**r,'query':'divided into sections','window':[1287.22,1298.66]}])
  add(u['B2'],'Emm','保留解析应声表示；独立Whisper1315—1336s识别(humming)，root确认有真实低声应和。应声不是可凭长度估时的词，不补造独立词时刻。',[{**r,'query':'Emm','window':[1315,1336]}, {'root_adjudication':'有humming声，不删除真实应声；可与前后完整话轮合并核边界。'}])
  target=next(s for s in u['B1']['sentences'] if not s.get('instruction_source') and 'has written a number of memoir' in s['en'])
  before=target['en'];target['en']=before.replace('memoirs and criticisms','memoirs and criticism')
  # 该句词条romanticism位于改动前；仍逐条按实际字符重新确认，不靠旧长度假设。
  for w in target['w']:
   for a,z in w['sp']:assert 0<=a<z<=len(target['en'])
  p2=B/'说明语句/局部复识别/2021/intro_memoirs.json';q=json.loads(p2.read_text())
  assert len(q['recognitions'])==2 and all('memoirs and criticism.' in x['text'] for x in q['recognitions'])
  add(u['B1'],'memoirs and criticism','采用两组聚焦错位Parakeet稳定读法memoirs(复数) and criticism(单数)。主ASR把criticism识别为复数；独立Whisper把memoirs识别为单数。分歧完整保留，不称双模型一致。',[{'file':str(p2.relative_to(B)),'sha256':sha(p2),'windows':[x['window'] for x in q['recognitions']],'texts':[x['text'] for x in q['recognitions']]},{**r,'query':'memoirs and criticisms','secondary':'memoir and criticism','note':'独立Whisper与主ASR有词尾分歧。'}])
  for key in ['A','B1','B2']:
   previous=u[key].get('待核',[])
   assert all(any(v in x for v in ['civil rights','memoir','dissections','Emm']) for x in previous),previous
   u[key]['已解决待核']=list(dict.fromkeys(u[key].get('已解决待核',[])+previous));u[key]['待核']=[]
 # 全句真实字符span及中文再检查；不把以上音证裁决当作整稿发布批准。
 for unit in d['units']:
  for i,s in enumerate(unit['sentences']):
   assert s['en'] and re.search('[\u4e00-\u9fff]',s['zh']) and s['w'],(year,unit['id'],i)
   occupied=[]
   for w in s['w']:
    for a,z in w['sp']:
     assert 0<=a<z<=len(s['en']),(year,unit['id'],i,w)
     assert all(z<=c or a>=v for c,v in occupied),(year,unit['id'],i,'overlap')
     occupied.append((a,z))
 assert p.read_text()==old,(year,'并发修改，请重新读稿')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(year,'音证逐项登记，真实span复查通过')
