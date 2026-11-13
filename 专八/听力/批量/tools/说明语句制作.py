"""按实际ASR词索引提取正式说明、题组提示和过渡语，不补造音频缺段。

公共译句表只提供译法；每个范围必须由当年ASR中的真实词锚定位。
输出为待最终听核的译注候选，不写approved，不估算时间。
"""
import argparse,hashlib,json,re
from pathlib import Path
B=Path(__file__).resolve().parents[1]
OUT=B/'说明语句'
YEARS=list(range(2009,2020))+list(range(2021,2025))
NUM={'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10','thirty':'30','i':'1'}
T={
 'test':('英语专业全国统一考试。','Majors','major','n.某专业的学生'),
 'grade':('专业八级。','Grade','grade','n.级别'),
 'part':('第一部分：听力理解。','Comprehension','comprehension','n.理解'),
 'a_header':('A节：短讲。','lecture','lecture','n.讲座；短讲'),
 'a_in':('在这一节中，你将听到一段短讲。','hear','hear','v.听到'),
 'a_once':('这段短讲只播放一遍。','once','once','adv.一次'),
 'a_gap':('请边听短讲，边完成答题卡一上的填空任务；每空填写不超过三个词。','gap-filling','gap-filling','adj.填空的'),
 'a_accept':('请确保填入的词在语法和语义上都恰当。','acceptable','acceptable','adj.可接受的；恰当的'),
 'a_blank':('你可以用空白纸做笔记。','blank','blank','adj.空白的'),
 'a_blank_fragment':('做笔记。','note-taking','note-taking','n.记笔记'),
 'a_preview':('你有三十秒钟预览填空任务。','preview','preview','v.预览；预先浏览'),
 'a_listen':('现在请听短讲。','listen','listen','v.听'),
 'a_check_future':('短讲结束后，你将有三分钟检查作答。','check','check','v.检查'),
 'a_check':('现在你有三分钟检查作答。','check','check','v.检查'),
 'a_end':('A节短讲到此结束。','end','end','n.结束'),
 'b_header':('B节：访谈。','Interview','interview','n.访谈'),
 'b_in_one':('在这一节中，你将听到一段访谈。','interview','interview','n.访谈'),
 'b_in_two':('在这一节中，你将听到两段访谈。','interviews','interview','n.访谈'),
 'b_divided':('这段访谈分为两部分。','divided','divide','v.划分'),
 'b_five_part':('每部分结束后，将就刚才所说的内容提出五个问题。','questions','question','n.问题'),
 'b_five_interview':('每段访谈结束后，将就刚才所说的内容提出五个问题。','questions','question','n.问题'),
 'b_once':('访谈和问题都只读一遍。','once','once','adv.一次'),
 'b_pause':('每个问题之后会有十秒钟的停顿。','pause','pause','n.停顿'),
 'b_pause_fragment':('题目……会有十秒钟的停顿。','pause','pause','n.停顿'),
 'b_choices':('请利用停顿时间阅读A、B、C、D四个选项，并在答题卡二上标出每题的最佳答案。','choices','choice','n.选项'),
 'b_preview_questions':('你有三十秒钟预览题目。','preview','preview','v.预览；预先浏览'),
 'b_preview_choices':('你有三十秒钟预览选项。','preview','preview','v.预览；预先浏览'),
 'b1_listen_part':('现在请听访谈的第一部分。','listen','listen','v.听'),
 'b1_listen_interview':('现在请听第一段访谈。','listen','listen','v.听'),
 'b2_listen_part':('现在请听访谈的第二部分。','listen','listen','v.听'),
 'b2_listen_interview':('现在请听第二段访谈。','listen','listen','v.听'),
 'b1_group_part':('第1至5题根据访谈的第一部分提问。','based on','be based on','phr.以……为依据'),
 'b1_group_interview':('第1至5题根据第一段访谈提问。','based on','be based on','phr.以……为依据'),
 'b2_group_part':('第6至10题根据访谈的第二部分提问。','based on','be based on','phr.以……为依据'),
 'b2_group_interview':('第6至10题根据第二段访谈提问。','based on','be based on','phr.以……为依据'),
 'b1_group_heard':('第1至5题根据你刚才听到的内容提问。','based on','be based on','phr.以……为依据'),
 'b2_group_heard':('第6至10题根据你刚才听到的内容提问。','based on','be based on','phr.以……为依据'),
 'b1_end_part':('访谈的第一部分到此结束。','end','end','n.结束'),
 'b2_end_part':('访谈的第二部分到此结束。','end','end','n.结束'),
 'b1_end_interview':('第一段访谈到此结束。','end','end','n.结束'),
 'b2_end_interview':('第二段访谈到此结束。','end','end','n.结束'),
 'b_end':('B节访谈到此结束。','end','end','n.结束'),
 'end':('第一部分听力理解到此结束。','Comprehension','comprehension','n.理解'),
 '2014_narrator':('现在请听奥斯卡获奖演员安吉丽娜·朱莉与CNN记者安德鲁·达曼的访谈。','actress','actress','n.女演员'),
}
TITLES={
 2009:('实验报告写作。','reports','report','n.报告'),
 2010:('语言的副语言特征。','Paralinguistic','paralinguistic','adj.副语言的；与语调、音量等语言伴随特征有关的'),
 2011:('文化的分类。','Classifications','classification','n.分类'),
 2012:('观察行为。','Behavior','behavior','n.行为'),
 2013:('主动学习者会做些什么？','active','active','adj.主动的；积极的'),
 2014:('如何减轻压力。','Stress','stress','n.压力'),
 2015:('理解学术……〔标题ASR未完整，待听核〕','academic','academic','adj.学术的'),
 2016:('论证的模式。','arguments','argument','n.论证'),
 2017:('语言的表达方式。','modes','mode','n.方式；模式'),
 2018:('语言与人类。','Humanity','humanity','n.人类'),
 2019:('肢体语言与心智。','mind','mind','n.心智；思维'),
 2021:('当前美国高等教育面临的挑战。','Challenges','challenge','n.挑战'),
 2022:('人类学的领域与分支。','Anthropology','anthropology','n.人类学'),
 2023:('讲话中的隐喻。','Metaphors','metaphor','n.隐喻'),
 2024:('为什么学习第二语言更难？','language','language','n.语言'),
}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):
 s=re.sub('[^a-z0-9]','',s.lower());return NUM.get(s,s)
def seek(n,pat,a=0,z=None):
 q=[norm(t) for t in pat.split()];z=len(n) if z is None else z
 return [i for i in range(a,z-len(q)+1) if n[i:i+len(q)]==q]
def raw(w,a,z):return ' '.join(x[0] for x in w[a:z])
def display(s,key):
 s=re.sub(r'\bmini[- ]lecture\b','mini-lecture',s,flags=re.I)
 s=re.sub(r'\bgap[- ]filling\b','gap-filling',s,flags=re.I)
 s=re.sub(r'\bnote[- ]taking\b','note-taking',s,flags=re.I)
 s=re.sub(r'\b(?:10|ten)[- ]second\b','ten-second',s,flags=re.I)
 # ASR句点不等于实际句界；同一正式说明句内部只整理标点，不加词。
 if key in ['a_gap','b_choices']:
  s=re.sub(r'\.\s+([A-Z])',lambda m:', '+m[1].lower(),s)
 if key in ['a_preview','b_preview_choices','b_preview_questions','b1_end_interview']:
  s=re.sub(r'\.\s+([A-Z])',lambda m:' '+m[1].lower(),s)
 if key=='a_check':s=re.sub(r'^Now[?.,]*\s+You\b','Now, you',s)
 s=re.sub(r',\s+(There|You|Complete|Please)\b',lambda m:', '+m[1].lower(),s)
 if key=='a_accept':s=re.sub(r'\bword words\b','word(s)',s,flags=re.I)
 s=re.sub(r'[,;:]\s*[.]$','.',s)
 s=s.strip();s=s[:1].upper()+s[1:]
 if s and s[-1] not in '.?!':s+='.'
 if key=='a_title' and re.match('(?:Why|What)\\b',s):s=s.rstrip('.?')+'?'
 return s

def sentence(year,w,a,z,key,role='instruction'):
 assert 0<=a<z<=len(w),(year,a,z,key)
 en=display(raw(w,a,z),key)
 if key=='test':zh,term,head,meaning=(f'{year}年'+T[key][0],*T[key][1:])
 elif key=='a_title':zh,term,head,meaning=TITLES[year]
 else:zh,term,head,meaning=T[key]
 # 有些ASR只识别到Lecture或复数Interviews；词条仍给出真实表面span。
 hit=re.search(re.escape(term),en,re.I)
 if not hit and key=='b_header':hit=re.search('interviews?',en,re.I)
 assert hit,(year,a,z,key,en,term)
 return {'en':en,'zh':zh,'w':[{'t':'phr' if ' ' in head else 'word','h':head,'m':meaning,'sp':[[hit.start(),hit.end()]]}],
  'role':role,'asr_range':[a,z],'asr_text':raw(w,a,z),'translation_key':key}

def group_starts(n):
 out=[]
 for i in range(len(n)-8):
  if n[i]!='questions':continue
  if n[i+1] in ['1','6'] and n[i+2]=='to' and n[i+3] in ['5','10']:
   out.append((i,1 if n[i+1]=='1' else 2))
  elif n[i+1]=='610' and n[i+2:i+5]==['are','based','on']:out.append((i,2))
 return out

def group_end(n,a):
 for i in range(a+3,min(a+22,len(n))):
  if n[i] in ['interview','interviews','heard']:return i+1
 raise ValueError(('group end',a,n[a:a+22]))

def anchors(n,a,z,kind):
 """每段语义句只按该段中真实存在的词锚起句，未命中范围不套模板。"""
 out=[]
 def add(p,key):
  for i in seek(n,p,a,z):out.append((i,key))
 if kind=='a_before':
  add('test for english majors','test');add('grade','grade');add('part','part')
  first_in=seek(n,'in this section',a,z)[0] if seek(n,'in this section',a,z) else z
  sec=seek(n,'section a',a,first_in)
  if sec:out.append((sec[0],'a_header'))
  else:
   # 2010 ASR将Section漏识，A Mini Lecture仍真实存在；不补这个单词。
   found=seek(n,'section',a,first_in) or seek(n,'a mini',a,first_in)
   if found:out.append((found[0],'a_header'))
  add('in this section','a_in');add('you will hear','a_once');add("you'll hear",'a_once')
  add('while listening','a_gap');add('make sure','a_accept');add('you may use','a_blank');add('you have','a_preview')
  if not seek(n,'you may use',a,z):
   add('note-taking','a_blank_fragment')
  add('now listen','a_listen');add('when it is over','a_check_future')
 elif kind=='a_after':add('now you have','a_check');add('this is the end','a_end')
 elif kind in ['b1_before','b2_before']:
  j=1 if kind=='b1_before' else 2
  if j==1:
   add('section b','b_header');add('in this section','b_in')
   add('the interview will','b_divided');add('at the end of each','b_five');add('both the','b_once')
   add('after each question','b_pause');add('question there will','b_pause_fragment')
   add('during the pause','b_choices');add('you have','b_preview')
  add('now listen',f'b{j}_listen');add('listen to part',f'b{j}_listen');add('listen to the',f'b{j}_listen')
  for i,k in group_starts(n):
   if a<=i<z:out.append((i,f'b{k}_group'))
 elif kind in ['b1_before_questions','b2_before_questions']:
  j=1 if kind.startswith('b1') else 2
  add('this is the end',f'b{j}_end')
  for i,k in group_starts(n):
   if a<=i<z:out.append((i,f'b{k}_group'))
 elif kind=='b2_after':add('this is the end','end_auto')
 # 较长词锚优先；Now listen不可在listen to处再重复开一条。
 out=sorted(set(out));clean=[]
 for i,k in out:
  if clean and k=='a_once' and clean[-1][1]=='a_in' and i-clean[-1][0]<=3:continue
  if clean and k=='b_pause_fragment' and clean[-1][1]=='b_pause' and i-clean[-1][0]<=2:continue
  if clean and i-clean[-1][0] in [1] and '_listen' in k and '_listen' in clean[-1][1]:continue
  clean.append((i,k))
 return clean

def split_block(year,w,n,a,z,kind,pending):
 aa=anchors(n,a,z,kind)
 if not aa or aa[0][0]!=a:
  pending.append({'asr_range':[a,aa[0][0] if aa else z],'asr_text':raw(w,a,aa[0][0] if aa else z),'reason':kind+'段首未识别为明确说明锚，未套模板。'})
 result=[]
 for j,(i,key) in enumerate(aa):
  end=aa[j+1][0] if j+1<len(aa) else z
  seg=n[i:end]
  if key=='b_in':key+='_'+('two' if '2' in seg else 'one')
  elif key=='b_five':key+='_'+('part' if 'part' in seg else 'interview')
  elif key=='b_preview':key+='_'+('choices' if 'choices' in seg else 'questions')
  elif re.match(r'b[12]_(?:listen|group|end)$',key):
   if key.endswith('_group') and 'heard' in seg:key+='_heard'
   else:key+='_'+('part' if 'part' in seg else 'interview')
  elif key=='end_auto':key='b_end' if 'section' in seg else 'end'
  role='transition' if key.endswith(('header','title')) or re.search(r'_(?:listen|group|end)(?:_|$)',key) or key in ['part','test','grade','end','a_check','a_check_future'] else 'instruction'
  result.append(sentence(year,w,i,end,key,role))
 return result

def build(year):
 path=B/f'预处理/{year}/识别.json';w=json.loads(path.read_text());n=[norm(x[0]) for x in w];pending=[]
 # 这里只匹配讲座问候前的正式题名；不把正文首句再算作说明。
 good=seek(n,'good morning',0,min(300,len(n)));assert good,(year,'lecture start')
 body_start=good[0];work=next(i+1 for i in range(body_start-1,-1,-1) if n[i]=='work')
 after=seek(n,'now you have',body_start)[0];sec=seek(n,'section b',after)[0]
 groups=group_starts(n)
 q1=[i for i,j in groups if j==1];q2=[i for i,j in groups if j==2]
 assert len(q1)==len(q2)==2,(year,groups)
 q1pre,q1post=q1;q2pre,q2post=q2
 ends=seek(n,'this is the end')
 b1end=max(i for i in ends if i<q1post);b2end=max(i for i in ends if i<q2post)
 final=min(i for i in ends if i>q2post)
 # B2前实际没有Now listen时，只从真实题组提示开始，不补模板。
 ls=[i for i in seek(n,'now listen',q1post,q2pre+1)]
 b2before=ls[-1] if ls else q2pre
 if not ls:pending.append({'asr_range':[q2pre,q2pre],'reason':'ASR未识别到第二段开始前Now listen提示，只收录实际题组提示；需原音核其是否真的缺失。'})
 units=[{'id':f'{year}-A','before':split_block(year,w,n,0,work,'a_before',pending),'after':split_block(year,w,n,after,sec,'a_after',pending)},
  {'id':f'{year}-B1','before':split_block(year,w,n,sec,group_end(n,q1pre),'b1_before',pending),'before_questions':split_block(year,w,n,b1end,group_end(n,q1post),'b1_before_questions',pending)},
  {'id':f'{year}-B2','before':split_block(year,w,n,b2before,group_end(n,q2pre),'b2_before',pending),'before_questions':split_block(year,w,n,b2end,group_end(n,q2post),'b2_before_questions',pending),'after':split_block(year,w,n,final,len(w),'b2_after',pending)}]
 units[0]['before'].append(sentence(year,w,work,body_start,'a_title','transition'))
 if year==2014:
  a=group_end(n,q1pre);z=seek(n,'first of all',a,a+30)[0]
  units[1]['before'].append(sentence(year,w,a,z,'2014_narrator','transition'))
  pending.append({'asr_range':[a,z],'reason':'额外采访引入中CNN记者姓名ASR为Andrew Darman，专名需原音或可靠资料核对，不冒称已核。'})
 if year==2018:
  for t in units[1]['before']:
   if t['translation_key']=='b_pause_fragment':pending.append({'asr_range':t['asr_range'],'asr_text':t['asr_text'],'reason':'ASR仅有question there will be...，疑漏After each；未按公共模板补英语。'})
 if year==2015:pending.append({'asr_range':[work,body_start],'reason':'ASR讲座题名仅Understanding academic，解析标题为Understanding Academic Lectures；未给漏识词伪造索引，需原音听核。'})
 if year==2021:
  a=group_end(n,q1pre);z=a+3
  if n[a:z]==['of','the','interview']:
   pending.append({'asr_range':[a,z],'asr_text':raw(w,a,z),'reason':'题组提示后ASR重复残片Of the interview，疑识别拼接重复，暂不当正式说明正文；需原音听核。'})
 if year==2022:pending.append({'reason':'当前ASR是原包缺开头版本，仅按实际Now listen起；完整来源与新ASR待root替换后重新提取。'})
 if year in [2010,2011]:pending.append({'reason':'卷首ASR标题漏识Section或Mini，英语保留实际已识别词，未凭模板补词；需原音听核。'})
 for u in units:
  for v in u.values():
   if not isinstance(v,list):continue
   for t in v:
    key=t['translation_key'];text=t['asr_text'];reason=None
    if key=='a_header' and year==2013:
     reason='ASR卷首标题为Section ANI Lecture，属于明显疑似漏识/错连；题卷标题为Section A MINI-LECTURE，未擅造漏词索引。'
    elif key=='a_gap' and re.search(r'please\W+please',text,re.I):
     reason='ASR连续重复please，需原音核是否确为口述重复；未静默删除。'
    elif key=='a_gap' and not re.search(r'\bsheet\b',text,re.I):
     reason='ASR把答题卡位置识别为answering one，与原卷ANSWER SHEET ONE不符；需要听核，不以普通模板冒充实际已识别词。'
    elif key=='a_blank' and re.search(r'use\W+use',text,re.I):
     reason='ASR连续重复use，需原音核是否口述重复；未静默删除。'
    elif key=='a_blank_fragment':
     reason='ASR仅识别到note-taking，缺少原卷You may use the blank sheet for...；单独保留已识别片段，未把它并入上一说明句。'
    elif key=='b_header' and len(text.split())>3:
     reason='ASR章节标题出现is the first of the U.S.额外语句，与原卷SECTION B INTERVIEW不符；需要听核是否为识别幻觉。'
    if reason:pending.append({'asr_range':t['asr_range'],'asr_text':text,'reason':reason})
 for u in units:
  for v in u.values():
   if not isinstance(v,list):continue
   for t in v:
    a,z=t['asr_range']
    flags=[p['reason'] for p in pending if 'asr_range' in p and max(a,p['asr_range'][0])<min(z,p['asr_range'][1])]
    if flags:t['待核']=flags
 p=B/f'数据/{year}/试卷.json'
 result={'year':year,'status':'draft_asr_anchored_audio_review_pending','units':units,'待核':pending,
  'source':{'asr':str(path.relative_to(B)),'asr_sha256':sha(path),'word_count':len(w),'paper':str(p.relative_to(B)),'paper_sha256':sha(p)},
  'index_convention':'asr_range为零起点[startWordIndex,endExclusive]，精确指向当年所列ASR；不是估时值。',
  'normalizations':['整理大小写与ASR误句点；mini-lecture/gap-filling/note-taking/ten-second以常规连字符排版','ASR读出的word words用书面word(s)表示，原始词保存在asr_text；不补漏识词'],
  'scope':'只含实际ASR有锚点的正式说明、题名、题组提示和过渡语；正文和10道具体题干由译注草稿另供。',
  'translation_table':'公共译句表.json；共用译法仅复用翻译，不决定任何年份的英文或词索引。'}
 OUT.mkdir(exist_ok=True);(OUT/f'{year}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--years',type=int,nargs='+',default=YEARS);a=p.parse_args()
 OUT.mkdir(exist_ok=True)
 (OUT/'公共译句表.json').write_text(json.dumps({'templates':{k:{'zh':v[0],'surface':v[1],'headword':v[2],'meaning':v[3]} for k,v in T.items()},'titles':{k:{'zh':v[0],'surface':v[1],'headword':v[2],'meaning':v[3]} for k,v in TITLES.items()}},ensure_ascii=False,indent=2)+'\n')
 for y in a.years:
  d=build(y);print(y,[(u['id'],{k:len(v) for k,v in u.items() if isinstance(v,list)}) for u in d['units']], '待核',len(d['待核']),flush=True)
if __name__=='__main__':main()
