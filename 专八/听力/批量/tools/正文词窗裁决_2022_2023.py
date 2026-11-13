"""逐项裁决已实读的32组正文双模型证据，采纳仅窗口中间可靠词，避开截窗假词。
不改母稿正文；供early验证SHA与JSON指针后组合实际词时刻。"""
import json,re,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];O=B/'核验/正文异文复核'
# 末端词锚含在采纳范围；每项决定指向真实窗口词，不套模板或按字数估时。
TABLE={2022:{
'greeting':('Good morning Harriet','Good morning James','保留原三句问候；原候选额外Good morning为组合ASR伪重复，局部两模型均与源文一致。'),
'underserved':('I did not remain','never faltered','两模型均and underserved，母稿已将in订为and；under-served/underserved仅复合词拼写等价。'),
'education_article':('Adamant that','school time','两模型均a public education；保留源文a，排除原ASR误识have。'),
'harriet_filler':('Hmm I see','Harry','保留真实低声应声，Parakeet Hmm/Whisper Mm；Harriet原专名由源页和Whisper确证，Harry属罕名误识。'),
'grants_number':('Last year','students','两模型均our grants与186,000；已落稿our，不把主ASR180,000/36,000拼接残片当数值。'),
'everfi':('I have heard','learning tools','两路确证EverFi合作内容；Everphi/Everphy为Parakeet对品牌的拼写误识，按源页与独立Whisper规范EverFi。'),
'hundreds':('If they had done','hundreds and hundreds','保留源文两次hundreds；额外第三次为ASR伪重复，两局部模型均无第三次。'),
'light_only':('Light pollution is not only','badly positioned','保留not only light，无第二个only；or lighting确有or；over-lit/overlit是连写等价。'),
'overlit':('So many people','overlit','源文over-lit正确，主ASR he是错词，两局部模型均overlit；不把连字符当正文异文。'),
'emitted_light':('By that I mean','into the sky','三路均a lot of light emitted（无the），母稿已删误印the。'),
'bulb':('The light source itself','a good cover on it','保留源页bulb：独立Whisper明确bulb，Parakeet bowl为错词；原音实际整词锚可审校绑定，不改为碗。')},
2023:{
'following':('In this Elvis is following','definition of metaphor','保留following，两局部模型均正确；排除主ASR followed错词。'),
'metaphor':('We mix and match','in this case the sun','保留原页metaphor’s source规范书写；音频连读两模型写metaphor source，整个词组可整体绑定，不猜所有格-s的内部时刻。'),
'and_in':('Experience of a stimulus','as well','两模型均in another sense organ，母稿已订正and→in；中文按联觉语境重译。'),
'when_where':('A moment of cognitive dissonance','ink','两模型均where the name，母稿已订正when→where；颜色词英美拼写不改原文。'),
'meaning_had':('The test shows','as well','保留have been done；两个局部模型均have，原had及额外meaning均识别伪差。'),
'id_say':("Well I'd say",'creates expectations','保留I’d say；两局部模型恢复真词，排除主ASR at错词。'),
'united_states':('What should they do','just do nothing','实际United Nations，两模型均同；排除主ASR多余States/United，不向正文补假词。'),
'chewed':('Some books are','chewed and digested','保留培根原引文chewed，两模型均正确；原changed为ASR错词。'),
'domain':('Delighted to have invited','spokesperson','保留gapyear.com’s spokesperson；两局部模型均读出网站与所有格，原主ASR省略com’s。'),
'seriously_asked':('Let me first ask','question all the time','保留原源完整问句/asked，两模型恢复；原seriously重复、here/off为分块误识。'),
'life_filler':('But I find','you can have on a gap year','保留完整两句源文；主ASR额外A未在两局部出现。Eh为源页非词性语气记号，需实际声学岛核边界，不删除声音或造词时。'),
'value_it':('In each new location','the best thing I think','保留源文which is the best thing I think，额外it未被两局部确认，排除。'),
'gapyear':('Others may advise','online forums','保留原页gap year；两模型将紧连读音拼作Dapia/gapia，按源页与整段gap year语境核整词组锚，不能教作不存在的Dapia。'),
'project_question':('Which project would you','taking a gap here','保留原完整Which project...taking a gap year；独立Whisper完整确认，聚焦Parakeet给全句真词时（year误拼here）。'),
'time_majority':('A gap year is just timeout','three to nine months','两模型均the majority，母稿已将a订正the；timeout/time-out、gap year为连写等价，不另改正文。'),
'specific_culture':("But you're also learning",'culture and society','两模型均有冠词；主ASR和Parakeet为a，Whisper为the，采用最稳定a并如实保留分歧，未称逐字一致。'),
'travel_lists':('Love to find out','ridiculous as possible','两模型均travel list单数、I think a travel list；母稿已补a，保留list而非主ASR lists。'),
'after_all':('After all','done everything','两局部均有what do you do完整问句，恢复原主漏do；原Ah保留语气声，声学边界另核。'),
'qomolangma':('Number three','think twice','保留Qomolangma规范专名，Komolangma/Como Langma属音译拼写；整个山名词锚绑定，排除原多余Number。'),
'validation':('For me','being in a place','两模型均完整三句，无主ASR to be able to do it伪串；it’ll/it will等价，of being已落稿订正or。'),
'jim':('Well Jim','the interview','两局部明确Jim，保留源页Jim；主ASR Tim为错词，不需要改人名。') }}
NUM=dict(zip('one two three four five six seven eight nine ten twenty thirty'.split(),map(str,[1,2,3,4,5,6,7,8,9,10,20,30])))
def lex(s):
 raw=re.findall(r"[a-z0-9]+(?:['’][a-z]+)?",s.lower().replace('’',"'"));out=[]
 for w in raw:
  if w=='gapyear':out+=['gap','year']
  elif w=='timeout':out+=['time','out']
  else:out.append(NUM.get(w,w))
 return out

def bound(w,phrase,end=False):
 flat=[(x,i) for i,t in enumerate(w) for x in lex(t[0])];q=lex(phrase);hits=[]
 for i in range(len(flat)-len(q)+1):
  if [x[0] for x in flat[i:i+len(q)]]==q:hits.append(flat[i+len(q)-1][1]+1 if end else flat[i][1])
 assert len(hits)==1,(phrase,hits,w)
 return hits[0]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for y,cc in TABLE.items():
 patches=[];decisions=[];canonical=None
 for key,(first,last,decision) in cc.items():
  p=O/str(y)/(key+'.json');d=json.loads(p.read_text());assert len(d['recognitions'])==2,(y,key,'独立模型未完成')
  r=d['recognitions'][0];assert r['model']=='parakeet' and r['words'];w=r['words'];a=bound(w,first);z=bound(w,last,True);assert a<z
  chosen=w[a:z];d['adopted_words']=chosen;d['adoption']={'parakeet_word_range':[a,z],'window':[chosen[0][1],chosen[-1][2]],'decision':decision,'method':'只取两个局部模型及原页能核定的内部可靠词窗，窗口截断边缘假词不采纳；未改任何词时间或原词拼写。'}
  p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');canonical=d['canonical_sha256']
  patches.append({'evidence_ref':str(p.relative_to(B)),'evidence_sha256':sha(p),'pointer':'/adopted_words','window':d['adoption']['window'],'decision':decision})
  decisions.append({'case':key,'decision':decision,'evidence_ref':str(p.relative_to(B)),'evidence_sha256':sha(p),'adopted_word_range':[a,z],'adopted_window':d['adoption']['window'],'source_sha256':d['source_sha256'],'texts':{x['model']:x['text'] for x in d['recognitions']}})
 patches.sort(key=lambda x:x['window'][0]);assert all(a['window'][1]<=b['window'][0] for a,b in zip(patches,patches[1:])),(y,'采纳词窗必须不重叠')
 (O/f'{y}-采纳词窗.json').write_text(json.dumps({'year':y,'canonical_source_sha256':canonical,'patches':patches,'decision_status':'逐项证据裁决；字幕最终音画审核不冒称approved'},ensure_ascii=False,indent=2)+'\n')
 (O/f'{y}-逐项裁决.json').write_text(json.dumps({'year':y,'decisions':decisions,'orthographic_equivalences':['color/colour','colored/coloured','travelled/traveled','travelling/traveling','under-served/underserved','over-lit/overlit','time-out/timeout','CV/C V','who is/who’s','it will/it’ll'],'retained_true_spoken_forms':['a year sharp（2023，原页+主ASR+独立Whisper均确证，不为语法修改）']},ensure_ascii=False,indent=2)+'\n')
 print(y,len(patches),'个不重叠真词窗，逐项裁决已保存')
