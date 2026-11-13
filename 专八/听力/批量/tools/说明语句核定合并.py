"""按保存的双模型局部证据恢复正式说明，并把说明插入译注草稿正确位置。

主ASR不改；恢复句的asr_ref/asr_range指向实际局部词表，primary_asr_range保留旧主词锚。
本脚本不签发approved。正文、题干对象逐字保留，全部词汇高亮区间重查。
"""
import argparse,copy,hashlib,importlib.util,json,re
from pathlib import Path
B=Path(__file__).resolve().parents[1];D=B/'说明语句'
spec=importlib.util.spec_from_file_location('instruction_builder',Path(__file__).with_name('说明语句制作.py'));M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
CASES={
 (2010,'a_header'):('Section A','In this section','a_header'),
 (2011,'a_header'):('Section A','In this section','a_header'),
 (2013,'a_header'):('Section A','In this section','a_header'),
 (2014,'2014_narrator'):('Now listen',None,'2014_narrator'),
 (2015,'a_title'):('Understanding academic','Good morning','a_title'),
 (2016,'a_gap'):('While listening','Make sure','a_gap'),
 (2018,'b_pause_fragment'):('After each question','During the pause','b_pause'),
 (2019,'a_blank'):('You may use','You have','a_blank'),
 (2019,'b_header'):('Section B','In this section','b_header'),
 (2021,'a_gap'):('While listening','Make sure','a_gap'),
 (2021,'b1_group_part'):('Questions one to five','Maureen','b1_group_part'),
 (2022,'a_check'):('Now you have',None,'a_check'),
 (2023,'a_blank_fragment'):('You may use','You have','a_blank'),
 (2024,'b2_group_interview'):('Now listen','Questions six to ten','b2_listen_interview'),
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def token(s):return [M.norm(x) for x in re.findall(r'[A-Za-z0-9]+',s)]
def instruction_fingerprint(s):
 s=re.sub(r'(Questions?\s+\d+)[-–](\d+)',r'\1 to \2',s,flags=re.I)
 ts=token(s)
 if ts[:1]==['now']:ts=ts[1:]
 return tuple(ts)
def find(w,p):
 flat=[(t,i) for i,x in enumerate(w) for t in token(x[0])];q=token(p)
 hits=[flat[i][1] for i in range(len(flat)-len(q)+1) if [x[0] for x in flat[i:i+len(q)]]==q]
 assert len(hits)==1,(p,hits,w)
 return hits[0]
def sentences(d):
 for u in d['units']:
  for k,v in u.items():
   if isinstance(v,list):
    for s in v:yield u,k,s

def adjudicate(year):
 p=D/f'{year}.json';d=json.loads(p.read_text());corrections=[]
 # 本脚本可重复运行，不重复增加恢复句；每次以实际局部词证据重建。
 for (y,case),(start_phrase,end_phrase,newkey) in CASES.items():
  if y!=year:continue
  local=D/f'局部复识别/{year}/{case}.json';e=json.loads(local.read_text())
  assert e['primary_asr_sha256']==d['source']['asr_sha256'],(year,case,'主ASR版本变了，必须重提取复识别')
  idx=next(i for i,r in enumerate(e['recognitions']) if r['model']=='parakeet');r=e['recognitions'][idx];w=r['words'];assert w
  a=find(w,start_phrase);z=find(w,end_phrase) if end_phrase else len(w)
  assert a<z
  selected=w[a:z]
  # 2014窗口尾到记者姓名即结束，若新重识别窗带入正式访谈首句则明确截断。
  if case=='2014_narrator':
   try:z=find(w,'First of all');selected=w[a:z]
   except AssertionError:pass
  targets=[(u,k,s) for u,k,s in sentences(d) if s.get('correction_case')==case or s.get('translation_key')==case]
  assert targets,(year,case,'找不到原说明句')
  u,slot,old=targets[0]
  # 2024该句属于全新找回的提示，原主ASR仅识别了后续题组，保留题组对象。
  append_before=(year==2024)
  old_primary=old.get('primary_asr_range',old['asr_range'])
  t=M.sentence(year,w,a,z,newkey,old['role'])
  if year==2015 and case=='a_title':t['zh']='理解学术讲座。'
  t.update({'speaker':'announcer','asr_ref':str(local.relative_to(B)),'asr_sha256':sha(local),'asr_pointer':f'/recognitions/{idx}/words',
   'primary_asr_range':old_primary,'primary_asr_ref':d['source']['asr'],'alignment_source':'local_parakeet_actual_word_timestamps',
   'words':selected,'start':selected[0][1],'end':selected[-1][2],'correction_case':case,
   'evidence':{'window':r['window'],'models':[v['model'] for v in e['recognitions']],
     'rationale':'局部错位上下文Parakeet恢复了完整实际词；独立Whisper文本互证（不借用公共模板补英语或估时）。',
     'whisper_timestamps':'模型未导出cross-attention，仅独立文本互证；词时刻明确来自Parakeet。'}})
  if year==2014:
   # root已明确裁定，按CNN原始采访规范罕见专名；ASR原词仍保留，不倒改证据。
   provenance=D/'来源/2014-CNN/抓取记录.json';sources=json.loads(provenance.read_text())
   assert all(x['status']==200 and sha(provenance.parent/x['file'])==x['sha256'] for x in sources)
   assert 'Andrew Darman' in t['en'],t['en']
   t['en']=t['en'].replace('Andrew Darman','Arwa Damon');t['zh']=t['zh'].replace('安德鲁·达曼','阿尔瓦·达蒙')
   c=t['en'].index('Arwa Damon');name_i=find(w,'Andrew Darman')
   t['w'].append({'t':'word','h':'Arwa Damon','m':'专名.阿尔瓦·达蒙，CNN记者','sp':[[c,c+len('Arwa Damon')]]})
   t['proper_name_audio_anchors']=[{'text':'Arwa Damon','char':[c,c+len('Arwa Damon')],
     'asr_ref':t['asr_ref'],'asr_pointer':t['asr_pointer'],'asr_range':[name_i,name_i+2],
     'start':w[name_i][1],'end':w[name_i+1][2],
     'method':'整个姓名对应原音实际人名两词锚，不按规范拼写猜词内时间。'}]
   t['proper_name_normalization']={'canonical':'Arwa Damon','asr_spelling':'Andrew Darman','legacy_material_spelling':'Andrew Damon',
     'authority':'root明确裁定依据CNN原始采访规范专名；录音不变。',
     'evidence_ref':str(provenance.relative_to(B)),'evidence_sha256':sha(provenance),
     'source_urls':[x['url'] for x in sources],
     'identity_check':'CNN原始采访首段明确Arwa Damon，正文First of all thank you...及两百万境内流离失所者段落与本年听力相同。'}
  if append_before:
   u[slot]=[x for x in u[slot] if x.get('correction_case')!=case]
   original=next(x for x in u[slot] if x['translation_key']==case)
   u[slot].insert(u[slot].index(original),t)
  else:u[slot][u[slot].index(old)]=t
  prior=next((c for c in d.get('local_corrections',[]) if c['case']==case),{})
  corrections.append({'case':case,'old_en':prior.get('old_en',old['en']),'new_en':t['en'],'primary_asr_range':old_primary,'local_asr_range':[a,z],
    'local_asr_ref':t['asr_ref'],'local_sha256':sha(local),'source_parts':r['source_parts'],'times':[t['start'],t['end']],
    'decision':'采用真实局部词，不改主ASR','independent_texts':{x['model']:x['text'] for x in e['recognitions']}})
 if corrections:
  # 这些既有待核均已得到对应局部双模型证据；2014专名仍保留拼写待核。
  d['previous_pending_resolved_by_local_asr']=d.get('previous_pending_resolved_by_local_asr',d['待核'])
  d['待核']=[]
  if year==2014:d['authority_name_normalization']='root依据已下载CNN原始2008-02-07采访及两处官方互证，明确裁定Arwa Damon；ASR罕名偏差及旧材料Andrew Damon误拼均保留证据，音频不改。'
  d['local_corrections']=corrections
  d['status']='draft_local_asr_checked_not_publication_approved'
  for u,k,s in sentences(d):
   if s.get('待核') and s.get('correction_case'):s.pop('待核',None)
  if year==2021:
   # 两局部模型都没有原主分块产生的重复Of the interview。
   d['excluded_primary_asr_artifacts']=[{'asr_range':[1324,1327],'asr_text':'Of the interview.','reason':'两种局部重识别都从题组提示直接进入Maureen介绍，无重复残片；排除原分块ASR拼接幻觉。','evidence':'局部复识别/2021/b1_group_part.json'}]
 save(p,d);return d

def validate_sentence(s,ctx):
 assert s['en'].strip() and re.search('[\u4e00-\u9fff]',s['zh']),ctx
 assert s['w'],ctx
 used=[]
 for w in s['w']:
  assert w['t'] in ['word','phr','core'] and w['h'] and w['m'],(ctx,w)
  for a,z in w['sp']:
   assert isinstance(a,int) and isinstance(z,int) and 0<=a<z<=len(s['en']),(ctx,w,s['en'])
   assert all(z<=c or a>=v for c,v in used),(ctx,'高亮重叠',w)
   used.append((a,z))
 if s.get('asr_ref'):
  ref=B/s['asr_ref'];assert sha(ref)==s['asr_sha256'],(ctx,'局部证据哈希')
  doc=json.loads(ref.read_text());idx=int(s['asr_pointer'].split('/')[2]);w=doc['recognitions'][idx]['words'];a,z=s['asr_range']
  assert s['words']==w[a:z],(ctx,'局部词索引对应')
  assert s['start']==s['words'][0][1] and s['end']==s['words'][-1][2],ctx

def merge(year,formal):
 p=B/f'译注草稿/{year}.json';before_text=p.read_text();d=json.loads(before_text);original=[];counts=[]
 duplicates=copy.deepcopy(d.get('instruction_merge',{}).get('existing_instruction_duplicates',[]))
 for u in d['units']:
  old=[s for s in u['sentences'] if s.get('instruction_source')!=f'说明语句/{year}.json']
  f=next(x for x in formal['units'] if x['id']==u['id'])
  formal_lookup={instruction_fingerprint(s['en']):(k,j) for k,v in f.items() if isinstance(v,list) for j,s in enumerate(v,1)}
  retained=[]
  for j,s in enumerate(old):
   match=formal_lookup.get(instruction_fingerprint(s['en'])) if s.get('role')!='question' else None
   if match:
    entry={'unit':u['id'],'original_index':j,'original':copy.deepcopy(s),'matched_new_slot':match[0],'matched_new_position':match[1],'reason':'原草稿未标role的正式过渡与实际ASR说明语义逐词相同，保留原对象登记后由新说明只呈现一次。'}
    if not any(x['unit']==u['id'] and x['original']==s for x in duplicates):duplicates.append(entry)
   else:retained.append(s)
  old=retained
  original.append(copy.deepcopy(old));body=[s for s in old if s.get('role')!='question'];questions=[s for s in old if s.get('role')=='question']
  def prepared(slot):
   ss=copy.deepcopy(f.get(slot,[]))
   for i,s in enumerate(ss,1):
    s['speaker']='announcer';s['instruction_source']=f'说明语句/{year}.json';s['instruction_slot']=slot;s['instruction_id']=f'{u["id"]}-{slot}-{i}'
    if 'asr_ref' not in s:s['asr_ref']=formal['source']['asr'];s['asr_sha256']=formal['source']['asr_sha256'];s['asr_pointer']=''
   return ss
  u['sentences']=prepared('before')+body+prepared('before_questions')+questions+prepared('after')
  u['instruction_review']={'source':f'说明语句/{year}.json','source_sha256':sha(D/f'{year}.json'),'status':formal['status'],'待核':formal['待核']}
  assert [s for s in u['sentences'] if not s.get('instruction_source')]==old,(year,u['id'],'正文题干必须保持原对象及顺序')
  counts.append({'unit':u['id'],'body_and_questions':len(old),'instructions_added':len(u['sentences'])-len(old),'total':len(u['sentences'])})
 for u in d['units']:
  for i,s in enumerate(u['sentences']):
   # 普通主ASR ref的结构是直接words，不走局部识别JSON指针分支。
   if s.get('asr_pointer')=='':
    marker=s.pop('asr_ref');validate_sentence(s,(year,u['id'],i));s['asr_ref']=marker
   else:validate_sentence(s,(year,u['id'],i))
  q=[s['n'] for s in u['sentences'] if s.get('role')=='question']
  if u['id'].endswith('B1'):assert q==list(range(1,6)),(year,u['id'],q)
  if u['id'].endswith('B2'):assert q==list(range(6,11)),(year,u['id'],q)
 assert p.read_text()==before_text,(year,'检测到他人并发修改，请重新读稿再合并')
 d['instruction_merge']={'source':f'说明语句/{year}.json','source_sha256':sha(D/f'{year}.json'),'body_and_question_objects_sha256':digest(original),'existing_instruction_duplicates':duplicates,'status':'已按播放顺序合入；全文词汇span已重查，不签发approved'}
 save(p,d)
 return {'year':year,'units':counts,'draft_sha256':sha(p),'original_body_and_questions_sha256':digest(original),'formal_sha256':sha(D/f'{year}.json'),'pending':formal['待核']}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--years',type=int,nargs='+',default=M.YEARS);ap.add_argument('--merge',action='store_true');a=ap.parse_args();rows=[]
 for y in a.years:
  f=adjudicate(y)
  if a.merge:rows.append(merge(y,f))
  print(y,'local corrections',len(f.get('local_corrections',[])),'pending',len(f['待核']),'merged',a.merge,flush=True)
 if rows:
  old=json.loads((D/'合并核查汇总.json').read_text())['rows'] if (D/'合并核查汇总.json').exists() else []
  byyear={x['year']:x for x in old};byyear.update({x['year']:x for x in rows});allrows=[byyear[y] for y in sorted(byyear)]
  save(D/'合并核查汇总.json',{'years':sorted(byyear),'rows':allrows,'status':'内容及真实span校验通过；正式音画发布仍由root最终核定'})
if __name__=='__main__':main()
