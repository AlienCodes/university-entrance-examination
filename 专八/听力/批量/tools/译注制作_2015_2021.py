"""据已实看PDF页图及人工逐句译注表生成两年草稿。不是自动翻译器。
英文仍须root统一对录音、生成时间轴；真题源字词歧义会显式列出。"""
import json,re
from pathlib import Path
B=Path(__file__).resolve().parents[1]
fixes={
 2015:{'Im going':"I’m going",'youre only':'you’re only','And Ill bet':'And I’ll bet','reduc- . ing':'reducing','education’ What':'education. What','don’t bother, If':'don’t bother. If','Government over':'Government over','(D:':'(I):','(D):':'(I):','(1):':'(I):','(也 :.':'(I): ...','[7|/':'','from_a':'from a','so called':'so-called'},
 2021:{'[4)':'','academic: values':'academic values','massifi-cation':'massification','Sécond,”':'Second,','significant numbers: of':'significant numbers of','middle. and':'middle- and','government’ control':'government control','as audible, aS':'as audible, as','compose-in':'compose in','L would probably':'I would probably','\'=e =':'','‘when I':'when I','My last two books,.':'My last two books,','.For me':'For me','community 一':'community —','my books have not tended to be that narrative. ,':'my books have not tended to be that narrative.'}
}
def prepare(year):
 d=json.loads((B/f'原文候选/{year}.json').read_text());out=[]
 for u in d['units']:
  en=u['en']
  for a,b in fixes[year].items():en=en.replace(a,b)
  # 仅合并这两年已在页图核过的跨行断词；重建无需机器外部词典。
  joined={'meaning','expect','connected','reducing','tension','historians','different','surprised'}
  en=re.sub(r'(\w+)-[.\s]+(\w+)',lambda m:m[1]+m[2] if (m[1]+m[2]).lower() in joined else m[1]+'- '+m[2],en)
  en=re.sub(r'\s+',' ',en).strip()
  if year==2015:
   en=en.replace('Good afternoon. Theresa.','Good afternoon, Theresa.').replace('over there?” Now','over there?”\nNow')
   en=en.replace(' VS ', ' versus ')
  en=re.sub(r'\((?:I|T)\):\s*',lambda m:'\n'+m[0],en)
  # 原页有但OCR遗漏的换人标记，按已实看页图恢复，不凭语气猜。
  if year==2021:
   # 原PDF确有这两处书面差错，已下载原音ASR给出清晰对应；仍由root听核。
   en=en.replace('a number of memoir and criticism','a number of memoirs and criticisms')
   en=en.replace('divided in dissections','divided into sections')
   en=en.replace(': Good evening! : Now,','W: Good evening!\nM: Now,').replace(': I would probably','W: I would probably').replace(': Oh, that’s interesting.','M: Oh, that’s interesting.').replace(': I had a wonderful tutor,','W: I had a wonderful tutor,')
   en=en.replace('So I almost think of the sections more musically.', 'So I almost think of the sections more musically.\nM: Emm, Emm...')
   en=en.replace('=e =','').replace('Ha ha ha... Okay.','\nM: Ha ha ha... Okay.').replace('Pleasure.','\nW: Pleasure.')
   if u['id'].endswith('B2'):
    turns=[('In My Poets,','M:'),('I really think','W:'),('Could you tell us why?','M:'),('For me, poetry','W:'),('Another question.','M:'),('My last two books,','W:'),('And I’m interested','W:'),('Is this the reason','M:'),('I think a concluding','W:'),('Do you have a particular','M:'),('Well, you can get locked','W:')]
    for a,sp in turns:en=en.replace(a,'\n'+sp+' '+a)
  en=re.sub(r'\s+(?=[MW]:\s)', '\n', en)
  # 标点切句；保护缩写、书名内部既有标点；短答与问句独立保留。
  protected={}
  for i,m in enumerate(list(re.finditer(r'\b(?:U\.S\.|Ph\.D\.|Dr\.|Mr\.|Mrs\.|Ms\.)',en))):
   k=f'ABBR{i}TOKEN';protected[k]=m[0];en=en.replace(m[0],k)
  ss=[]
  for para in en.splitlines():
   parts=re.split(r'(?<=[.!?])\s+(?=[A-Z“(])',para.strip())
   for s in parts:
    for k,v in protected.items():s=s.replace(k,v)
    if s.strip():ss.append(s.strip())
  out.append({'id':u['id'],'title':u['title'],'section':u['section'],'source_refs':u['source_refs'],'sentences':ss})
 return out

QUESTIONS={
2015:[
('In Theresa’s view, what is the present government doing?','在特雷莎看来，现任政府正在做什么？','government','n.政府'),
('What is the problem in secondary schools now?','现在中学存在什么问题？','secondary schools~secondary school','n.中学'),
('What can we learn from the interview?','我们能从访谈中了解到什么？','learn','v.了解到；获知'),
('What contribution does Theresa think her party has made in education?','特雷莎认为，她所在的政党在教育方面作出了什么贡献？','contribution','n.贡献'),
('What’s the man’s focus in this part of the interview?','在访谈的这一部分，男士关注的重点是什么？','focus','n.关注的重点'),
('In Theresa’s view, what is school freedom?','在特雷莎看来，学校自由意味着什么？','freedom','n.自由；自主权'),
('According to Theresa, who decides money for schools at the present?','根据特雷莎的说法，目前由谁决定学校经费？','According to','phr.根据；按照'),
('What is the role of the interviewer throughout the talk?','在整个谈话过程中，采访者扮演了什么角色？','throughout','prep.贯穿；在整个……期间'),
('Why some state school pupils give up applying to leading universities?','为什么有些公立学校的学生放弃申请顶尖大学？','give up','phr.放弃'),
('What do we learn about the money being spent on schools at the moment?','关于目前用于学校的经费，我们了解到什么？','at the moment','phr.目前；此刻')],
2021:[
('What is Maureen McLane according to the interviewer?','根据采访者的介绍，莫琳·麦克莱恩是什么身份？','according to','phr.根据；按照'),
('When did Maureen first begin to read poetry?','莫琳最早是什么时候开始读诗的？','poetry','n.诗歌'),
('Who were the most important teachers to Maureen?','对莫琳来说，最重要的老师是谁？','important','adj.重要的'),
('Which of the following did Maureen feel more strongly about when she returned to teach at Harvard?','莫琳回到哈佛任教时，对下列哪一方面感受更加强烈？','returned~return','v.返回'),
('Why did Maureen bring recordings to class?','莫琳为什么把录音带到课堂上？','recordings~recording','n.录音'),
('What did Maureen think about socializing with writers?','莫琳如何看待与作家交往？','socializing~socialize','v.社交；与人交往'),
('What was Maureen’s view about a community for poets?','莫琳如何看待诗人的群体或圈子？','community','n.群体；圈子'),
('Why did her sections have concluding stanzas?','她为什么在各部分设置结尾的诗节？','stanzas~stanza','n.诗节'),
('What did Maureen think about her way of poetry reading?','莫琳如何看待自己的诗歌朗读方式？','reading','n.朗读'),
('What is the interview mainly about?','这次访谈主要谈论什么？','mainly','adv.主要地')]
}


def annotations(en,term,meaning):
 surface,_,head=term.partition('~');head=head or surface
 hits=list(re.finditer(re.escape(surface),en,re.I))
 assert hits,(en,surface)
 m=hits[0]
 return [{'t':'phr' if ' ' in head else 'word','h':head,'m':meaning,'sp':[[m.start(),m.end()]]}]


def build(year):
 tables={};current=None
 for line in (B/f'译注草稿/{year}_人工译注.tsv').read_text().splitlines():
  if line.startswith('['):current=line[1:-1];tables[current]=[]
  elif line.strip():
   a=line.split('|');assert len(a)==3,line
   tables[current].append(a)
 units=prepare(year)
 for u in units:
  ss=u.pop('sentences');tr=tables[u['id']]
  assert len(ss)==len(tr),(u['id'],len(ss),len(tr))
  u['sentences']=[];speaker='lecturer' if u['id'].endswith('-A') else None
  for i,(en,(zh,term,meaning)) in enumerate(zip(ss,tr),1):
   prefix=re.match(r'^(?:\(([IT])\)|([MW]))\s*:\s*',en)
   if prefix:speaker=prefix[1] or prefix[2];en=en[prefix.end():]
   en=en.strip();w=annotations(en,term,meaning)
   for item in w:
    for a,b in item['sp']:assert 0<=a<b<=len(en)
   u['sentences'].append({'en':en,'zh':zh,'w':w,'speaker':speaker,'role':'body','source_sentence':i})
  if u['id'].endswith(('B1','B2')):
   start=0 if u['id'].endswith('B1') else 5
   for n,(en,zh,term,meaning) in enumerate(QUESTIONS[year][start:start+5],start+1):
    u['sentences'].append({'en':en,'zh':zh,'w':annotations(en,term,meaning),'role':'question','n':n,'speaker':'announcer'})
  u['待核']=[]
 if year==2015:
  units[0]['待核']=['ASR在197.73秒明确识别versus，已把版面VS转成该口述词；da da DA节奏拟声仍按页图保留但ASR无对应，需原音听核，不能把版面符号强加到录音。']
  units[2]['待核']=['第9题原解析与1332.27秒ASR都为Why some...，均无助动词do；保留实际口述候选，不擅自按语法加词。']
  units[0]['audio_corrections']=[{'source':'VS','candidate':'versus','evidence':'预处理/2015/识别.json 197.73s；非人工听核结论'}]
 else:
  units[0]['待核']=['解析与473.12秒ASR均为civil rights of the 1960s（未见movement）；不凭语法补英语词，由root最终听核。']
  units[1]['待核']=['解析印为a number of memoir and criticism；908.27秒ASR明确为memoirs and criticisms，已据ASR修复复数，仍由root原音听核。']
  units[2]['待核']=['解析误印divided in dissections，1291.22秒ASR明确divided into sections，已修为该候选；root最终听核。','原页5有采访者应声Emm, Emm...，OCR漏掉，已按页图恢复；ASR1323秒附近无此应声，须原音核具体应声。']
  units[1]['audio_corrections']=[{'source':'a number of memoir and criticism','candidate':'a number of memoirs and criticisms','evidence':'预处理/2021/识别.json 908.27s；非人工听核结论'}]
  units[2]['audio_corrections']=[{'source':'divided in dissections','candidate':'divided into sections','evidence':'预处理/2021/识别.json 1291.22s；非人工听核结论'}]
 for u in units:
  u['source_check']={'pdf_pages_viewed':True,'transcript_scope':'解析正文及其真实题干；未把答案或中文解析混入英文正文','audio_alignment':'待root统一ASR与原音核对；此稿不含时间值'}
 result={'year':year,'status':'draft_pdf_checked_audio_pending','units':units,'source_version':'所供新题型优化版' if year==2015 else '所供新题型解析与原卷',
         'review':'解析页图已实看核对并修OCR；翻译和语境词义为人工草稿，原音一致性未冒称通过。'}
 (B/f'译注草稿/{year}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
 print(year,[(u['id'],len(u['sentences']),len(u['待核'])) for u in units])


if __name__=='__main__':
 for year in [2015,2021]:build(year)
