"""只读审计2022/2023六篇及2024-B2，不写源文批准、registry或renderer。
依赖已做的423句人工语义审阅、原音/PDF复核及逐项局部音证；新快照不满足条件即hold。
"""
from pathlib import Path
import copy,hashlib,json,re,sys,datetime
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B/'tools'))
from 精听数据 import content_sha,validate,resolve_manual_splits,first_aligned_word
O=B/'核验/剩余源审核候选';O.mkdir(exist_ok=True)
H=lambda data:hashlib.sha256(data).hexdigest()
def sha(path):return H(path.read_bytes())
def load(rel):return json.loads((B/rel).read_text())
def sem(u):return {k:copy.deepcopy(u.get(k,[] if k in ['names','manual_splits'] else None)) for k in ['id','section','title','names','manual_splits']}|{'sentences':[{k:copy.deepcopy(s[k]) for k in ['en','zh','w']} for s in u['sentences']]}
def digest(obj):return H(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def pointer(obj,p):
 for k in p.strip('/').split('/') if p else []:obj=obj[int(k)] if isinstance(obj,list) else obj[k]
 return obj
extra=load('核验/剩余源审核候选/额外ASR逐项裁决.json');sourceproof=B/'核验/剩余源审核候选/原音及材料引用复核.json';summary=[]
for year in [2022,2023,2024]:
 mp=B/f'译注草稿/{year}.json';mb=mp.read_bytes();mother=json.loads(mb);rp=B/f'核验/原文对齐/{year}/对齐报告.json';rb=rp.read_bytes();report=json.loads(rb);ap=B/report['inputs']['asr'];asrb=ap.read_bytes();raw=json.loads(asrb);prep=load(f'预处理/{year}/原音准备.json')
 for unit in mother['units']:
  uid=unit['id']
  if year==2024 and uid!='2024-B2':continue
  fp=B/f'精听数据/{uid}.json';block=[];notes=[];events=[];anchor_records=[];differences=[];pending=[];refs=[]
  def check(ok,label):
   if not ok:block.append(label)
   return bool(ok)
  def evidence(rel,expected=None):
   p=B/rel
   if not p.exists():check(False,'证据文件缺失：'+rel);return None
   actual=sha(p)
   if expected:check(actual==expected,'证据SHA不符：'+rel)
   if not any(x['file']==rel for x in refs):refs.append({'file':rel,'sha256':actual})
   return json.loads(p.read_text()) if p.suffix=='.json' else p.read_text()
  check(report['inputs']['draft_sha256']==H(mb),'年度对齐报告不是当前母稿SHA，须early刷新后再审')
  check(report['inputs']['asr_sha256']==H(asrb),'有效ASR已变化，报告SHA失效')
  check(report['inputs']['canonical_source_sha256']==prep['canonical']['sha256'],'报告canonical与原音准备不一致')
  if not fp.exists():
   out={'id':uid,'recommendation':'hold','status':'source-review-candidate-only','source_approved':False,'blocking':['最新可制作精听数据不存在，须early完成真实边界导出'],'mother_file_sha256':H(mb),'mother_semantic_sha256':digest(sem(unit))};(O/f'{uid}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');summary.append({'id':uid,'recommendation':'hold','blocking':out['blocking']});continue
  fb=fp.read_bytes();f=json.loads(fb);same=sem(unit)==sem(f);check(same,'母稿title/names/section/en/zh/w/manual_splits与当前final不一致')
  if block:
   out={'id':uid,'recommendation':'hold','status':'source-review-candidate-preflight-stale-inputs','source_approved':False,'blocking':block,'current':{'mother_file_sha256':H(mb),'mother_semantic_sha256':digest(sem(unit)),'final_file_sha256':H(fb),'final_semantic_sha256':digest(sem(f)),'semantic_exact':same,'report_draft_sha256':report['inputs']['draft_sha256'],'report_asr_sha256':report['inputs']['asr_sha256'],'current_asr_sha256':H(asrb)},'disposition':'输入版本未闭环，未用新的ASR行号审旧final，不宣称任何旧缺词/锚结果为当前事实。待early刷新后重跑。','completed_independent_evidence':['423句EN/ZH/词注已读','原音及材料引用复核.json','额外ASR逐项裁决.json']}
   (O/f'{uid}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');summary.append({'id':uid,'recommendation':'hold','blocking':block});print(uid,'hold preflight',len(block),flush=True);continue
  try:validate(f,draft=True)
  except BaseException as e:check(False,'数据约束检查失败：'+str(e))
  if f.get('review',{}).get('content_sha256'):check(f['review']['content_sha256']==content_sha(f),'final自身review.content_sha256与当前内容不一致')
  prov=report.get('ASR_provenance',{});check(prov.get('canonical_and_ASR_sha_verified') is True,'缺真实ASR canonical来源登记');evidence(prov['file'],prov.get('sha256')) if prov.get('file') else None
  check(f['audio']['sha256']==prep['canonical']['sha256'],'final原音SHA不符');boundary=f['audio'].get('boundary_evidence',{});check(boundary.get('status')=='measured_PCM_boundaries_or_complete_file_edge','源窗口缺真实PCM边界核验');check(boundary.get('canonical_sha256')==f['audio']['sha256'],'边界证据canonical SHA不符');check(boundary.get('window')==f['audio']['window'],'边界实测窗与final窗口不一致')
  source_total=mapped=nonverbal=acoustic_missing=word_segments=0;external_rows=[];all_word_records=[];missing_rows=[];question_rows=[]
  for n,s in enumerate(f['sentences'],1):
   al=s.get('alignment',{});source_total+=al.get('source_lexemes',0);mapped+=al.get('mapped_lexemes',0)
   if s.get('role')=='question':question_rows.append(s)
   missing=al.get('missing',[]);legal=None
   if al.get('whole_sentence_audio_coverage_verified'):
    legal='verified_whole_sentence_acoustic_event';ev=al['whole_sentence_audio_coverage_verified'];events.append({'sentence':n,'en':s['en'],'kind':legal,'start':s['start'],'end':s['end'],'unknown_words_without_fake_word_times':missing,'evidence':ev})
   elif s.get('nonverbal'):
    legal='verified_nonverbal_event';nonverbal+=al.get('nonverbal_not_words',0);ev=al.get('nonverbal_evidence',{});events.append({'sentence':n,'en':s['en'],'kind':legal,'start':s['start'],'end':s['end'],'evidence':ev});check(not s.get('word_alignment'),'非言语整事件不应伪造逐词时刻')
   elif al.get('acoustic_filler_boundary'):
    ev=al['acoustic_filler_boundary'];allowed=all(re.fullmatch(r'(eh|ah|um|emm|mm|hmm|ha)',x['text'],re.I) for x in missing)
    if allowed:legal='verified_interjection_acoustic_boundary';acoustic_missing+=len(missing);events.append({'sentence':n,'en':s['en'],'kind':legal,'start':s['start'],'end':s['end'],'missing_not_word_timed':missing,'evidence':ev})
   if missing:
    missing_rows.append({'sentence':n,'en':s['en'],'missing':missing,'disposition':legal or 'unresolved'});check(bool(legal),'内部原文缺词尚无合法整句/非词声学例外：'+s['en'])
   check(al.get('boundary_anchored') or bool(legal),'句首尾无真实词锚或合法整事件：'+s['en'])
   for w in s.get('word_alignment',[]):
    word_segments+=1;all_word_records.append(w)
    if w.get('asr_indices'):
     rows=[raw[i] for i in w['asr_indices']];check(abs(w['start']-min(x[1] for x in rows))<1e-6 and abs(w['end']-max(x[2] for x in rows))<1e-6,'逐词时刻并非实际有效ASR行边界：'+s['en'][w['char']:w['char_end']])
    elif w.get('whole_reviewed_ASR_span'):
     ev=evidence(w['evidence_ref'],w.get('evidence_sha256'));aa,zz=w['asr_range'];rows=pointer(ev,w.get('asr_pointer',''))[aa:zz] if ev is not None else [];check(rows==w['asr_words'],'外部整词锚未匹配原证据实际行');check(bool(rows) and abs(w['start']-min(x[1] for x in rows))<1e-6 and abs(w['end']-max(x[2] for x in rows))<1e-6,'外部整词锚时刻不是真实行边界');external_rows.extend(rows);anchor_records.append({'sentence':n,'en':s['en'],'source_text':s['en'][w['char']:w['char_end']],'actual_ASR_rows':rows,'evidence_ref':w['evidence_ref'],'evidence_sha256':w.get('evidence_sha256'),'disposition':'完整真实声段共享；没有估计词内边界'})
    else:check(False,'词锚既无有效ASR行又无已核外部实际行')
  for ev in events:
   data=ev.get('evidence',{})
   if isinstance(data,dict):
    rel=data.get('evidence_ref',data.get('asr_ref'));expected=data.get('evidence_sha256',data.get('asr_sha256'))
    if rel:evidence(rel,expected)
   check(ev['start']<ev['end'],'整事件真实窗口无效')
  # 对齐差异逐项处置；插入候选必须有局部真音裁决或明确外部整词覆盖。
  lo,hi=f['audio']['window']
  for diff in report['differences']:
   src=diff.get('source',[]);window=diff.get('window');relevant=any(x['unit']==uid for x in src) if src else bool(window and lo<=window[0] and window[1]<=hi)
   if not relevant:continue
   dd=copy.deepcopy(diff)
   if diff['kind']=='insert':
    rows=[raw[i] for i in diff.get('asr_indices',[])]
    if rows and all(row in external_rows for row in rows):dd['audit_disposition']='已由有证据的同一真实外部整词锚覆盖，是拼写/同音识别差异，非遗漏口述。'
    else:
     candidates=[x for x in extra['decisions'] if x['year']==year and x['canonical_source_sha256']==f['audio']['sha256'] and window and x['analysis_window'][0]<=window[0] and window[1]<=x['analysis_window'][1]]
     if candidates:
      c=min(candidates,key=lambda x:abs(sum(x['original_ASR_candidate']['window'])/2-sum(window)/2));dd['audit_disposition']=c['decision'];dd['adjudication']=copy.deepcopy(c);evidence(c['evidence_ref'],c['evidence_sha256'])
     else:dd['audit_disposition']='尚无该ASR额外段的明确实音裁决';check(False,'ASR额外段待核：'+repr(diff.get('asr_text'))+' '+str(window))
   elif diff['kind']=='normalized_or_reviewed_mapping':
    dd['audit_disposition']='已读中文/语境与原文；采用工具严格正字法/数词/缩写等价或明确局部人工完整词锚，不作否定/词形模糊合并。'
   else:
    dd['audit_disposition']='逐句语义已读；最终原文字符在实际词锚/已核完整声段中覆盖；保留具体局部人名/拼写及真实口述异文证据，未为配ASR改写。'
    dd['human_decisions']=[x for x in report.get('human_decisions',[]) if x.get('unit')==uid and any(x.get('sentence')==q['sentence'] for q in src)]
    dd['external_anchors']=[x for x in anchor_records if any(x['sentence']==q['sentence'] for q in src)]
    dd['whole_events']=[x for x in events if any(x['sentence']==q['sentence'] for q in src)]
   differences.append(dd)
  for item in report.get('decision_inputs',[]):
   rel=item.get('file');evidence(rel,item.get('sha256')) if rel else None
  for origin,items in [('mother',unit.get('待核',[])),('formal',unit.get('instruction_review',{}).get('待核',[])),('final',f.get('待核',[]))]:
   for item in items:
    generic='程序仅绑定ASR候选' in item
    pending.append({'origin':origin,'text':item,'disposition':'本候选已逐项核对真实词锚、全部对齐差异与额外ASR局部证据；待root最终源审签署后清除此通用门禁，当前不自行批准。' if generic else '真实未决项，须人工解决或提供明确证据','blocking':not generic});check(generic,'仍有具体待核项：'+item)
  plans=resolve_manual_splits(unit);plan_checks=[]
  for n,plan in plans.items():
   s=f['sentences'][int(n)-1];ats=plan['at'] if isinstance(plan['at'],list) else [plan['at']];cuts=[s['en'].index(x) for x in ats];bound=[0,*cuts,len(s['en'])];first=[]
   for at,c in zip(ats,cuts):
    try:w=first_aligned_word(s.get('word_alignment',[]),s['en'],c);first.append({'at':at,'actual_word':s['en'][w['char']:w['char_end']],'actual_word_start':w['start'],'actual_word_end':w['end'],'disposition':'仅真实首词存在性；实际静音guard与PNG另审'})
    except BaseException as e:check(False,'人工分屏首词无真实锚：'+str(e))
   vocab=all(any(a<=w['sp'][0][0]<z for w in s['w']) for a,z in zip(bound,bound[1:]));check(vocab,'人工分屏存在无实际内容词的屏');plan_checks.append({'en':s['en'],'at':plan['at'],'zh':plan['zh'],'exact_chinese_rejoin':''.join(plan['zh'])==s['zh'],'each_part_has_actual_vocabulary':vocab,'first_words':first})
  # 口述问题逐字与考试数据一致，不重推答案。
  exam=load(f'数据/{year}/试卷.json');qs={q['n']:q['stem'] for q in exam['questions']}
  for s in question_rows:check(re.sub(r'^Question\s+\d+\.\s*','',s['en'])==qs[s['n']],'念题文本与考试stem不一致：'+str(s['n']))
  check(mp.read_bytes()==mb and fp.read_bytes()==fb and rp.read_bytes()==rb,'核验期间源文件并发更新，须锁新SHA重审')
  if events:
   eproof=B/'核验/剩余源审核候选/合法整句声学例外复核.json'
   if eproof.exists():refs.append({'file':str(eproof.relative_to(B)),'sha256':sha(eproof)})
  refs.extend([{'file':str(sourceproof.relative_to(B)),'sha256':sha(sourceproof)},{'file':'核验/剩余源审核候选/额外ASR逐项裁决.json','sha256':sha(O/'额外ASR逐项裁决.json')},{'file':'核验/第二批人工语义分屏/分屏平表.json','sha256':sha(B/'核验/第二批人工语义分屏/分屏平表.json')}])
  result={'id':uid,'status':'source-review-candidate-only','source_approved':False,'recommendation':'hold' if block else 'ready','blocking':block,'scope':'仅建议root批准源EN/中文/词汇/真实锚及原音窗；不批准PNG、实际换屏guard或编码成品。','checked_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current':{'mother_file':str(mp.relative_to(B)),'mother_file_sha256':H(mb),'mother_semantic_sha256':digest(sem(unit)),'final_file':str(fp.relative_to(B)),'final_file_sha256':H(fb),'final_semantic_sha256':digest(sem(f)),'semantic_exact':same,'final_production_content_sha256':content_sha(f),'alignment_report':str(rp.relative_to(B)),'alignment_report_sha256':H(rb),'effective_ASR':report['inputs']['asr'],'effective_ASR_sha256':H(asrb)},'counts':{'sentences':len(f['sentences']),'vocabulary_entries':sum(len(s['w']) for s in f['sentences']),'source_lexemes':source_total,'mapped_lexemes':mapped,'word_alignment_segments':word_segments,'reviewed_external_whole_word_spans':len(anchor_records),'whole_sentence_or_nonword_events':len(events),'nonverbal_lexemes_not_word_timed':nonverbal,'acoustic_interjection_missing_not_word_timed':acoustic_missing,'manual_plans':len(plans),'spoken_questions_checked_against_exam':len(question_rows)},'source_audio':{'canonical_sha256':f['audio']['sha256'],'window':f['audio']['window'],'native_sample_rate':prep['canonical']['sample_rate'],'native_channels':prep['canonical']['channels'],'registered_pcm_sha256':prep['canonical']['pcm_sha256'],'original_source_entries':prep['source_entries'],'boundary_evidence':boundary,'first_sentence':{'en':f['sentences'][0]['en'],'start':f['sentences'][0]['start'],'end':f['sentences'][0]['end']},'last_sentence':{'en':f['sentences'][-1]['en'],'start':f['sentences'][-1]['start'],'end':f['sentences'][-1]['end']},'last_actual_word':all_word_records[-1] if all_word_records else None},'pending_dispositions':pending,'source_missing_dispositions':missing_rows,'legal_whole_sentence_and_nonword_events':events,'external_actual_word_span_evidence':anchor_records,'alignment_difference_dispositions':differences,'source_references':copy.deepcopy(unit.get('source_refs',[])),'source_variant_dispositions':{'recorded_original_audio_checks':copy.deepcopy(unit.get('原音核实记录',[])),'recorded_body_audio_corrections':copy.deepcopy(unit.get('body_audio_corrections',[])),'current_binding_proof_note':'历史修订记录原样保留；本次真实词锚/整句例外的有效证据引用及SHA逐项在本候选另核，不将旧修订时SHA冒称当前文件SHA。'},'bilingual_vocabulary_review':{'all_sentences_and_vocabulary_read':True,'review_total_scope':'423句逐句审阅，包括语境词性/lemma与释义、否定/条件、数值/计量单位、列举和插入语；不独立重推答案。','specific_semantic_checks':{'2022-A':['体质/文化人类学、考古学/语言学/民族志层级及心理人类学归属，材料来源与rather than方法对比均对应。','两位人类学家的研究地域与专名分别成屏，人物与研究对象对应正确。'],'2022-B1':['1969年创立、每年三次资助、6000多名教师及186000多名学生数量准确；未把millions或percent误套。','neither父母完成学业的否定、基金会支持资源及教师追求卓越/关爱学生含义对应。'],'2022-B2':['天文可见度症状与严重后果区别、眩光/光侵扰的术语和定义对应。','not only、not everybody及不反对安保照明的范围正确；本应照亮的区域与邻近窗户/道路分屏无错配。'],'2023-A':['太阳为隐喻源域、朱丽叶为目标域，联觉/认知失调、字面/隐喻真假对比对应。','施事与物体隐喻、二战/越战/中性描述三个条件以及培根引文的三类读法顺序正确。'],'2023-B1':['63%调查赞同的是建设性间隔经历对申请的帮助，几个月/一年与海外志愿/工作经历关系未跨屏错配。','保留原音a year sharp及to put it simple等非标准表达，未为语法改写原音文本。'],'2023-B2':['三到九个月、一个月短期方案、26岁/16岁/90国等数字及所指对应。','四项旅行清单分别成屏，珠峰项think twice未错接其他项目；国籍认同与全球/人类视角对比完整。'],'2024-B2':['2007年比较、南极贡献6英寸与总计3英尺、加速情形可能6英尺以及2100年时间点均对应。','without反事实、even if三个假设、历史累积碳与现在控制排放减速的区别无否定/条件错配；three times faster按该新闻通常用义译三倍并保留来源说明。']}[uid],'known_corrections':'2023-A两处句末逗号句点与look→看起来，见2023-A-三处显示译意修复.json；其他未发现明确错义。','all_sp_valid_and_nonoverlapping':True,'names_exact':f.get('names',[])==unit.get('names',[])},'manual_plan_checks':plan_checks,'evidence':refs,'next':'root阅读本篇具体差异/例外后写源审核及registry；PNG和实际音频换屏guard另审。'}
  (O/f'{uid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');summary.append({'id':uid,'recommendation':result['recommendation'],'blocking':block,'content_sha256':result['current']['final_production_content_sha256']});print(uid,result['recommendation'],'blockers',len(block),block[:3],flush=True)
(O/'汇总.json').write_text(json.dumps({'scope':'7篇只读源审核候选；不自行source-approved','units':summary},ensure_ascii=False,indent=2)+'\n')
