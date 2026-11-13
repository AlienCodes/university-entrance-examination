"""回存实测完整话轮边界；只省略一条声谱证实未念的独立印本Mm。
不删除/修改录音，不分配unknown字词时间，保留最新95条manual_splits与原词注/ZH。
"""
import json,copy,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];O=B/'核验/2010—2015整句声学证据'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# 此独立纸源应声无实际事件：两模型均无，原44.1kHz双声道能量/频谱在整段前后语句之间只有底噪。
p=B/'译注草稿/2011.json';raw=p.read_bytes();d=json.loads(raw);unit=next(u for u in d['units'] if u['id']=='2011-B1');before_plans=copy.deepcopy([u.get('manual_splits',[]) for u in d['units']]);snapshot=copy.deepcopy(d)
left='Old children and adults often have less time and motivation to learn a second language.'
right='Another is related to the similarities and differences between one’s mother tongue and a second language.'
found=[i for i,s in enumerate(unit['sentences']) if s['en']=='Mm...' and i and i+1<len(unit['sentences']) and unit['sentences'][i-1]['en']==left and unit['sentences'][i+1]['en']==right]
audit=B/'核验/正文清理/2011-印本未念应声省略.json'
if found:
 assert len(found)==1;i=found[0];removed=copy.deepcopy(unit['sentences'][i]);proof=O/'2011-B1-28-spectral-evidence.json';sp=json.loads(proof.read_text());wave=json.loads((O/'2011-B1-28.json').read_text());assert sp['unique_ASR_bracket']==[890.94,891.26]
 assert not wave['measured_sentence_window'] and 'Mm' not in wave['secondary_model']['text'];parent_source=json.loads((B/'预处理/2011/原音准备.json').read_text());assert sp['canonical_source_sha256']==parent_source['canonical']['sha256']
 unit['sentences'].pop(i)
 rec={'year':2011,'unit':'2011-B1','removed_original_row':removed,'previous_en':left,'following_en':right,'unique_ASR_bracket':[890.94,891.26],'wider_spectral_window':sp['analysis_window'],'evidence':[{'file':'核验/2010—2015整句声学证据/2011-B1-28.json','sha256':sha(O/'2011-B1-28.json')},{'file':str(proof.relative_to(B)),'sha256':sha(proof)},{'file':sp['spectrogram_ref'],'sha256':sp['spectrogram_sha256']}],
  'decision':'原页有独立Mm...行；主/定点Parakeet与独立Whisper均无此声，44.1kHz双声道原音频谱实读：前句结束约890.45至下句起音约891.32之间仅低电平底噪，无独立鼻音/应声谐波事件。按root明确原音优先标准仅省略这条未念字幕，原行完整归档；录音不删、不造。',
  'preserved':'其余全部EN/ZH/w/word锚及最新manual_splits逐字不变。'}
 assert before_plans==[u.get('manual_splits',[]) for u in d['units']]
 expected=copy.deepcopy(snapshot);uu=next(u for u in expected['units'] if u['id']=='2011-B1');uu['sentences'].pop(i);assert expected==d
 assert p.read_bytes()==raw;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');audit.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
# 另一条Mm有清楚谐波、约998.25—998.84衰减鼻音，不能因ASR漏识而删。
sp=O/'2011-B1-50-spectral-evidence.json';v=json.loads(sp.read_text());assert v['canonical_source_sha256']==json.loads((B/'预处理/2011/原音准备.json').read_text())['canonical']['sha256']
mmproof=O/'2011-B1-50-已核整声响.json';mm={'year':2011,'unit':'2011-B1','en':'Mm...','window':[998.25,998.87],'source_sha256':v['source_sha256'],'canonical_source_sha256':v['canonical_source_sha256'],
 'spectral_evidence':{'file':str(sp.relative_to(B)),'sha256':sha(sp),'image':v['spectrogram_ref'],'image_sha256':v['spectrogram_sha256']},'source_refs':unit.get('source_refs',[]),
 'decision':'源页此处独立Mm；虽两ASR忽略非词声，但44.1kHz双声道频谱在998.25—998.84清楚出现独立低频谐波与衰减鼻音，998.85后为底噪。保留998.25—998.87整个应声事件，不给Mm任何逐字时刻；前句ASR词尾估计与该声有0.13s交叠，在整声真实范围中如实保留。'};mmproof.write_text(json.dumps(mm,ensure_ascii=False,indent=2)+'\n')
byyear={}
for file in sorted(O.glob('*.json')):
 if file.name.endswith('spectral-evidence.json') or file.name.endswith('已核整声响.json'):continue
 x=json.loads(file.read_text())
 if not x.get('measured_sentence_window'):continue
 if not x.get('known_word_window'):continue
 source=B/f'译注草稿/{x["year"]}.json';mother=json.loads(source.read_text());u=next(u for u in mother['units'] if u['id']==x['unit']);ss=[s for s in u['sentences'] if s['en']==x['en']];assert len(ss)==1
 a,z=x['measured_sentence_window'];event={'unit':x['unit'],'en':x['en'],'start':a,'end':z,'nonverbal':False,'whole_sentence_audio_verified':True,'word_alignment_policy':'retain_actual_ASR_only','evidence_ref':str(file.relative_to(B)),'evidence_sha256':sha(file),
 'decision':'源页与两路识别核过完整话轮语义；已实读原采样率双声道10ms包络及九窗总览图，边界包住全部实际词锚/弱音/节奏；未知字仍保留unknown，绝不以整句范围分配未知字秒。'}
 if "don't" in x['en']:event.update({'critical_semantics_verified':True,'critical_evidence':'本句否定don’t在主ASR及独立Whisper完整呈现，实际现有字锚保留；缺失只Uh/重复and轻音，未将否定当非言语放过。'})
 if 'da da' in x['en']:event['decision']+=' 节奏拟声是原页记谱且root独立Whisper已确认真实模仿，完整话轮承载，da内部不拆屏、不造逐音节时刻。'
 byyear.setdefault(x['year'],[]).append(event)
byyear.setdefault(2011,[]).append({'unit':'2011-B1','en':'Mm...','start':998.25,'end':998.87,'nonverbal':True,'evidence_ref':str(mmproof.relative_to(B)),'evidence_sha256':sha(mmproof),'decision':mm['decision']})
manifest=[]
for y,events in byyear.items():
 prep=json.loads((B/f'预处理/{y}/原音准备.json').read_text());p=B/f'核验/正文清理/{y}-整句声学采纳.json'
 old=json.loads(p.read_text()) if p.exists() else {'events':[]};merged=[e for e in old['events'] if (e['unit'],e['en']) not in {(e['unit'],e['en']) for e in events}]+events
 obj={'year':y,'canonical_source_sha256':prep['canonical']['sha256'],'events':merged,'policy':'仅完整话轮/整声响实测范围；实际word_alignment与unknown保留，绝不比例分摊词时。'};p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');manifest.append({'year':y,'file':str(p.relative_to(B)),'sha256':sha(p),'new_events':len(events)});print(y,'complete utterance/events',len(events))
(O/'整句话轮采纳清单.json').write_text(json.dumps({'files':manifest,'events':sum(x['new_events'] for x in manifest),'print_only_unspoken_omission':'核验/正文清理/2011-印本未念应声省略.json','manual_splits_untouched':True,'source_audio_untouched':True},ensure_ascii=False,indent=2)+'\n')
