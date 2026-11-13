"""核对正式说明主/局部词索引、来源SHA、合并位置及全文真实词条span。"""
import hashlib,json,re
from pathlib import Path
B=Path(__file__).resolve().parents[1];YEARS=list(range(2009,2020))+list(range(2021,2025))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for y in YEARS:
 f=json.loads((B/f'说明语句/{y}.json').read_text());main=json.loads((B/f['source']['asr']).read_text());assert sha(B/f['source']['asr'])==f['source']['asr_sha256'];count=0
 for u in f['units']:
  for slot,v in u.items():
   if not isinstance(v,list):continue
   for s in v:
    count+=1;assert s['role'] in ['instruction','transition']
    if s.get('asr_pointer'):
     p=B/s['asr_ref'];assert sha(p)==s['asr_sha256'];doc=json.loads(p.read_text());words=doc['recognitions'][int(s['asr_pointer'].split('/')[2])]['words'];a,z=s['asr_range'];assert s['words']==words[a:z]
     assert s['start']==s['words'][0][1] and s['end']==s['words'][-1][2]
     for q in s.get('proper_name_audio_anchors',[]):
      a,z=q['asr_range'];assert q['start']==words[a][1] and q['end']==words[z-1][2];a,z=q['char'];assert s['en'][a:z]==q['text']
     if s.get('proper_name_normalization'):
      q=s['proper_name_normalization'];assert sha(B/q['evidence_ref'])==q['evidence_sha256']
    else:
     a,z=s['asr_range'];assert s['asr_text']==' '.join(x[0] for x in main[a:z]),(y,s['en'])
 d=json.loads((B/f'译注草稿/{y}.json').read_text());inst=[s for u in d['units'] for s in u['sentences'] if s.get('instruction_source')];assert len(inst)==count
 assert d['instruction_merge']['source_sha256']==sha(B/f'说明语句/{y}.json')
 for u in d['units']:
  if u['id'].endswith('B1'):assert [s['n'] for s in u['sentences'] if s.get('role')=='question']==list(range(1,6))
  if u['id'].endswith('B2'):assert [s['n'] for s in u['sentences'] if s.get('role')=='question']==list(range(6,11))
  slots=[s.get('instruction_slot','question' if s.get('role')=='question' else 'body') for s in u['sentences']]
  order={'before':0,'body':1,'before_questions':2,'question':3,'after':4};assert slots==sorted(slots,key=order.get),(y,u['id'],slots)
  for i,s in enumerate(u['sentences']):
   assert s['en'].strip() and re.search('[\u4e00-\u9fff]',s['zh']) and s['w'],(y,u['id'],i)
   used=[]
   for w in s['w']:
    for a,z in w['sp']:
     assert 0<=a<z<=len(s['en']),(y,u['id'],i,w);assert all(z<=c or a>=e for c,e in used);used.append((a,z))
 rows.append({'year':y,'instructions':count,'body_and_questions':sum(not s.get('instruction_source') for u in d['units'] for s in u['sentences']),'pending_formal':len(f['待核']),'duplicates_removed':len(d['instruction_merge'].get('existing_instruction_duplicates',[])),'formal_sha256':sha(B/f'说明语句/{y}.json'),'draft_sha256':sha(B/f'译注草稿/{y}.json')})
report={'years':YEARS,'rows':rows,'instruction_count':sum(x['instructions'] for x in rows),'checks':['主/局部ASR来源哈希严格对应','普通说明原词逐字对应主ASR索引','恢复说明严格对应局部指针/索引/哈希/实际词时刻','权威专名对应实际整个人名声锚与原始来源证据','15年按before→正文→before_questions→题干→after顺序合入','每年10题编号完整','全文词条真实字符span有效且不重叠'],'publication_approved':False}
(B/'说明语句/全量内容核查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS',len(YEARS),'years',report['instruction_count'],'instructions','formal pending',sum(x['pending_formal'] for x in rows),'duplicates deduplicated',sum(x['duplicates_removed'] for x in rows))
