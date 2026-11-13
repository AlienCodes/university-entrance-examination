"""由已保存的ASR/静音候选生成可复核的年度考试时间轴，不自动清除题源待核。
所有时间是剪头前原音秒；正式音乐裁切需另有逐年登记，不以首个ASR词冒充剪点。
"""
import argparse,difflib,hashlib,json,re
from pathlib import Path
D=Path(__file__).resolve().parents[1]
NUM={str(i):i for i in range(1,11)}|dict(zip('one two three four five six seven eight nine ten'.split(),range(1,11)))
def norm(s):return re.sub('[^a-z0-9]','',s.lower())
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def seqhits(w,seq,lo,hi):
 n=[norm(s) for s in seq.split()]
 return [i for i in range(len(w)-len(n)+1) if lo<=w[i][1]<hi and [norm(x[0]) for x in w[i:i+len(n)]]==n]
def unique(w,seq,lo,hi):
 hit=seqhits(w,seq,lo,hi);assert len(hit)==1,(seq,lo,hi,hit)
 return hit[0]
def build(y):
 p=D/'预处理'/str(y);w=json.loads((p/'识别.json').read_text());sil=json.loads((p/'停顿.json').read_text())['静音'];prep=json.loads((p/'原音准备.json').read_text());qpath=D/'数据'/str(y)/'试卷.json';q=json.loads(qpath.read_text())
 duration=prep['canonical']['duration'];sha=prep['canonical']['sha256']
 override_file=D/'核验'/f'{y}-停顿边界复核.json'
 override=None
 if override_file.exists():
  audit=json.loads(override_file.read_text());assert audit['status']=='verified' and audit['source_sha256']==sha
  assert y==2022 and audit['signal_handling']['preserve_entire_wait_audio'] and not audit['signal_handling']['pure_silence_compression_allowed']
  for filename,digest in audit['bindings'].items():
   assert hashlib.sha256((p/filename).read_bytes()).hexdigest()==digest,('停顿核验依赖已变',filename)
  override=audit['machine_override']
 check=([override['check']] if override else [s for s in sil if 165<s[1]-s[0]<205]);assert len(check)==1,(y,'检查段非唯一',check);check=check[0]
 previews=[override['previewA'],override['previewB']] if override else [s for s in sil if 24<s[1]-s[0]<42]
 preA=[s for s in previews if s[0]<check[0]];preB=[s for s in previews if s[0]>check[1]]
 missing_opening=(y==2022 and not preA)
 assert (len(preA)==1 or missing_opening) and len(preB)==1,(y,previews)
 preA,preB=(preA[0] if preA else None),preB[0]
 pp=override['question_pauses'] if override else [s for s in sil if s[0]>preB[1] and 8.5<s[1]-s[0]<13]
 assert len(pp)==len(q['questions'])==10,(y,'题后作答段不是10段',pp)
 def real_end(a,b):
  ts=[x[1] for x in w if a+.5<x[1]<b+.5]
  return min(b,min(ts)) if ts else b
 preA=[preA[0],real_end(*preA)] if preA else None;preB=[preB[0],real_end(*preB)];check=[check[0],real_end(*check)]
 pp=[[a,real_end(a,b)] for a,b in pp]
 anchor_notes=[]
 if missing_opening:
  secA=0;anchor_notes.append('原包2022录音从Now listen指令开始，缺A正式说明/30秒预览；只按现有原音排候选，不补造声音/时间。')
 else:
  hits=seqhits(w,'Section A',0,preA[0])
  if len(hits)==1:secA=hits[0]
  else:
   ins=unique(w,'In this section',0,preA[0])
   heading=[i for i in range(ins) if norm(w[i][0]).startswith('section')]
   if not heading:heading=seqhits(w,'Mini Lecture',0,w[ins][1])
   assert len(heading)==1,(y,'标题替代锚非唯一',heading)
   secA=heading[0];anchor_notes.append('ASR漏了Section A完整词形，标题依据唯一说明前标题词实测锚，未补造时间。')
 secB=unique(w,'Section B',check[1],preB[0])
 trim_file=D/'音乐剪切'/f'{y}.json';trim=json.loads(trim_file.read_text()) if trim_file.exists() else {'start':0,'status':'待核片头音乐，时间轴仍保留完整原声，不准发布'}
 events=[]
 def add(t,**state):events.append({'t':round(float(t),3),**state})
 add(trim['start'],kind='instr',sec='A',hi=-1,st='请备好纸笔，听正式考试说明')
 add(w[secA][1],kind='instr',sec='A',hi=-1)
 # 说明仅按真实词匹配高亮；不匹配时仍完整展示原卷说明，另列核对报告。
 notes=anchor_notes.copy()
 instruction_windows=[('B',w[secB][1],preB[0])]
 if preA:instruction_windows.insert(0,('A',w[secA][1],preA[0]))
 for sec,lo,hi in instruction_windows:
  section=next(s for s in q['sections'] if s['id']==sec)
  for k,line in enumerate(section['lines']):
   prefix=' '.join(re.findall(r'[A-Za-z0-9]+',line)[:4]);hits=seqhits(w,prefix,lo,hi)
   if len(hits)==1:add(w[hits[0]][1],kind='instr',sec=sec,hi=k)
   else:notes.append({'section':sec,'line':k,'issue':'说明前缀未唯一对应，保留整段原卷说明、不制造逐句时间','text':line})
 if preA:
  add(preA[0],kind='sheet',st='预览答题卡',countdown={'end':preA[1],'label':'预览'})
  add(preA[1],kind='sheet',st='Mini-lecture 即将开始，只放一遍')
 else:add(w[0][1],kind='sheet',st='按所供原音开始，Section A开头说明与预览缺失')
 add(check[0],kind='sheet',st='检查答案',countdown={'end':check[1],'label':'检查'})
 add(check[1],kind='sheet',st='Section A 结束')
 add(w[secB][1],kind='instr',sec='B',hi=-1)
 groups=q['groups'];assert len(groups)==2
 add(preB[0],kind='plist',group=groups[0]['id'],st='预览采访选项',countdown={'end':preB[1],'label':'预览'})
 add(preB[1],kind='plist',group=groups[0]['id'],st='采访播放中，结束后作答第1—5题')
 question_candidates=[]
 for k,(a,b) in enumerate(pp):
  n=k+1;lo=(preB[1] if k==0 else pp[k-1][1]);hits=[]
  for i,x in enumerate(w[:-1]):
   if lo-.2<=x[1]<a and norm(x[0])=='question' and NUM.get(norm(w[i+1][0]))==n:hits.append(i)
  if len(hits)==1:t=w[hits[0]][1];idx=hits[0]+2
  elif k not in [0,5]:
   t=lo;idx=next(i for i,x in enumerate(w) if x[1]>=lo-.12);notes.append({'question':n,'issue':'ASR未认出唯一Question题号；按前一道作答停顿的实测终点显示下一题，须核录音'})
  else:raise AssertionError((y,n,'组首题未找到题号',hits))
  add(t,kind='q',n=n,st='听题')
  add(a,kind='q',n=n,st='请在答题纸上作答',countdown={'end':b,'label':'作答'})
  question_candidates.append({'n':n,'start':t,'pause':[a,b],'asr_text':' '.join(x[0] for x in w[idx:] if t-.1<=x[1]<a),'source':'仅机器候选，题干须核解析与实际录音，不直接替代原文'})
  if k==4:add(b,kind='plist',group=groups[1]['id'],st='采访播放中，结束后作答第6—10题')
 add(pp[-1][1],kind='end',st='请等待正式考试结束，之后展示答案')
 events.sort(key=lambda e:e['t'])
 # 同秒两个说明状态只保留最终者，倒计时及不同题不能用此隐去。
 merged=[]
 for ev in events:
  if merged and abs(ev['t']-merged[-1]['t'])<.0001:merged[-1]=ev
  else:merged.append(ev)
 T={'source_duration':duration,'source_sha256':sha,'trim':trim,'events':merged,'evidence':{'asr_sha256':hashlib.sha256((p/'识别.json').read_bytes()).hexdigest(),'pauses_sha256':hashlib.sha256((p/'停顿.json').read_bytes()).hexdigest(),'previewA':preA,'check':check,'previewB':preB,'question_pauses':pp,**({'reviewed_pause_override':{'file':str(override_file.relative_to(D)),'sha256':hashlib.sha256(override_file.read_bytes()).hexdigest(),'preserve_entire_wait_audio':True}} if override else {})},'pending':notes+([] if trim_file.exists() else ['片头音乐剪切点尚待正式核定'])}
 dump(D/'数据'/str(y)/'时间轴.json',T);dump(D/'核验'/f'{y}-时间轴候选.json',{'year':y,'questions':question_candidates,'notes':notes,'status':'候选待与实际原音/解析核对'})
 print(y,'timeline',len(merged),'events','notes',len(notes),'trim reviewed',trim_file.exists(),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('years',nargs='+',type=int);a=ap.parse_args()
 errors=[]
 for y in a.years:
  try:build(y)
  except Exception as e:errors.append((y,repr(e)));print('ERROR',y,repr(e),flush=True)
 if errors:raise SystemExit(str(errors))
