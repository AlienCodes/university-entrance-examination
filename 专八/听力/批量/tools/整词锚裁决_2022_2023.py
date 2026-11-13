"""为已确证拼写/罕名/连读给实际整个词或词组声锚，不按拼写推算内部时间。
所有原ASR词、SHA、指针及索引保留；不用更改正文词形来迎合ASR错误标签。
"""
import json,hashlib,re,copy
from pathlib import Path
B=Path(__file__).resolve().parents[1];O=B/'核验/正文异文复核'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# year,unit,唯一正文片段,真实源文字,证据case,原始词range,属性,具体裁决
T=[
(2022,'B1','Now, Harriet, can you tell','Harriet','harriet_filler',[7,8],'proper_name_audio_anchors','源页及本访谈多次明确Harriet Sanford；独立Whisper该处正确Harriet，Parakeet Harry是人名误识。'),
(2022,'B1','How do EverFi and','EverFi','everfi',[12,13],'proper_name_audio_anchors','源页品牌EverFi，独立Whisper同；Parakeet Everphi为罕名拼写偏差。'),
(2022,'B1','foundation and EverFi work','EverFi','everfi',[24,25],'proper_name_audio_anchors','源页品牌EverFi，独立Whisper同；Parakeet Everphy为罕名拼写偏差。'),
(2022,'B2','the bulb I mean','bulb','bulb',[14,15],'reviewed_word_audio_anchors','源页灯具light source语境唯一为bulb，独立Whisper清楚bulb；Parakeet bowl是该词错标签，采用同一个实际整词范围。'),
(2022,'B1','Um, I see. Now, Harriet','Um','harriet_filler',[3,4],'reviewed_interjection_audio_anchors','源页Um为非词性应声写法，局部Parakeet Hmm与Whisper Mm都确认真实应声；用实际整个Hmm声音范围，不造拼写内或独立字母时刻。'),
(2023,'A','the metaphor’s source','metaphor’s source','metaphor',[10,12],'reviewed_phrase_audio_anchors','源页规范所有格metaphor’s source，两模型连读标作metaphor source；保留规范原文，把整个二词组绑定实际二词声锚，不猜所有格-s内部时刻。'),
(2023,'B1','friends with some experience of gap year','gap year','gapyear',[10,11],'reviewed_phrase_audio_anchors','所供源页明确gap year，整个访谈反复解释间隔年，紧连读音被两模型拼作Dapia/gapia；源文语义及真实整体0.56秒连读锚对应，不教成不存在的Dapia，也不拆出虚假两词内部时间。'),
(2023,'B2','climbing Mount Qomolangma','Qomolangma','qomolangma',[21,22],'proper_name_audio_anchors','源页Mount Qomolangma规范罗马字，Parakeet Komolangma/Whisper Como Langma为同一山名音译写法；整个专名共用实际一词声锚。'),
]
changes=[]
for year in [2022,2023]:
 p=B/f'译注草稿/{year}.json';text=p.read_text();d=json.loads(text);protected=[copy.deepcopy(s) for u in d['units'] for s in u['sentences'] if s.get('instruction_source') or s.get('role')=='question']
 for y,uid,frag,surface,case,rr,field,decision in T:
  if y!=year:continue
  u=next(x for x in d['units'] if x['id']==f'{year}-{uid}');ss=[s for s in u['sentences'] if not s.get('instruction_source') and s.get('role')!='question' and frag in s['en']];assert len(ss)==1,(y,case,frag)
  s=ss[0];a=s['en'].index(surface);ep=O/str(y)/(case+'.json');e=json.loads(ep.read_text());w=e['recognitions'][0]['words'];i,j=rr;assert 0<=i<j<=len(w)
  v={'text':surface,'char':[a,a+len(surface)],'asr_ref':str(ep.relative_to(B)),'asr_sha256':sha(ep),'asr_pointer':'/recognitions/0/words','asr_range':rr,'start':w[i][1],'end':w[j-1][2],'method':'整个字词/词组使用实际ASR声锚，不依据规范拼写猜词内时间。','decision':decision,'source_refs':u['source_refs'],'status':'已记录具体证据对应，不冒称整个单元approved'}
  arr=s.setdefault(field,[]);arr[:]=[x for x in arr if x['text']!=surface];arr.append(v);changes.append({'year':y,'unit':u['id'],'en':s['en'],'field':field,'anchor':v})
 if year==2023:
  u=d['units'][0];s=next(s for s in u['sentences'] if not s.get('instruction_source') and 'The Dow fell like a brick' in s['en']);a=s['en'].index('Dow');ep=B/'预处理/2023/识别.json';w=json.loads(ep.read_text());i=next(i for i,x in enumerate(w) if x[0]=='DAO.' and 425<x[1]<427)
  v={'text':'Dow','char':[a,a+3],'asr_ref':str(ep.relative_to(B)),'asr_sha256':sha(ep),'asr_pointer':'','asr_range':[i,i+1],'start':w[i][1],'end':w[i][2],'method':'整个金融指数专名Dow与原音实际同音DAO词锚对应，不猜字母时刻。','decision':'源页财经隐喻引文The Dow fell like a brick，指道琼斯指数；DAO为同音转写，并非此处人名或其他实体。','source_refs':u['source_refs'],'status':'具体源词与实际整词声锚对应'}
  arr=s.setdefault('proper_name_audio_anchors',[]);arr[:]=[x for x in arr if x['text']!='Dow'];arr.append(v);changes.append({'year':year,'unit':u['id'],'en':s['en'],'field':'proper_name_audio_anchors','anchor':v})
 for u in d['units']:
  for s in u['sentences']:
   for field in ['proper_name_audio_anchors','reviewed_word_audio_anchors','reviewed_phrase_audio_anchors','reviewed_interjection_audio_anchors']:
    for v in s.get(field,[]):a,z=v['char'];assert s['en'][a:z]==v['text']
   used=[]
   for w in s['w']:
    for a,z in w['sp']:assert 0<=a<z<=len(s['en']);assert all(z<=c or a>=e for c,e in used);used.append((a,z))
 assert protected==[s for u in d['units'] for s in u['sentences'] if s.get('instruction_source') or s.get('role')=='question']
 assert p.read_text()==text,(year,'并发更新需重读')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
(O/'整词声锚裁决.json').write_text(json.dumps({'changes':changes,'principle':'所有时间来自原ASR真实整个词或词组声锚；不推测人名、所有格、连读或拼写的内部时间。'},ensure_ascii=False,indent=2)+'\n');print('整个字词/词组真声锚',len(changes),'项，char与span全量通过')
