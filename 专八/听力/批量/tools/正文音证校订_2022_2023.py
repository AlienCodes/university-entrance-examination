"""仅按两路局部原音证据订正2022/2023母稿body；保留formal/question及新版词注。
旧EN/新EN完整登记，版式锚必须由theme按新EN重新匹配。
"""
import json,re,copy,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];O=B/'核验/正文异文复核'
CHANGES=[
(2022,'B1','underserved','improving lives in under-served','improving lives and under-served','虽然我在课堂上任教的年头不算很多，但我致力于改善人们生活、改善服务不足社区状况的决心，从未动摇。'),
(2022,'B1','grants_number','Last year, all grants','Last year, our grants','去年，我们的资助共支持了6000多名教育工作者，惠及18.6万多名学生。'),
(2022,'B2','emitted_light','a lot of the light emitted','a lot of light emitted',None),
(2023,'A','and_in','sense organ and another','sense organ in another','联觉是指一种感觉器官接收到的刺激，也在另一种感觉器官中产生感受的体验，例如色听联觉。'),
(2023,'A','when_where','dissonance when the name','dissonance where the name','如果你和大多数人一样，面对用另一种颜色墨水印出的颜色名称时，会经历片刻的认知失调。'),
(2023,'B2','time_majority','and a majority of this time','and the majority of this time',None),
(2023,'B2','specific_culture','about specific culture','about a specific culture',None),
(2023,'B2','travel_lists','I think travel list','I think a travel list',None),
(2023,'B2','validation','experience or being in a place','experience of being in a place','身处某个地方的亲身经历中，有太多值得学习的东西。'),
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def remap(old,new,w,edit_a,edit_z,delta):
 out=copy.deepcopy(w)
 for term in out:
  spans=[]
  for a,z in term['sp']:
   surface=old[a:z];matches=list(re.finditer(re.escape(surface),new));assert matches,(surface,new)
   expected=a+(delta if a>=edit_z else 0);m=min(matches,key=lambda t:abs(t.start()-expected));spans.append(list(m.span()))
  term['sp']=spans
 return out
rows=[]
prior=O/'正文订正旧新EN.json';previous=json.loads(prior.read_text()).get('changes',[]) if prior.exists() else []
for year in [2022,2023]:
 p=B/f'译注草稿/{year}.json';text=p.read_text();d=json.loads(text)
 protected=[copy.deepcopy(s) for u in d['units'] for s in u['sentences'] if s.get('instruction_source') or s.get('role')=='question']
 for y,uid,case,oldfrag,newfrag,zh in CHANGES:
  if y!=year:continue
  ep=O/str(year)/(case+'.json');ev=json.loads(ep.read_text());rr=ev['recognitions']
  if len(rr)<2:print('WAIT',year,case,flush=True);continue
  assert {x['model'] for x in rr}=={'parakeet','whisper'}
  unit=next(u for u in d['units'] if u['id']==f'{year}-{uid}')
  ss=[s for s in unit['sentences'] if not s.get('instruction_source') and s.get('role')!='question' and (oldfrag in s['en'] or newfrag in s['en'])];assert len(ss)==1,(year,case,'整句锚不唯一')
  s=ss[0];old=s['en'];record=next((x for x in previous if x['year']==year and x['case']==case),None)
  if oldfrag in old:
   a=old.index(oldfrag);z=a+len(oldfrag);new=old[:a]+newfrag+old[z:];s['w']=remap(old,new,s['w'],a,z,len(newfrag)-len(oldfrag));s['en']=new
   if zh:s['zh']=zh
  else:new=old
  evidence={'file':str(ep.relative_to(B)),'sha256':sha(ep),'source_sha256':ev['source_sha256'],'canonical_sha256':ev['canonical_sha256'],'windows':[r['window'] for r in rr],'texts':{r['model']:r['text'] for r in rr}}
  decision='两种错位上下文模型对实际口述一致；只订正本句明确印误/异文，不为语法修音。'
  if case=='specific_culture':decision='主ASR与聚焦Parakeet均为a specific culture；Whisper为the specific culture，两路均确认有冠词。采用最稳定的a并完整保留冠词分歧，不声称双模型逐字一致。'
  item={'year':year,'unit':unit['id'],'case':case,'old_en':record['old_en'] if record else old,'new_en':new,'new_zh':s['zh'],'evidence':evidence,'decision':decision};rows.append(item)
  hist=unit.setdefault('body_audio_corrections',[]);hist[:]=[x for x in hist if x['case']!=case];hist.append(item)
 for u in d['units']:
  for s in u['sentences']:
   assert s['en'] and s['zh'] and s['w'];used=[]
   for w in s['w']:
    for a,z in w['sp']:assert 0<=a<z<=len(s['en']);assert all(z<=c or a>=e for c,e in used);used.append((a,z))
 assert protected==[s for u in d['units'] for s in u['sentences'] if s.get('instruction_source') or s.get('role')=='question'],'正式说明和题干不能改变'
 assert p.read_text()==text,(year,'并发写入，需重读')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
O.mkdir(exist_ok=True);prior.write_text(json.dumps({'changes':rows,'rule':'按整句旧EN/新EN重新匹配版式候选；不以旧句序硬套','formal_question_unchanged':True},ensure_ascii=False,indent=2)+'\n')
print('落稿明确原音异文',len(rows),'处，全文sp/保护对象校验通过')
