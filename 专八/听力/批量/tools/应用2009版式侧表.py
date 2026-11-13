"""按完整英文和明确旧新原文裁决，将2009旧技术版式侧表安全重锚到含formal母稿。

不运行旧精听2009分屏补充.py，不按旧序号覆盖，不改变英文/真实音轨时刻。
"""
import copy,hashlib,json,re
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def spans(text,fragment):return [m.span()for m in re.finditer(re.escape(fragment),text)]
# 原技术侧表30项之外的10个真实语境内容词/搭配。逐项定位，不与已有词注重叠。
EXTRA=[
('2009-A','No doubt in other parts','put forward','phr','put forward','phr. 提出（理论或观点）'),
('2009-A','My task today is','write up','phr','write up','phr. 撰写；写成完整报告'),
('2009-A','In doing this, you are','long-established','word','long-established','adj. 由来已久的；长期确立的'),
('2009-A','Moreover, like the storyteller','storyteller','word','storyteller','n. 讲故事的人；说书人'),
('2009-A','In reality, however, the marker','assessing','word','assess','v. 评价；评估'),
('2009-A','In short, you should write','knowledge','word','knowledge','n. 知识；了解'),
('2009-A','At this early stage','evidence','word','evidence','n. 证据；依据'),
('2009-A','You will need, therefore','develop the habit of','phr','develop the habit of','phr. 养成……的习惯'),
('2009-B1','By becoming involved in Toastmasters','audience','word','audience','n. 听众；观众'),
('2009-B2','As an individual continues to give speeches','progresses','word','progress','v. 逐步提高；取得进步')]
def main():
 mother=B/'译注草稿/2009.json';sidefile=B/'核验/精听2009版式补充.json';decfile=B/'核验/2009-末轮原文裁决.json'
 draft=json.loads(mother.read_text());before=copy.deepcopy(draft);mother_before_sha=sha(mother);side=json.loads(sidefile.read_text());side_before_sha=sha(sidefile);dec=json.loads(decfile.read_text());units={u['id']:u for u in draft['units']}
 changes={(x['unit'],x['old_en']):x['en']for x in dec['changes']};reanchors=[];added=[];skipped=[];split_audit=[];short_titles=[]
 def current(uid,en):
  old=en
  while (uid,en)in changes and changes[(uid,en)]!=en:en=changes[(uid,en)]
  matches=[(i,s)for i,s in enumerate(units[uid]['sentences'],1)if s['en']==en]
  assert len(matches)==1,('完整EN未唯一对应当前母稿',uid,old,en)
  n,s=matches[0];assert s.get('role')!='question'
  if old!=en:reanchors.append({'unit':uid,'old_en':old,'new_en':en,'decision_ref':'核验/2009-末轮原文裁决.json','current_ordinal_hint':n})
  return n,s
 def anchor_note(old_en,new_en,note):
  out=copy.deepcopy(note);out['sp']=[]
  for a,b in note['sp']:
   fragment=old_en[a:b];old_hits=spans(old_en,fragment);new_hits=spans(new_en,fragment);assert len(old_hits)==len(new_hits)>0,(note,fragment)
   assert (a,b)in old_hits;out['sp'].append(list(new_hits[old_hits.index((a,b))]))
  out['t']='phr'if ' 'in out['h']else'word';return out
 for unit_side in side['units']:
  uid=unit_side['id'];u=units[uid];short_titles.append({'unit':uid,'old':u['title'],'new':unit_side['title']});u['title']=unit_side['title'];u['names']=list(dict.fromkeys([*u.get('names',[]),*unit_side.get('names',[])]))
  for row in unit_side['vocabulary_additions']:
   old_en=row['en'];n,s=current(uid,old_en);row.setdefault('legacy_ordinal_hint',row.get('k'));row['k']=n;row['old_en']=row.get('old_en',old_en);row['en']=s['en'];row['add']=[anchor_note(old_en,s['en'],note)for note in row['add']]
  for row in unit_side['split_records']:
   old_en=row['en'];n,s=current(uid,old_en);row.setdefault('legacy_ordinal_hint',row.get('ordinal_hint'));row['ordinal_hint']=n;row['old_en']=row.get('old_en',old_en);row['en']=s['en'];plan=row['plan']
   at=plan['at'];anchors=[at]if isinstance(at,str)else list(at);anchors=[a.replace('as if it would','as if it will').replace('or serving as a','or serving as')for a in anchors]
   assert all(s['en'].count(a)==1 for a in anchors),(uid,n,anchors)
   cuts=[s['en'].index(a)for a in anchors];assert cuts==sorted(cuts)and len(set(cuts))==len(cuts)and all(c>0 for c in cuts)
   plan['at']=anchors[0]if isinstance(at,str)else anchors
   if ''.join(plan['zh'])!=s['zh']:
    # 最新语言复核把invariably明确译为“总是”，不回退到旧技术快照的“往往”。
    assert s['en'].startswith('Moreover, like the storyteller'),(uid,n,'中文差异未审',s['zh'],plan['zh'])
    plan['zh']=['而且，像旧时的说书人一样，尽管你总是在向已经相当了解这个故事的人讲述，','仍然应当把它当作一个从未被听过的故事来讲。']
   assert ''.join(plan['zh'])==s['zh'] and len(plan['zh'])==len(anchors)+1
   row['zh']=s['zh'];s['zh']=''.join(plan['zh']);row['status']='已按当前完整EN和中文精确重锚；仅版式候选，真实音轨换屏须在导出后复核'
   split_audit.append({'unit':uid,'en':s['en'],'current_ordinal_hint':n,'at':plan['at'],'zh':plan['zh'],'chinese_reassembles_exactly':True})
  unit_side['apply_rule']='只按unit+en整句完全一致匹配；k/ordinal_hint均仅阅读定位，不准按序号套用含formal的新稿。所有sp已按新EN逐字定位，旧snapshot/base_sha256仅历史记录。'
 # 增加明确的10项内容词，构成完整40项，不添加虚词凑数。
 for uid,prefix,fragment,typ,head,meaning in EXTRA:
  matches=[(n,s)for n,s in enumerate(units[uid]['sentences'],1)if s['en'].startswith(prefix)];assert len(matches)==1,(uid,prefix);n,s=matches[0];hit=spans(s['en'],fragment);assert len(hit)==1,(uid,fragment);a,b=hit[0];note={'t':typ,'h':head,'m':meaning,'sp':[[a,b]]};unit_side=next(u for u in side['units']if u['id']==uid)
  row=next((r for r in unit_side['vocabulary_additions']if r['en']==s['en']),None)
  if row is None:row={'k':n,'en':s['en'],'add':[]};unit_side['vocabulary_additions'].append(row)
  if not any(w['h']==head and w['sp']==[[a,b]]for w in row['add']):row['add'].append(note)
 for unit_side in side['units']:
  uid=unit_side['id']
  for row in unit_side['vocabulary_additions']:
   n,s=current(uid,row['en']);occupied=[(a,b)for w in s['w']for a,b in w['sp']]
   for note in row['add']:
    identical=next((w for w in s['w']if w['h']==note['h']and w['sp']==note['sp']),None)
    if identical:skipped.append({'unit':uid,'en':s['en'],'note':note,'reason':'同词同span已存在，去重'});continue
    for a,b in note['sp']:
     assert 0<=a<b<=len(s['en'])and all(not(a<y and x<b)for x,y in occupied),(uid,n,'词注span重叠',note,occupied)
    s['w'].append(copy.deepcopy(note));occupied.extend(map(tuple,note['sp']));added.append({'unit':uid,'en':s['en'],'note':note,'anchor_text':[s['en'][a:b]for a,b in note['sp']]})
   s['w'].sort(key=lambda w:w['sp'][0][0])
 # 校验：全部源文、时间及已有ASR字段逐字/逐项不变，所有新旧词注完整且互不重叠。
 invariant_keys=['en','start','end','word_alignment','alignment','words','asr_ref','asr_sha256','asr_pointer','asr_range']
 for old_u,new_u in zip(before['units'],draft['units']):
  assert old_u['id']==new_u['id']and len(old_u['sentences'])==len(new_u['sentences'])
  for old_s,s in zip(old_u['sentences'],new_u['sentences']):
   assert {k:old_s.get(k)for k in invariant_keys}=={k:s.get(k)for k in invariant_keys}
   assert old_s['zh']==s['zh'],'保留最新语言复核中文，不回退旧译文'
   occupied=[]
   for w in s['w']:
    for a,b in w['sp']:
     assert 0<=a<b<=len(s['en'])
     assert not(a>0 and s['en'][a-1].isalnum()and s['en'][a].isalnum())
     assert not(b<len(s['en'])and s['en'][b-1].isalnum()and s['en'][b].isalnum())
     assert all(not(a<y and x<b)for x,y in occupied),(new_u['id'],s['en'],w,'现有或新增词注重叠')
     occupied.append((a,b))
 assert sum(len(r['add'])for u in side['units']for r in u['vocabulary_additions'])==40
 assert len(split_audit)==17
 assert sha(mother)==mother_before_sha and sha(sidefile)==side_before_sha,'并发修改，拒绝覆盖'
 dump(mother,draft);after_sha=sha(mother)
 side['scope']='40项真实语境词注、短标题/names及17处保义中文分屏；已按明确旧新EN裁决重锚到当前含formal母稿，不改英文/音轨时刻；换屏仍须真实词锚核验。'
 side['source_mother_sha256_before']=mother_before_sha;side['source_mother_sha256_after']=after_sha;side['adjudication_sha256']=sha(decfile);side['status']='reanchored_current_mother_layout_candidate'
 for u in side['units']:u['source_mother_sha256']=after_sha
 dump(sidefile,side)
 proof={'status':'2009当前母稿版式合并与侧表重锚完成；非最终音画审批','before_mother_sha256':mother_before_sha,'after_mother_sha256':after_sha,'before_side_sha256':side_before_sha,'after_side_sha256':sha(sidefile),'source_adjudication_sha256':sha(decfile),'English_and_timing_unchanged':True,'latest_chinese_preserved':True,'all_spans_full_and_nonoverlapping':True,'all_17_splits_chinese_reassemble':True,'new_vocabulary_count':len(added),'already_present_vocabulary_count':len(skipped),'side_vocabulary_count':40,'counts_before':{u['id']:sum(len(s['w'])for s in u['sentences'])for u in before['units']},'counts_after':{u['id']:sum(len(s['w'])for s in u['sentences'])for u in draft['units']},'short_titles':short_titles,'reanchors':reanchors,'vocabulary_added':added,'splits':split_audit}
 dump(B/'核验/2009-版式侧表重锚核验.json',proof)
 print(json.dumps({k:proof[k]for k in ['new_vocabulary_count','side_vocabulary_count','counts_before','counts_after','English_and_timing_unchanged','all_17_splits_chinese_reassemble']},ensure_ascii=False))
if __name__=='__main__':main()
