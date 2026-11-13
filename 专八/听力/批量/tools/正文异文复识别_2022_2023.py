"""2022完整源/2023正文异文的小窗双模型证据；仅分析，不改母稿或主ASR。"""
import importlib.util,json,time,subprocess,hashlib
from pathlib import Path
import numpy as np,sherpa_onnx
B=Path(__file__).resolve().parents[1];O=B/'核验/正文异文复核'
C={2022:[('greeting',851,860),('underserved',870,881),('education_article',901,911),('harriet_filler',941,950),('grants_number',971,985),('everfi',1021,1039),('hundreds',1264,1273),('light_only',1289,1308),('overlit',1314,1323),('emitted_light',1351,1363),('bulb',1426,1436)],
2023:[('following',153,161),('metaphor',207,216),('and_in',254,262),('when_where',314,323),('meaning_had',331,345),('id_say',397,409),('united_states',487,499),('chewed',604,614),('domain',899,909),('seriously_asked',924,939),('life_filler',947,964),('value_it',981,990),('gapyear',1036,1045),('project_question',1053,1063),('time_majority',1243,1263),('specific_culture',1306,1316),('travel_lists',1320,1332),('after_all',1333,1345),('qomolangma',1347,1362),('validation',1429,1450),('jim',1453,1462)]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def words(r,start,end):
 out=[];cur=None
 for token,ts in zip(r.tokens,r.timestamps):
  t=round(start+float(ts),3)
  if token.startswith(' ') or cur is None:
   if cur and cur[0]:out.append(cur)
   cur=[token.strip(),t,round(min(end,t+.08),3)]
  else:cur[0]+=token;cur[2]=round(min(end,t+.08),3)
 if cur and cur[0]:out.append(cur)
 return out
for model in ['parakeet','whisper']:
 m=Path('/workspace/tem8-check-model/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8') if model=='parakeet' else Path('/workspace/tem8-whisper-check/sherpa-onnx-whisper-base.en')
 if model=='parakeet':
  ff={k:m/(k+'.int8.onnx') for k in ['encoder','decoder','joiner']};ff['tokens']=m/'tokens.txt';asr=sherpa_onnx.OfflineRecognizer.from_transducer(**{k:str(v) for k,v in ff.items()},model_type='nemo_transducer',num_threads=1)
 else:
  ff={k:m/('base.en-'+v) for k,v in [('encoder','encoder.int8.onnx'),('decoder','decoder.int8.onnx'),('tokens','tokens.txt')]};asr=sherpa_onnx.OfflineRecognizer.from_whisper(**{k:str(v) for k,v in ff.items()},num_threads=1,enable_token_timestamps=True,enable_segment_timestamps=True)
 meta={k:{'file':v.name,'sha256':sha(v)} for k,v in ff.items()}
 for y,cc in C.items():
  prep=json.loads((B/f'预处理/{y}/原音准备.json').read_text());ent=prep['source_entries'][0];src=Path('/workspace')/ent['file'] if y==2022 else Path('/workspace/tem8-input')/ent['file'];assert sha(src)==ent['sha256']
  for key,a,z in cc:
   p=O/str(y)/(key+'.json');d=json.loads(p.read_text()) if p.exists() else {}
   if any(x['model']==model for x in d.get('recognitions',[])):continue
   start=max(0,a-(1.35 if model=='whisper' else 0));end=min(prep['canonical']['duration'],z+(1.1 if model=='whisper' else 0))
   pcm=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-t',str(end-start),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-']);audio=np.frombuffer(pcm,dtype='<f4');s=asr.create_stream();s.accept_waveform(16000,audio);t=time.monotonic();asr.decode_stream(s);r=s.result;has=bool(r.timestamps) and len(r.tokens)==len(r.timestamps)
   row={'model':model,'window':[start,end],'text':r.text,'tokens':r.tokens,'timestamps_relative':r.timestamps,'words':words(r,start,end) if has else [],'elapsed_seconds':round(time.monotonic()-t,3),'model_files':meta,'timestamps_available':has,'note':'真实模型token时刻；Whisper若无cross-attention则仅保留文本证据，不估词时。'}
   d.update({'year':y,'query':key,'source_file':ent['file'],'source_sha256':ent['sha256'],'canonical_sha256':prep['canonical']['sha256'],'primary_asr_sha256':sha(B/f'预处理/{y}/识别.json'),'script_sha256':sha(__file__),'recognitions':d.get('recognitions',[])+[row],'status':'机器证据待逐项裁决，不是approved'})
   save(p,d);print(model,y,key,r.text,flush=True)
 del asr
