"""Draft per-question reasoning and writing transfers against the checked Cambridge lesson."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]
CJK = re.compile(r'[\u3400-\u9fff]')
QUESTION_SYSTEM = """你是给中国考生写雅思学术阅读解析的编辑。每题有原书答案与题目，全文及核定翻译列在 sentences。以原文事实为准，自己写两到三句简洁具体的中文推理，约70至130字。第一步指出题干究竟问的是哪件事；第二步把原文的具体事实或对应短语与题干比较，说明为什么应当作此判断。比如一项没查地点的购买记录不能证明是在法国画廊购买，不要只说“未提及”三个字。选择题点出一个实际出现的干扰项为何不合，双选分别解释两个正确选项。填空说明语法位置、同义改写或单复数中真正关键的一点。段落标题要概括段落，不以例子替代主旨。所引英文必须是题目或原文中真实出现的短片段。不要补写文中未给的事实，不要改变答案，不要重复大段原句。给出1到3个实际原文句号（材料索引），每个序号选准确。全文都可查。每题字段为 reasoning（中文）和 evidence（原文序号数组）。"""
GRAMMAR_SYSTEM = """你是中国学生的雅思阅读与写作老师。给定3个原文长句及其准确中译。为每个原句写一条细读讲解和一条写作迁移。heading 是本句具体结构，analysis 用中文清楚指出真实主句主语、完整谓语、主要从句或非谓语修饰谁，说明连接词或指代如何改变意思。pattern 是能复用的英文骨架。task 为一个具体的 IELTS Writing Task 1 或 Task 2 写作情境，如“Task 2 · 城市是否应增加低价出租房”。example 为针对该场景的一个原创、语法自然的英文句子，真正用到所讲结构。example_zh 译得准确流畅。usage 用中文说清这个写法在示例中表达什么、使用时一个具体限制。不可给未经提供的研究数字或杜撰的事实，不用空泛的万能句。每条取不同的合理写作情境。"""
def obj(fields):
 return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
STR={'type':'string'}
def invoke(instruction,payload,schema):
 url=os.environ.get('STUDY_EDITOR_URL','http://127.0.0.1:8176/v1/chat/completions')
 data={'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],'temperature':.12,'seed':721,'max_tokens':2400,'response_format':{'type':'json_schema','json_schema':{'name':'study','strict':True,'schema':schema}},'cache_prompt':True}
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,data=json.dumps(data,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=950) as h:choice=json.load(h)['choices'][0]
   if choice.get('finish_reason')=='length':raise ValueError('Incomplete editor response')
   return json.loads(choice['message']['content'])
  except (OSError,ValueError,KeyError):
   if attempt==2: raise
   data['seed']+=1
   time.sleep(2+attempt)
def write(path,data):
 tmp=path.with_suffix('.partial');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');os.replace(tmp,path)
def sentences_for(lesson):
 return [{'n':i,'p':s['tag'] or s['p'],'en':s['en'],'zh':s['zh']} for i,s in enumerate(lesson['sentences'],1)]
def question_batch(lesson,questions):
 sentences=sentences_for(lesson)
 schema={};records=[]
 for q in questions:
  i=q['numbers'][0];name='q'+str(i)
  schema[name]=obj({'reasoning':STR,'evidence':{'type':'array','items':{'type':'integer','minimum':1,'maximum':len(sentences)},'minItems':1,'maxItems':3}})
  row={k:v for k,v in q.items() if k not in {'accepted_variants','evidence','logic'}}
  # Candidate sentences guide retrieval. They do not gate a justified passage-wide judgement.
  row['candidate_sentences']=q['evidence']
  records.append(row)
 indices={i for q in questions for anchor in q['evidence'] for i in (anchor-1,anchor,anchor+1) if 1<=i<=len(sentences)}
 anchors=[s for s in sentences if s['n'] in indices]
 original=[dict(n=s['n'],en=s['en']) for s in sentences if s['n'] not in indices]
 ans=invoke(QUESTION_SYSTEM,dict(title=lesson['display_title'],questions=records,sentences=anchors,other_original_sentences=original),obj(schema))
 out={}
 for q in questions:
  i=q['numbers'][0];cell=ans['q'+str(i)];ev=list(dict.fromkeys(cell['evidence']));logic=cell['reasoning'].strip()
  if len(CJK.findall(logic))<24 or any(not 1<=x<=len(sentences) for x in ev):raise ValueError(f'{i}: incomplete analysis')
  out[str(i)]={'logic':logic,'evidence':ev}
 return out
PATTERNS=[
 ('concessive',r'\b(?:[Aa]lthough|[Ww]hile|[Ee]ven though|[Ww]hereas|[Ww]hatever|[Dd]espite)\b'),
 ('conditional',r'\b(?:[Ii]f|[Uu]nless|[Pp]rovided that|[Ww]hether)\b'),
 ('relative',r',\s*(?:which|who|whose|where)\b|\b(?:some|many|one|most) of (?:whom|which)\b'),
 ('object',r'\b(?:show(?:s|ed)?|suggest(?:s|ed)?|found|believe[ds]?|argue[ds]?|examined|asked|recognise[ds]?|concluded)\s+(?:that|what|whether|how)\b'),
 ('time',r'\b(?:[Ww]hen|[Oo]nce|[Bb]efore|[Aa]fter|[Uu]ntil|[Aa]s soon as)\b'),
 ('result',r'\b(?:[Bb]ecause|[Ss]ince|so that|resulting in|leading to|which means)\b'),
 ('modifier',r',\s*(?:[a-z]+ing|(?:a|an) [a-z]+)\b')]
def select(lesson):
 items=sentences_for(lesson);picked=[];paragraphs=set()
 for group,pattern in PATTERNS:
  candidates=[s for s in items if s['n'] not in picked and len(s['en'].split())>=23 and len(s['en'].split())<=58 and re.search(pattern,s['en'])]
  candidates.sort(key=lambda s:(s['p'] in paragraphs,abs(len(s['en'].split())-34),s['n']))
  if candidates:
   s=candidates[0];picked.append(s['n']);paragraphs.add(s['p'])
  if len(picked)==3:break
 if len(picked)<3:
  candidates=sorted((s for s in items if s['n'] not in picked and 20<=len(s['en'].split())<=70),key=lambda s:abs(len(s['en'].split())-35))
  picked.extend(s['n'] for s in candidates[:3-len(picked)])
 if len(picked)!=3:raise ValueError(lesson['lesson'])
 return sorted(picked)
def grammar(lesson):
 indices=select(lesson);src=sentences_for(lesson)
 fields=['heading','analysis','pattern','task','example','example_zh','usage']
 schema=obj({'s'+str(i):obj({k:STR for k in fields}) for i in indices})
 got=invoke(GRAMMAR_SYSTEM,{'passage':lesson['display_title'],'sentences':[src[i-1] for i in indices]},schema)
 rows=[]
 for i in indices:
  entry=got['s'+str(i)]
  if (len(CJK.findall(entry['analysis']))<22 or not CJK.search(entry['example_zh']) or len(entry['example'].split())<8 or CJK.search(entry['example']) or not CJK.search(entry['usage'])):raise ValueError('Incomplete writing example '+str(i))
  rows.append({'sentence':i,**entry})
 return rows
def generate(pid,folder):
 src=PROJECT/'配套讲义/题目与证据'/(pid+'.json');lesson=json.loads(src.read_text());folder.mkdir(parents=True,exist_ok=True);f=folder/(pid+'.json')
 key=hashlib.sha256(src.read_bytes()).hexdigest()
 draft=json.loads(f.read_text()) if f.is_file() else {}
 if draft.get('input_sha256')!=key: draft={'lesson':pid,'input_sha256':key,'questions':{}}
 if 'grammar' in lesson:
  draft['grammar']=lesson['grammar']
 for start in range(0,len(lesson['questions']),4):
  group=lesson['questions'][start:start+4]
  needed=[]
  for q in group:
   name=str(q['numbers'][0])
   if 'logic' in q:draft['questions'][name]={'logic':q['logic'],'evidence':q['evidence']}
   elif name not in draft['questions']:needed.append(q)
  if needed:draft['questions'].update(question_batch(lesson,needed))
  write(f,draft)
 if not draft.get('grammar'):
  draft['grammar']=grammar(lesson)
 write(f,draft)
 print(pid,len(draft['questions']),'question analyses;',len(draft['grammar']),'writing transfers',flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('ids',nargs='+')
 args=ap.parse_args()
 for pid in args.ids:generate(pid,args.folder)
